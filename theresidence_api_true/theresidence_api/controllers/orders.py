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
        
        domain = [('x_tr_is_mobile_order', '=', True)]
        if kwargs.get('memberId'):
            domain.append(('x_tr_member_id.x_tr_uuid', '=', kwargs['memberId']))
        if kwargs.get('status'):
            domain.append(('x_tr_order_status', '=', kwargs['status']))
        if kwargs.get('mode'):
            domain.append(('x_tr_order_mode', '=', kwargs['mode']))
        
        total = request.env['pos.order'].sudo().search_count(domain)
        orders = request.env['pos.order'].sudo().search(domain, offset=page * size, limit=size, order='create_date desc')
        return paginated_response([o.to_order_api_dict() for o in orders], total, page, size)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_orders')
    def get_order(self, order_id, **kwargs):
        order = request.env['pos.order'].sudo().search([
            ('x_tr_is_mobile_order', '=', True),
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        ], limit=1)
        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
        return success_response(order.to_order_api_dict())

    @http.route(f'{API_PREFIX}/orders', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_orders')
    def create_order(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data)
            order = request.env['pos.order'].sudo().create_order_from_api(data)
            return success_response(order.to_order_api_dict(), 201)
        except Exception as e:
            _logger.error(f"Error creating order: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    @api_auth('write_orders')
    def update_order(self, order_id, **kwargs):
        order = request.env['pos.order'].sudo().search([
            ('x_tr_is_mobile_order', '=', True),
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        ], limit=1)
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
        order = request.env['pos.order'].sudo().search([
            ('x_tr_is_mobile_order', '=', True),
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', int(order_id) if order_id.isdigit() else 0)
        ], limit=1)
        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
        
        try:
            order.action_confirm_order()
            return success_response(order.to_order_api_dict())
        except Exception as e:
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

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
