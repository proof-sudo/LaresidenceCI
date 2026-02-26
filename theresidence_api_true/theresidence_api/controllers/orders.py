# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request
from .main import API_PREFIX, api_auth, success_response, error_response, paginated_response

_logger = logging.getLogger(__name__)


class OrdersController(http.Controller):
    """Controller pour les commandes restaurant."""
    @http.route(f'{API_PREFIX}/orders', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_orders')
    def list_orders(self, **kwargs):
        page = int(kwargs.get('page', 0))
        size = min(int(kwargs.get('size', 20)), 100)

        # Recherche dans POS (ajout 26/02/2026 pour inclure les commandes déjà envoyées au POS)
        domain_pos = [('x_tr_is_mobile_order', '=', True)]
        if kwargs.get('memberId'):
            domain_pos.append(('x_tr_member_id.x_tr_uuid', '=', kwargs['memberId']))
        if kwargs.get('status'):
            domain_pos.append(('x_tr_order_status', '=', kwargs['status']))
        if kwargs.get('mode'):
            domain_pos.append(('x_tr_order_mode', '=', kwargs['mode']))
        
        orders_pos = request.env['pos.order'].sudo().search(domain_pos)
        
        # Recherche dans Mobile Order pour les commandes non encore envoyées au POS
        domain_mobile = [('x_tr_is_mobile_order', '=', True)]
        if kwargs.get('memberId'):
            domain_mobile.append(('partner_id.x_tr_uuid', '=', kwargs['memberId']))
        if kwargs.get('status'):
            domain_mobile.append(('x_tr_order_status', '=', kwargs['status']))  # ici on map state ↔ status
        if kwargs.get('mode'):
            domain_mobile.append(('x_tr_order_mode', '=', kwargs['mode']))
        
        orders_mobile = request.env['mobile.order'].sudo().search(domain_mobile)
        
        # Fusionner les résultats et trier par date de création
        all_orders = orders_pos + orders_mobile
        all_orders = all_orders.sorted(key=lambda o: o.create_date, reverse=True)

        total = len(all_orders)
        # Pagination manuelle
        start = page * size
        end = start + size
        paginated_orders = all_orders[start:end]

        return paginated_response([o.to_order_api_dict() for o in paginated_orders], total, page, size)
    # @http.route(f'{API_PREFIX}/orders', type='http', auth='public', methods=['GET'], csrf=False)
    # @api_auth('read_orders')
    # def list_orders(self, **kwargs):
    #     page = int(kwargs.get('page', 0))
    #     size = min(int(kwargs.get('size', 20)), 100)
        
    #     domain = [('x_tr_is_mobile_order', '=', True)]
    #     if kwargs.get('memberId'):
    #         domain.append(('x_tr_member_id.x_tr_uuid', '=', kwargs['memberId']))
    #     if kwargs.get('status'):
    #         domain.append(('x_tr_order_status', '=', kwargs['status']))
    #     if kwargs.get('mode'):
    #         domain.append(('x_tr_order_mode', '=', kwargs['mode']))
        
    #     total = request.env['pos.order'].sudo().search_count(domain)
    #     orders = request.env['pos.order'].sudo().search(domain, offset=page * size, limit=size, order='create_date desc')
    #     return paginated_response([o.to_order_api_dict() for o in orders], total, page, size)
    @http.route(f'{API_PREFIX}/orders/<string:order_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_orders')
    def get_order(self, order_id, **kwargs):
        # On cherche d'abord dans mobile.order
        MobileOrder = request.env['mobile.order'].sudo()
        PosOrder = request.env['pos.order'].sudo()

        order = MobileOrder.search([
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        ], limit=1)

        # Si pas trouvé dans mobile.order, on cherche dans pos.order
        if not order:
            order = PosOrder.search([
                ('x_tr_is_mobile_order', '=', True),
                '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
            ], limit=1)

        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)

        # On s'assure que le dict de retour est uniforme
        if hasattr(order, 'to_order_api_dict'):
            data = order.to_order_api_dict()
        else:
            # fallback si mobile.order n'a pas cette méthode
            data = {
                'id': getattr(order, 'x_tr_uuid', order.id),
                'status': getattr(order, 'x_tr_order_status', 'PENDING'),
                'partner': getattr(order, 'partner_id', False) and {
                    'id': order.partner_id.id,
                    'name': order.partner_id.name,
                    'email': order.partner_id.email
                } or {},
            }

        return success_response(data)
    # @http.route(f'{API_PREFIX}/orders/<string:order_id>', type='http', auth='public', methods=['GET'], csrf=False)
    # @api_auth('read_orders')
    # def get_order(self, order_id, **kwargs):
    #     order = request.env['pos.order'].sudo().search([
    #         ('x_tr_is_mobile_order', '=', True),
    #         '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
    #     ], limit=1)
    #     if not order:
    #         return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
    #     return success_response(order.to_order_api_dict())

    @http.route(f'{API_PREFIX}/orders', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_orders')
    def create_order(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data)
            order = request.env['mobile.order'].sudo().create_order_from_api(data)
            # order = request.env['pos.order'].sudo().create_order_from_api(data)
            return success_response(order.to_order_api_dict(), 201)
        except Exception as e:
            _logger.error(f"Error creating order: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    @api_auth('write_orders')
    def update_order(self, order_id, **kwargs):
        order = request.env['mobile.order'].sudo().search([
            ('x_tr_is_mobile_order', '=', True),
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        ], limit=1)
        # order = request.env['pos.order'].sudo().search([
        #     ('x_tr_is_mobile_order', '=', True),
        #     '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        # ], limit=1)
        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
        if order.x_tr_order_status != 'PENDING':
            return error_response('Only PENDING orders can be updated', 'INVALID_STATUS_TRANSITION', 400)
        
        try:
            data = json.loads(request.httprequest.data)
            
            # Mettre à jour les champs simples
            vals = {}
            if 'deliveryAddress' in data:
                vals['x_tr_delivery_address'] = data['deliveryAddress']
            if 'notes' in data:
                vals['note'] = data['notes']
            if 'mode' in data:
                vals['x_tr_order_mode'] = data['mode']
            if vals:
                order.write(vals)
            
            # Remplacer les items si fournis
            if 'items' in data:
                order.lines.unlink()
                for item in data['items']:
                    product = request.env['product.product'].sudo().browse(int(item['menuItemId']))
                    if product.exists():
                        request.env['pos.order.line'].sudo().create({
                            'order_id': order.id,
                            'product_id': product.id,
                            'qty': item.get('quantity', 1),
                            'price_unit': item.get('unitPrice', product.lst_price),
                            'price_subtotal': item.get('quantity', 1) * item.get('unitPrice', product.lst_price),
                            'price_subtotal_incl': item.get('quantity', 1) * item.get('unitPrice', product.lst_price),
                        })
            
            return success_response(order.to_order_api_dict())
        except Exception as e:
            _logger.error(f"Error updating order: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>/confirm', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_orders')
    def confirm_order(self, order_id, **kwargs):
        MobileOrder = request.env['mobile.order'].sudo()
        PosOrder = request.env['pos.order'].sudo()

        # Cherche d'abord dans mobile.order
        order = MobileOrder.search([
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        ], limit=1)

        # Si pas trouvé, cherche dans pos.order
        if not order:
            order = PosOrder.search([
                ('x_tr_is_mobile_order', '=', True),
                '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
            ], limit=1)

        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)

        try:
            # Si la commande est une MobileOrder PENDING, on la valide et l'envoie au POS
            if order._name == 'mobile.order' and order.x_tr_order_status == 'PENDING':
                order.action_validate()
                order.action_send_to_pos()
            # Si c'est déjà un POS order, on peut confirmer via POS
            elif hasattr(order, 'action_confirm_order'):
                order.action_confirm_order()
            else:
                return error_response('Cannot confirm this order', 'INVALID_STATUS_TRANSITION', 400)

            # Retour uniforme pour l'App
            if hasattr(order, 'to_order_api_dict'):
                data = order.to_order_api_dict()
            else:
                data = {
                    'id': getattr(order, 'x_tr_uuid', order.id),
                    'status': getattr(order, 'x_tr_order_status', 'PENDING'),
                    'partner': getattr(order, 'partner_id', False) and {
                        'id': order.partner_id.id,
                        'name': order.partner_id.name,
                        'email': order.partner_id.email
                    } or {},
                }

            return success_response(data)
        except Exception as e:
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)
    # def confirm_order(self, order_id, **kwargs):
        
    #     order = request.env['pos.order'].sudo().search([
    #         ('x_tr_is_mobile_order', '=', True),
    #         '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
    #     ], limit=1)
    #     if not order:
    #         return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
        
    #     try:
    #         order.action_confirm_order()
    #         return success_response(order.to_order_api_dict())
    #     except Exception as e:
    #         return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>/ready', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_orders')
    def ready_order(self, order_id, **kwargs):
        order = request.env['pos.order'].sudo().search([
            ('x_tr_is_mobile_order', '=', True),
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        ], limit=1)
        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
        
        try:
            order.action_ready_order()
            return success_response(order.to_order_api_dict())
        except Exception as e:
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>/complete', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_orders')
    def complete_order(self, order_id, **kwargs):
        order = request.env['pos.order'].sudo().search([
            ('x_tr_is_mobile_order', '=', True),
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        ], limit=1)
        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
        
        try:
            order.action_complete_order()
            return success_response(order.to_order_api_dict())
        except Exception as e:
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_orders')
    def cancel_order(self, order_id, **kwargs):
        order = request.env['pos.order'].sudo().search([
            ('x_tr_is_mobile_order', '=', True),
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        ], limit=1)
        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
        
        try:
            reason = kwargs.get('reason', '')
            order.action_cancel_order(reason)
            return success_response({
                'id': order.x_tr_uuid,
                'status': 'CANCELLED',
                'cancelledAt': order.write_date.isoformat() if order.write_date else ''
            })
        except Exception as e:
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/members/<string:member_id>/orders', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_orders')
    def get_member_orders(self, member_id, **kwargs):
        member = request.env['res.partner'].sudo().search([
            ('x_tr_is_member', '=', True),
            '|', ('x_tr_uuid', '=', member_id), ('id', '=', int(member_id) if member_id.isdigit() else 0)
        ], limit=1)
        if not member:
            return error_response('Member not found', 'MEMBER_NOT_FOUND', 404)
        
        kwargs['memberId'] = member.x_tr_uuid
        return self.list_orders(**kwargs)
    # @http.route(f'{API_PREFIX}/members/<string:member_id>/orders', type='http', auth='public', methods=['GET'], csrf=False)
    # @api_auth('read_orders')
    # def get_member_orders(self, member_id, **kwargs):
    #     member = request.env['res.partner'].sudo().search([
    #         ('x_tr_is_member', '=', True),
    #         '|', ('x_tr_uuid', '=', member_id), ('id', '=', int(member_id) if member_id.isdigit() else 0)
    #     ], limit=1)
    #     if not member:
    #         return error_response('Member not found', 'MEMBER_NOT_FOUND', 404)
        
    #     kwargs['memberId'] = member.x_tr_uuid
    #     return self.list_orders(**kwargs)
    @http.route(f'{API_PREFIX}/members/<string:member_id>/orders', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_orders')
    def get_member_orders(self, member_id, **kwargs):
        # Cherche le membre
        member = request.env['res.partner'].sudo().search([
            ('x_tr_is_member', '=', True),
            '|', ('x_tr_uuid', '=', member_id), ('id', '=', int(member_id) if member_id.isdigit() else 0)
        ], limit=1)

        if not member:
            return error_response('Member not found', 'MEMBER_NOT_FOUND', 404)

        # Cherche les commandes mobiles et POS du membre
        MobileOrder = request.env['mobile.order'].sudo()
        PosOrder = request.env['pos.order'].sudo()

        domain = [('x_tr_member_id', '=', member.id)]
        if kwargs.get('status'):
            domain.append(('x_tr_order_status', '=', kwargs['status']))
        if kwargs.get('mode'):
            domain.append(('x_tr_order_mode', '=', kwargs['mode']))

        # Pagination
        page = int(kwargs.get('page', 0))
        size = min(int(kwargs.get('size', 20)), 100)

        # Cherche dans mobile.order
        mobile_orders = MobileOrder.search(domain, offset=page * size, limit=size, order='create_date desc')
        # Cherche dans pos.order
        pos_orders = PosOrder.search(domain, offset=page * size, limit=size, order='create_date desc')

        # Combine les deux listes et trier par date
        all_orders = list(mobile_orders) + list(pos_orders)
        all_orders.sort(key=lambda o: o.create_date, reverse=True)

        total = len(all_orders)
        # Pagination manuelle après combinaison
        paginated_orders = all_orders[page * size: (page + 1) * size]

        # Retour uniforme
        orders_data = []
        for o in paginated_orders:
            if hasattr(o, 'to_order_api_dict'):
                orders_data.append(o.to_order_api_dict())
            else:
                orders_data.append({
                    'id': getattr(o, 'x_tr_uuid', o.id),
                    'status': getattr(o, 'x_tr_order_status', 'PENDING'),
                    'partner': {
                        'id': o.partner_id.id,
                        'name': o.partner_id.name,
                        'email': o.partner_id.email
                    } if o.partner_id else {}
                })

        return {
            'success': True,
            'total': total,
            'page': page,
            'size': size,
            'orders': orders_data
        }