# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.http import request

from .main import (
    api_response, api_error, validate_api_key,
    paginate, get_pagination_params, parse_json_body
)

_logger = logging.getLogger(__name__)


class ResidenceAPIOrders(http.Controller):
    """APIs pour les commandes restaurant"""

    # ==========================================
    # GET Orders
    # ==========================================
    @http.route('/api/v1/orders', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_orders(self):
        """Liste des commandes"""
        try:
            page, size = get_pagination_params()

            domain = []

            # Filtre par membre
            member_id = request.params.get('memberId')
            if member_id:
                partner = request.env['res.partner'].sudo().get_by_external_id(member_id)
                if partner:
                    domain.append(('partner_id', '=', partner.id))

            # Filtre par statut
            status = request.params.get('status')
            if status:
                domain.append(('state', '=', status.lower()))

            # Filtre par mode
            mode = request.params.get('mode')
            if mode:
                domain.append(('mode', '=', mode.lower()))

            # Tri
            sort = request.params.get('sort', 'create_date,desc')
            order = 'create_date desc'
            if sort:
                parts = sort.split(',')
                field = parts[0]
                direction = parts[1] if len(parts) > 1 else 'desc'
                field_mapping = {
                    'createdAt': 'create_date',
                    'orderedAt': 'ordered_date',
                    'status': 'state',
                    'totalAmount': 'amount_total'
                }
                odoo_field = field_mapping.get(field, field)
                order = f"{odoo_field} {direction}"

            orders = request.env['residence.order'].sudo().search(domain, order=order)

            data = [order.to_api_dict() for order in orders]
            result = paginate(data, page, size)

            return api_response(result)

        except Exception as e:
            _logger.error(f"Erreur get_orders: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/orders/<string:order_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_order(self, order_id):
        """Détail d'une commande"""
        try:
            order = request.env['residence.order'].sudo().get_by_external_id(order_id)

            if not order:
                return api_error('Commande non trouvée', error_code='ORDER_NOT_FOUND', status=404)

            return api_response(order.to_api_dict())

        except Exception as e:
            _logger.error(f"Erreur get_order: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/orders/by-qr/<string:qr_token>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_order_by_qr(self, qr_token):
        """Trouver une commande par token QR"""
        try:
            order = request.env['residence.order'].sudo().search([
                ('qr_token', '=', qr_token)
            ], limit=1)

            if not order:
                return api_error('Commande non trouvée', error_code='ORDER_NOT_FOUND', status=404)

            return api_response(order.to_api_dict())

        except Exception as e:
            _logger.error(f"Erreur get_order_by_qr: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # POST Order (Create)
    # ==========================================
    @http.route('/api/v1/orders', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def create_order(self):
        """Créer une nouvelle commande"""
        try:
            data = parse_json_body()
            if data is None:
                return api_error('Corps JSON invalide', error_code='INVALID_REQUEST', status=400)

            # Validation des champs requis
            if not data.get('memberId'):
                return api_error('Champ requis: memberId', error_code='INVALID_REQUEST', status=400)

            if not data.get('items') or len(data.get('items', [])) == 0:
                return api_error('Au moins un article est requis', error_code='INVALID_REQUEST', status=400)

            # Vérifier le membre
            partner = request.env['res.partner'].sudo().get_by_external_id(data['memberId'])
            if not partner:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            # Vérifier les articles
            for item in data.get('items', []):
                product = request.env['product.template'].sudo().get_by_external_id(item.get('menuItemId'))
                if not product or not product.is_residence_menu_item:
                    return api_error(
                        f"Article non trouvé: {item.get('menuItemId')}",
                        error_code='MENU_ITEM_NOT_FOUND',
                        status=404
                    )
                if not product.residence_is_available:
                    return api_error(
                        f"Article non disponible: {product.name}",
                        error_code='MENU_ITEM_NOT_AVAILABLE',
                        status=400
                    )

            # Créer la commande
            order = request.env['residence.order'].sudo().create_from_api(data)

            return api_response(
                order.to_api_dict(),
                message='Commande créée avec succès',
                status=201
            )

        except Exception as e:
            _logger.error(f"Erreur create_order: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Status Actions
    # ==========================================
    @http.route('/api/v1/orders/<string:order_id>/confirm', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def confirm_order(self, order_id):
        """Confirmer une commande"""
        try:
            order = request.env['residence.order'].sudo().get_by_external_id(order_id)

            if not order:
                return api_error('Commande non trouvée', error_code='ORDER_NOT_FOUND', status=404)

            if order.state != 'pending':
                return api_error(
                    'Seules les commandes en attente peuvent être confirmées',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            order.action_confirm()

            return api_response(
                order.to_api_dict(),
                message='Commande confirmée'
            )

        except Exception as e:
            _logger.error(f"Erreur confirm_order: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/orders/<string:order_id>/prepare', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def prepare_order(self, order_id):
        """Commencer la préparation"""
        try:
            order = request.env['residence.order'].sudo().get_by_external_id(order_id)

            if not order:
                return api_error('Commande non trouvée', error_code='ORDER_NOT_FOUND', status=404)

            if order.state != 'confirmed':
                return api_error(
                    'Seules les commandes confirmées peuvent être préparées',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            order.action_start_preparation()

            return api_response(
                order.to_api_dict(),
                message='Préparation commencée'
            )

        except Exception as e:
            _logger.error(f"Erreur prepare_order: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/orders/<string:order_id>/ready', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def ready_order(self, order_id):
        """Marquer la commande comme prête"""
        try:
            order = request.env['residence.order'].sudo().get_by_external_id(order_id)

            if not order:
                return api_error('Commande non trouvée', error_code='ORDER_NOT_FOUND', status=404)

            if order.state not in ('confirmed', 'preparing'):
                return api_error(
                    'Cette commande ne peut pas être marquée comme prête',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            order.action_mark_ready()

            return api_response(
                order.to_api_dict(),
                message='Commande prête'
            )

        except Exception as e:
            _logger.error(f"Erreur ready_order: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/orders/<string:order_id>/complete', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def complete_order(self, order_id):
        """Terminer la commande"""
        try:
            order = request.env['residence.order'].sudo().get_by_external_id(order_id)

            if not order:
                return api_error('Commande non trouvée', error_code='ORDER_NOT_FOUND', status=404)

            if order.state != 'ready':
                return api_error(
                    'Seules les commandes prêtes peuvent être terminées',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            order.action_complete()

            return api_response(
                order.to_api_dict(),
                message='Commande terminée'
            )

        except Exception as e:
            _logger.error(f"Erreur complete_order: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/orders/<string:order_id>/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def cancel_order(self, order_id):
        """Annuler la commande"""
        try:
            order = request.env['residence.order'].sudo().get_by_external_id(order_id)

            if not order:
                return api_error('Commande non trouvée', error_code='ORDER_NOT_FOUND', status=404)

            if order.state in ('completed', 'cancelled'):
                return api_error(
                    'Cette commande ne peut pas être annulée',
                    error_code='INVALID_STATUS_TRANSITION',
                    status=400
                )

            # Récupérer le motif
            data = parse_json_body() or {}
            reason = data.get('reason', '')

            order.action_cancel(reason=reason)

            return api_response(
                order.to_api_dict(),
                message='Commande annulée'
            )

        except Exception as e:
            _logger.error(f"Erreur cancel_order: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Kitchen Display
    # ==========================================
    @http.route('/api/v1/orders/kitchen', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_kitchen_orders(self):
        """Commandes pour l'affichage cuisine"""
        try:
            # Commandes actives à préparer
            orders = request.env['residence.order'].sudo().search([
                ('state', 'in', ['confirmed', 'preparing'])
            ], order='ordered_date asc')

            data = []
            for order in orders:
                order_data = order.to_api_dict()
                # Ajouter le temps écoulé
                if order.ordered_date:
                    from datetime import datetime
                    elapsed = (datetime.now() - order.ordered_date).total_seconds() / 60
                    order_data['elapsedMinutes'] = round(elapsed, 1)
                data.append(order_data)

            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_kitchen_orders: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/orders/ready-for-pickup', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_ready_orders(self):
        """Commandes prêtes pour récupération"""
        try:
            orders = request.env['residence.order'].sudo().search([
                ('state', '=', 'ready')
            ], order='ready_date asc')

            data = [order.to_api_dict() for order in orders]
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_ready_orders: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Order Item Status
    # ==========================================
    @http.route('/api/v1/orders/<string:order_id>/items/<string:item_id>/status', type='http', auth='public', methods=['PUT'], csrf=False)
    @validate_api_key
    def update_item_status(self, order_id, item_id):
        """Mettre à jour le statut d'un article"""
        try:
            data = parse_json_body()
            if data is None:
                return api_error('Corps JSON invalide', error_code='INVALID_REQUEST', status=400)

            order = request.env['residence.order'].sudo().get_by_external_id(order_id)
            if not order:
                return api_error('Commande non trouvée', error_code='ORDER_NOT_FOUND', status=404)

            line = request.env['residence.order.line'].sudo().search([
                ('order_id', '=', order.id),
                ('external_id', '=', item_id)
            ], limit=1)

            if not line:
                return api_error('Article non trouvé', error_code='ITEM_NOT_FOUND', status=404)

            new_status = data.get('status', '').lower()
            if new_status not in ('pending', 'preparing', 'ready'):
                return api_error('Statut invalide', error_code='INVALID_REQUEST', status=400)

            line.preparation_state = new_status

            return api_response(
                order.to_api_dict(),
                message='Statut mis à jour'
            )

        except Exception as e:
            _logger.error(f"Erreur update_item_status: {str(e)}")
            return api_error(str(e), status=500)
