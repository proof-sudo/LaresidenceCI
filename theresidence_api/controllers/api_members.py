# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.http import request

from .main import (
    api_response, api_error, validate_api_key,
    paginate, get_pagination_params, parse_json_body
)

_logger = logging.getLogger(__name__)


class ResidenceAPIMembers(http.Controller):
    """APIs pour les membres"""

    # ==========================================
    # GET Members
    # ==========================================
    @http.route('/api/v1/members', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_members(self):
        """Liste des membres"""
        try:
            page, size = get_pagination_params()

            # Filtres
            domain = [('is_residence_member', '=', True)]

            # Recherche par texte
            query = request.params.get('query')
            if query:
                domain.extend(['|', '|', '|',
                    ('name', 'ilike', query),
                    ('email', 'ilike', query),
                    ('phone', 'ilike', query),
                    ('company_name', 'ilike', query)
                ])

            # Filtre par statut
            status = request.params.get('status')
            if status:
                domain.append(('residence_membership_status', '=', status.lower()))

            # Filtre par type d'abonnement
            membership_type = request.params.get('membershipType')
            if membership_type:
                mtype = request.env['residence.membership.type'].sudo().get_by_code(membership_type)
                if mtype:
                    domain.append(('residence_membership_type_id', '=', mtype.id))

            partners = request.env['res.partner'].sudo().search(domain, order='name')

            data = [partner.to_api_dict() for partner in partners]
            result = paginate(data, page, size)

            return api_response(result)

        except Exception as e:
            _logger.error(f"Erreur get_members: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/members/<string:member_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_member(self, member_id):
        """Détail d'un membre"""
        try:
            partner = request.env['res.partner'].sudo().get_by_external_id(member_id)

            if not partner or not partner.is_residence_member:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            data = partner.to_api_dict(include_details=True)
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_member: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/members/by-qr/<string:qr_token>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_member_by_qr(self, qr_token):
        """Trouver un membre par token QR"""
        try:
            partner = request.env['res.partner'].sudo().get_by_qr_token(qr_token)

            if not partner:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            data = partner.to_api_dict(include_details=True)
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_member_by_qr: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/members/by-email/<string:email>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_member_by_email(self, email):
        """Trouver un membre par email"""
        try:
            partner = request.env['res.partner'].sudo().search([
                ('email', '=', email),
                ('is_residence_member', '=', True)
            ], limit=1)

            if not partner:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            data = partner.to_api_dict(include_details=True)
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_member_by_email: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # POST/PUT Members
    # ==========================================
    @http.route('/api/v1/members', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def create_member(self):
        """Créer un nouveau membre"""
        try:
            data = parse_json_body()
            if data is None:
                return api_error('Corps JSON invalide', error_code='INVALID_REQUEST', status=400)

            # Validation
            if not data.get('email'):
                return api_error('Email requis', error_code='INVALID_REQUEST', status=400)

            # Vérifier si un membre avec cet email existe déjà
            existing = request.env['res.partner'].sudo().search([
                ('email', '=', data.get('email')),
                ('is_residence_member', '=', True)
            ], limit=1)

            if existing:
                return api_error(
                    'Un membre avec cet email existe déjà',
                    error_code='DUPLICATE_EMAIL',
                    status=409
                )

            # Créer le membre
            partner = request.env['res.partner'].sudo().create_from_api(data)

            # Envoyer webhook
            config = request.env['residence.config'].sudo().get_config()
            if config:
                config.send_webhook(
                    event_type='MEMBER_CREATED',
                    entity_type='member',
                    entity_id=partner.residence_external_id,
                    data=partner.to_api_dict(),
                    new_status='ACTIVE' if partner.residence_membership_status == 'active' else 'PENDING'
                )

            return api_response(
                partner.to_api_dict(include_details=True),
                message='Membre créé avec succès',
                status=201
            )

        except Exception as e:
            _logger.error(f"Erreur create_member: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/members/<string:member_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    @validate_api_key
    def update_member(self, member_id):
        """Mettre à jour un membre"""
        try:
            data = parse_json_body()
            if data is None:
                return api_error('Corps JSON invalide', error_code='INVALID_REQUEST', status=400)

            partner = request.env['res.partner'].sudo().get_by_external_id(member_id)

            if not partner or not partner.is_residence_member:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            # Vérifier l'unicité de l'email si modifié
            if data.get('email') and data['email'] != partner.email:
                existing = request.env['res.partner'].sudo().search([
                    ('email', '=', data['email']),
                    ('is_residence_member', '=', True),
                    ('id', '!=', partner.id)
                ], limit=1)
                if existing:
                    return api_error(
                        'Un autre membre utilise cet email',
                        error_code='DUPLICATE_EMAIL',
                        status=409
                    )

            # Mettre à jour
            partner.update_from_api(data)

            # Envoyer webhook
            config = request.env['residence.config'].sudo().get_config()
            if config:
                config.send_webhook(
                    event_type='MEMBER_UPDATED',
                    entity_type='member',
                    entity_id=partner.residence_external_id,
                    data=partner.to_api_dict()
                )

            return api_response(
                partner.to_api_dict(include_details=True),
                message='Membre mis à jour avec succès'
            )

        except Exception as e:
            _logger.error(f"Erreur update_member: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Member Stats
    # ==========================================
    @http.route('/api/v1/members/<string:member_id>/stats', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_member_stats(self, member_id):
        """Statistiques d'un membre"""
        try:
            partner = request.env['res.partner'].sudo().get_by_external_id(member_id)

            if not partner or not partner.is_residence_member:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            # Calculer les stats
            SaleOrder = request.env['sale.order'].sudo()
            ResidenceOrder = request.env['residence.order'].sudo()

            # Réservations
            reservations = SaleOrder.search([
                ('partner_id', '=', partner.id),
                ('is_rental_order', '=', True)
            ])

            total_reservations = len(reservations)
            completed_reservations = len(reservations.filtered(
                lambda r: r.residence_reservation_status == 'completed'
            ))

            # Commandes
            orders = ResidenceOrder.search([('partner_id', '=', partner.id)])
            total_orders = len(orders)
            completed_orders = len(orders.filtered(lambda o: o.state == 'completed'))

            # Montants
            total_reservation_amount = sum(reservations.mapped('amount_total'))
            total_order_amount = sum(orders.mapped('amount_total'))

            return api_response({
                'memberId': member_id,
                'memberName': partner.name,
                'reservations': {
                    'total': total_reservations,
                    'completed': completed_reservations,
                    'totalAmount': total_reservation_amount
                },
                'orders': {
                    'total': total_orders,
                    'completed': completed_orders,
                    'totalAmount': total_order_amount
                },
                'totalSpent': total_reservation_amount + total_order_amount,
                'memberSince': partner.residence_joined_date.isoformat() if partner.residence_joined_date else None
            })

        except Exception as e:
            _logger.error(f"Erreur get_member_stats: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/members/<string:member_id>/reservations', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_member_reservations(self, member_id):
        """Réservations d'un membre"""
        try:
            page, size = get_pagination_params()

            partner = request.env['res.partner'].sudo().get_by_external_id(member_id)

            if not partner or not partner.is_residence_member:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            domain = [
                ('partner_id', '=', partner.id),
                ('is_rental_order', '=', True)
            ]

            # Filtre par statut
            status = request.params.get('status')
            if status:
                domain.append(('residence_reservation_status', '=', status.lower()))

            reservations = request.env['sale.order'].sudo().search(
                domain, order='create_date desc'
            )

            data = [res.to_reservation_api_dict() for res in reservations]
            result = paginate(data, page, size)

            return api_response(result)

        except Exception as e:
            _logger.error(f"Erreur get_member_reservations: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/members/<string:member_id>/orders', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_member_orders(self, member_id):
        """Commandes d'un membre"""
        try:
            page, size = get_pagination_params()

            partner = request.env['res.partner'].sudo().get_by_external_id(member_id)

            if not partner or not partner.is_residence_member:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            domain = [('partner_id', '=', partner.id)]

            # Filtre par statut
            status = request.params.get('status')
            if status:
                domain.append(('state', '=', status.lower()))

            orders = request.env['residence.order'].sudo().search(
                domain, order='create_date desc'
            )

            data = [order.to_api_dict() for order in orders]
            result = paginate(data, page, size)

            return api_response(result)

        except Exception as e:
            _logger.error(f"Erreur get_member_orders: {str(e)}")
            return api_error(str(e), status=500)
