# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from odoo import http
from odoo.http import request

from .main import (
    api_response, api_error, validate_api_key,
    paginate, get_pagination_params, parse_json_body
)

_logger = logging.getLogger(__name__)


class ResidenceAPIReservations(http.Controller):
    """APIs pour les réservations de salles"""

    # ==========================================
    # GET Reservations
    # ==========================================
    @http.route('/api/v1/reservations', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_reservations(self):
        """Liste des réservations"""
        try:
            page, size = get_pagination_params()

            # Filtres de base
            domain = [('is_rental_order', '=', True)]

            # Filtre par membre
            member_id = request.params.get('memberId')
            if member_id:
                partner = request.env['res.partner'].sudo().get_by_external_id(member_id)
                if partner:
                    domain.append(('partner_id', '=', partner.id))

            # Filtre par salle
            space_id = request.params.get('spaceId')
            if space_id:
                space = request.env['product.template'].sudo().get_by_external_id(space_id)
                if space:
                    domain.append(('residence_space_id', '=', space.id))

            # Filtre par statut
            status = request.params.get('status')
            if status:
                domain.append(('residence_reservation_status', '=', status.lower()))

            # Filtre par dates
            start_date = request.params.get('startDate')
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    domain.append(('residence_start_time', '>=', start_dt))
                except ValueError:
                    pass

            end_date = request.params.get('endDate')
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    domain.append(('residence_end_time', '<=', end_dt))
                except ValueError:
                    pass

            # Tri
            sort = request.params.get('sort', 'create_date,desc')
            order = 'create_date desc'
            if sort:
                parts = sort.split(',')
                field = parts[0]
                direction = parts[1] if len(parts) > 1 else 'desc'
                # Mapping des champs API vers Odoo
                field_mapping = {
                    'createdAt': 'create_date',
                    'startTime': 'residence_start_time',
                    'endTime': 'residence_end_time',
                    'status': 'residence_reservation_status'
                }
                odoo_field = field_mapping.get(field, field)
                order = f"{odoo_field} {direction}"

            reservations = request.env['sale.order'].sudo().search(domain, order=order)

            data = [res.to_reservation_api_dict() for res in reservations]
            result = paginate(data, page, size)

            return api_response(result)

        except Exception as e:
            _logger.error(f"Erreur get_reservations: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/reservations/<string:reservation_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_reservation(self, reservation_id):
        """Détail d'une réservation"""
        try:
            reservation = request.env['sale.order'].sudo().get_by_external_id(reservation_id)

            if not reservation or not reservation.is_rental_order:
                return api_error('Réservation non trouvée', error_code='RESERVATION_NOT_FOUND', status=404)

            return api_response(reservation.to_reservation_api_dict())

        except Exception as e:
            _logger.error(f"Erreur get_reservation: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # POST Reservation (Create)
    # ==========================================
    @http.route('/api/v1/reservations', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def create_reservation(self):
        """Créer une nouvelle réservation"""
        try:
            data = parse_json_body()
            if data is None:
                return api_error('Corps JSON invalide', error_code='INVALID_REQUEST', status=400)

            # Validation des champs requis
            required_fields = ['memberId', 'spaceId', 'startTime', 'endTime']
            for field in required_fields:
                if not data.get(field):
                    return api_error(f'Champ requis: {field}', error_code='INVALID_REQUEST', status=400)

            # Vérifier le membre
            partner = request.env['res.partner'].sudo().get_by_external_id(data['memberId'])
            if not partner:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            # Vérifier la salle
            space = request.env['product.template'].sudo().get_by_external_id(data['spaceId'])
            if not space or not space.is_residence_space:
                return api_error('Salle non trouvée', error_code='SPACE_NOT_FOUND', status=404)

            # Vérifier disponibilité
            try:
                start_time = datetime.fromisoformat(data['startTime'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(data['endTime'].replace('Z', '+00:00'))
            except ValueError:
                return api_error('Format de date invalide', error_code='INVALID_REQUEST', status=400)

            # Vérifier les conflits de réservation
            conflicts = request.env['sale.order'].sudo().search([
                ('residence_space_id', '=', space.id),
                ('residence_reservation_status', 'in', ['pending', 'approved', 'checked_in']),
                ('residence_start_time', '<', end_time),
                ('residence_end_time', '>', start_time)
            ])

            if conflicts:
                return api_error(
                    'La salle n\'est pas disponible pour ce créneau',
                    error_code='SPACE_NOT_AVAILABLE',
                    status=409
                )

            # Créer la réservation
            reservation = request.env['sale.order'].sudo().create_reservation_from_api(data)

            # Envoyer webhook
            config = request.env['residence.config'].sudo().get_config()
            if config:
                config.send_webhook(
                    event_type='RESERVATION_CREATED',
                    entity_type='reservation',
                    entity_id=reservation.residence_external_id,
                    data=reservation.to_reservation_api_dict(),
                    new_status='PENDING'
                )

            return api_response(
                reservation.to_reservation_api_dict(),
                message='Réservation créée avec succès',
                status=201
            )

        except Exception as e:
            _logger.error(f"Erreur create_reservation: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # PUT Reservation (Update)
    # ==========================================
    @http.route('/api/v1/reservations/<string:reservation_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    @validate_api_key
    def update_reservation(self, reservation_id):
        """Mettre à jour une réservation"""
        try:
            data = parse_json_body()
            if data is None:
                return api_error('Corps JSON invalide', error_code='INVALID_REQUEST', status=400)

            reservation = request.env['sale.order'].sudo().get_by_external_id(reservation_id)

            if not reservation or not reservation.is_rental_order:
                return api_error('Réservation non trouvée', error_code='RESERVATION_NOT_FOUND', status=404)

            # Vérifier que la réservation peut être modifiée
            if reservation.residence_reservation_status in ('checked_in', 'completed', 'cancelled'):
                return api_error(
                    'Cette réservation ne peut plus être modifiée',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            # Mise à jour des champs
            vals = {}

            if 'guestCount' in data:
                vals['residence_guest_count'] = data['guestCount']

            if 'notes' in data:
                vals['residence_notes'] = data['notes']

            # Si les dates changent, vérifier les conflits
            if data.get('startTime') or data.get('endTime'):
                try:
                    start_time = datetime.fromisoformat(data.get('startTime', '').replace('Z', '+00:00')) \
                        if data.get('startTime') else reservation.residence_start_time
                    end_time = datetime.fromisoformat(data.get('endTime', '').replace('Z', '+00:00')) \
                        if data.get('endTime') else reservation.residence_end_time
                except ValueError:
                    return api_error('Format de date invalide', error_code='INVALID_REQUEST', status=400)

                # Vérifier les conflits (excluant cette réservation)
                conflicts = request.env['sale.order'].sudo().search([
                    ('residence_space_id', '=', reservation.residence_space_id.id),
                    ('residence_reservation_status', 'in', ['pending', 'approved', 'checked_in']),
                    ('residence_start_time', '<', end_time),
                    ('residence_end_time', '>', start_time),
                    ('id', '!=', reservation.id)
                ])

                if conflicts:
                    return api_error(
                        'La salle n\'est pas disponible pour ce créneau',
                        error_code='SPACE_NOT_AVAILABLE',
                        status=409
                    )

                # Mettre à jour les lignes de location
                for line in reservation.order_line.filtered(lambda l: l.is_rental):
                    line.write({
                        'start_date': start_time,
                        'return_date': end_time
                    })

            if vals:
                reservation.write(vals)

            # Mettre à jour l'événement calendrier
            reservation._create_or_update_calendar_event()

            # Envoyer webhook
            config = request.env['residence.config'].sudo().get_config()
            if config:
                config.send_webhook(
                    event_type='RESERVATION_UPDATED',
                    entity_type='reservation',
                    entity_id=reservation.residence_external_id,
                    data=reservation.to_reservation_api_dict()
                )

            return api_response(
                reservation.to_reservation_api_dict(),
                message='Réservation mise à jour avec succès'
            )

        except Exception as e:
            _logger.error(f"Erreur update_reservation: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # DELETE Reservation (Cancel)
    # ==========================================
    @http.route('/api/v1/reservations/<string:reservation_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    @validate_api_key
    def delete_reservation(self, reservation_id):
        """Annuler une réservation"""
        try:
            reservation = request.env['sale.order'].sudo().get_by_external_id(reservation_id)

            if not reservation or not reservation.is_rental_order:
                return api_error('Réservation non trouvée', error_code='RESERVATION_NOT_FOUND', status=404)

            # Vérifier que la réservation peut être annulée
            if reservation.residence_reservation_status in ('completed', 'cancelled'):
                return api_error(
                    'Cette réservation ne peut pas être annulée',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            # Annuler
            reservation.action_cancel_reservation()

            return api_response(
                {'id': reservation_id, 'status': 'CANCELLED'},
                message='Réservation annulée avec succès'
            )

        except Exception as e:
            _logger.error(f"Erreur delete_reservation: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Status Actions
    # ==========================================
    @http.route('/api/v1/reservations/<string:reservation_id>/approve', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def approve_reservation(self, reservation_id):
        """Approuver une réservation"""
        try:
            reservation = request.env['sale.order'].sudo().get_by_external_id(reservation_id)

            if not reservation or not reservation.is_rental_order:
                return api_error('Réservation non trouvée', error_code='RESERVATION_NOT_FOUND', status=404)

            if reservation.residence_reservation_status != 'pending':
                return api_error(
                    'Seules les réservations en attente peuvent être approuvées',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            reservation.action_approve_reservation()

            return api_response(
                reservation.to_reservation_api_dict(),
                message='Réservation approuvée'
            )

        except Exception as e:
            _logger.error(f"Erreur approve_reservation: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/reservations/<string:reservation_id>/reject', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def reject_reservation(self, reservation_id):
        """Rejeter une réservation"""
        try:
            reservation = request.env['sale.order'].sudo().get_by_external_id(reservation_id)

            if not reservation or not reservation.is_rental_order:
                return api_error('Réservation non trouvée', error_code='RESERVATION_NOT_FOUND', status=404)

            if reservation.residence_reservation_status != 'pending':
                return api_error(
                    'Seules les réservations en attente peuvent être rejetées',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            # Récupérer le motif
            reason = request.params.get('reason', '')

            reservation.action_reject_reservation(reason=reason)

            return api_response(
                reservation.to_reservation_api_dict(),
                message='Réservation rejetée'
            )

        except Exception as e:
            _logger.error(f"Erreur reject_reservation: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/reservations/<string:reservation_id>/check-in', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def checkin_reservation(self, reservation_id):
        """Check-in d'une réservation"""
        try:
            reservation = request.env['sale.order'].sudo().get_by_external_id(reservation_id)

            if not reservation or not reservation.is_rental_order:
                return api_error('Réservation non trouvée', error_code='RESERVATION_NOT_FOUND', status=404)

            if reservation.residence_reservation_status != 'approved':
                return api_error(
                    'Seules les réservations approuvées peuvent faire le check-in',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            reservation.action_checkin_reservation()

            return api_response(
                reservation.to_reservation_api_dict(),
                message='Check-in effectué'
            )

        except Exception as e:
            _logger.error(f"Erreur checkin_reservation: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/reservations/<string:reservation_id>/complete', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def complete_reservation(self, reservation_id):
        """Terminer une réservation"""
        try:
            reservation = request.env['sale.order'].sudo().get_by_external_id(reservation_id)

            if not reservation or not reservation.is_rental_order:
                return api_error('Réservation non trouvée', error_code='RESERVATION_NOT_FOUND', status=404)

            if reservation.residence_reservation_status not in ('approved', 'checked_in'):
                return api_error(
                    'Cette réservation ne peut pas être terminée',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            reservation.action_complete_reservation()

            return api_response(
                reservation.to_reservation_api_dict(),
                message='Réservation terminée'
            )

        except Exception as e:
            _logger.error(f"Erreur complete_reservation: {str(e)}")
            return api_error(str(e), status=500)
