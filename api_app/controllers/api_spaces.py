# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta

from odoo import http
from odoo.http import request

from .main import (
    api_response, api_error, validate_api_key,
    paginate, get_pagination_params, get_locale
)

_logger = logging.getLogger(__name__)


class ResidenceAPISpaces(http.Controller):
    """APIs pour les salles/espaces"""

    # ==========================================
    # Locations (Emplacements)
    # ==========================================
    @http.route('/api/v1/locations', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_locations(self):
        """Liste des emplacements/bâtiments"""
        try:
            locale = get_locale()
            locations = request.env['residence.location'].sudo().search([])

            data = [loc.to_api_dict() for loc in locations]
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_locations: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/locations/<string:location_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_location(self, location_id):
        """Détail d'un emplacement"""
        try:
            location = request.env['residence.location'].sudo().get_by_external_id(location_id)
            if not location:
                return api_error('Emplacement non trouvé', error_code='NOT_FOUND', status=404)

            return api_response(location.to_api_dict())

        except Exception as e:
            _logger.error(f"Erreur get_location: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Spaces (Salles)
    # ==========================================
    @http.route('/api/v1/spaces', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_spaces(self):
        """Liste des salles disponibles"""
        try:
            locale = get_locale()
            page, size = get_pagination_params()

            # Filtres
            domain = [('is_residence_space', '=', True)]

            location_id = request.params.get('locationId')
            if location_id:
                location = request.env['residence.location'].sudo().get_by_external_id(location_id)
                if location:
                    domain.append(('residence_location_id', '=', location.id))

            state = request.params.get('state')
            if state:
                domain.append(('residence_space_state', '=', state.lower()))

            min_capacity = request.params.get('minCapacity')
            if min_capacity:
                try:
                    domain.append(('residence_capacity', '>=', int(min_capacity)))
                except ValueError:
                    pass

            # Recherche
            ProductTemplate = request.env['product.template'].sudo()
            spaces = ProductTemplate.search(domain, order='name')

            # Convertir en format API
            data = [space.to_space_api_dict() for space in spaces]

            # Paginer
            result = paginate(data, page, size)
            return api_response(result)

        except Exception as e:
            _logger.error(f"Erreur get_spaces: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/spaces/<string:space_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_space(self, space_id):
        """Détail d'une salle"""
        try:
            space = request.env['product.template'].sudo().get_by_external_id(space_id)

            if not space or not space.is_residence_space:
                return api_error('Salle non trouvée', error_code='SPACE_NOT_FOUND', status=404)

            data = space.to_space_api_dict()

            # Ajouter les détails supplémentaires
            data['description'] = space.description_sale or space.description or ''
            data['fullDescription'] = space.description or ''

            # Tarifs (si sale_renting est installé)
            if hasattr(space, 'rent_ok') and space.rent_ok:
                data['isRentable'] = True
                # Les tarifs sont gérés par le module sale_renting
            else:
                data['isRentable'] = False

            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_space: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/spaces/<string:space_id>/availability', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_space_availability(self, space_id):
        """Disponibilités d'une salle"""
        try:
            space = request.env['product.template'].sudo().get_by_external_id(space_id)

            if not space or not space.is_residence_space:
                return api_error('Salle non trouvée', error_code='SPACE_NOT_FOUND', status=404)

            # Récupérer les paramètres de date
            start_date_str = request.params.get('startDate')
            end_date_str = request.params.get('endDate')

            if start_date_str:
                try:
                    start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                except ValueError:
                    start_date = datetime.now()
            else:
                start_date = datetime.now()

            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                except ValueError:
                    end_date = start_date + timedelta(days=7)
            else:
                end_date = start_date + timedelta(days=7)

            # Récupérer les réservations existantes
            SaleOrder = request.env['sale.order'].sudo()
            reservations = SaleOrder.search([
                ('residence_space_id', '=', space.id),
                ('residence_reservation_status', 'in', ['pending', 'approved', 'checked_in']),
                ('residence_start_time', '<=', end_date),
                ('residence_end_time', '>=', start_date)
            ])

            # Créneaux réservés
            booked_slots = []
            for res in reservations:
                booked_slots.append({
                    'startTime': res.residence_start_time.isoformat() if res.residence_start_time else None,
                    'endTime': res.residence_end_time.isoformat() if res.residence_end_time else None,
                    'status': res.residence_reservation_status
                })

            return api_response({
                'spaceId': space_id,
                'spaceName': space.name,
                'queryStartDate': start_date.isoformat(),
                'queryEndDate': end_date.isoformat(),
                'currentState': space.residence_space_state,
                'bookedSlots': booked_slots,
                'isAvailableNow': space.residence_space_state == 'available'
            })

        except Exception as e:
            _logger.error(f"Erreur get_space_availability: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Equipment (Équipements)
    # ==========================================
    @http.route('/api/v1/equipment', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_equipment(self):
        """Liste des équipements disponibles"""
        try:
            equipment = request.env['residence.space.equipment'].sudo().search([])
            data = [eq.to_api_dict() for eq in equipment]
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_equipment: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/equipment/<string:equipment_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_equipment_detail(self, equipment_id):
        """Détail d'un équipement"""
        try:
            equipment = request.env['residence.space.equipment'].sudo().get_by_external_id(equipment_id)
            if not equipment:
                return api_error('Équipement non trouvé', error_code='NOT_FOUND', status=404)

            return api_response(equipment.to_api_dict())

        except Exception as e:
            _logger.error(f"Erreur get_equipment_detail: {str(e)}")
            return api_error(str(e), status=500)
