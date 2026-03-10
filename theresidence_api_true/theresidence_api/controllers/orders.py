# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request
from .main import API_PREFIX, api_auth, success_response, error_response, paginated_response

_logger = logging.getLogger(__name__)


class OrdersController(http.Controller):

    def _get_pos_order(self, order_id):
        """Récupère une pos.order mobile par UUID ou ID."""
        id_int = int(order_id) if order_id.isdigit() else 0
        return request.env['pos.order'].sudo().search([
            ('x_tr_is_mobile_order', '=', True),
            '|', ('x_tr_uuid', '=', order_id), ('id', '=', id_int)
        ], limit=1) or None

    @http.route(f'{API_PREFIX}/orders', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_orders')
    def list_orders(self, **kwargs):
        page = int(kwargs.get('page', 0))
        size = min(int(kwargs.get('size', 20)), 100)

        domain = [('x_tr_is_mobile_order', '=', True)]
        if kwargs.get('memberId'):
            domain.append(('x_tr_member_id.x_tr_uuid', '=', kwargs['memberId']))
        if kwargs.get('mode'):
            domain.append(('x_tr_order_mode', '=', kwargs['mode']))

        total = request.env['pos.order'].sudo().search_count(domain)
        orders = request.env['pos.order'].sudo().search(
            domain, offset=page * size, limit=size, order='create_date desc'
        )
        return paginated_response([o.to_order_api_dict() for o in orders], total, page, size)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_orders')
    def get_order(self, order_id, **kwargs):
        order = self._get_pos_order(order_id)
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
            _logger.error("Error creating order: %s", str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    @api_auth('write_orders')
    def update_order(self, order_id, **kwargs):
        order = self._get_pos_order(order_id)
        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
        if order.state != 'draft':
            return error_response('Only draft orders can be updated', 'INVALID_STATUS_TRANSITION', 400)

        try:
            data = json.loads(request.httprequest.data)

            vals = {}
            if 'deliveryAddress' in data:
                vals['x_tr_delivery_address'] = data['deliveryAddress']
            if 'notes' in data:
                vals['internal_note'] = data['notes']
            if 'mode' in data:
                vals['x_tr_order_mode'] = data['mode']
            if vals:
                order.write(vals)

            if 'items' in data:
                order.lines.unlink()
                for item in data['items']:
                    product = request.env['product.product'].sudo().browse(int(item['menuItemId']))
                    if not product.exists():
                        continue
                    qty = item.get('quantity', 1)
                    price_unit = item.get('unitPrice', product.lst_price)
                    taxes = product.taxes_id.filtered(
                        lambda t: t.company_id.id == request.env.company.id
                    )
                    tax_result = taxes.compute_all(price_unit, quantity=qty, product=product, partner=order.partner_id)
                    request.env['pos.order.line'].sudo().create({
                        'order_id': order.id,
                        'product_id': product.id,
                        'qty': qty,
                        'price_unit': price_unit,
                        'price_subtotal': tax_result['total_excluded'],
                        'price_subtotal_incl': tax_result['total_included'],
                        'tax_ids': [(6, 0, taxes.ids)],
                        'product_uom_id': product.uom_id.id,
                    })
                order._compute_prices()

            return success_response(order.to_order_api_dict())
        except Exception as e:
            _logger.error("Error updating order: %s", str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/orders/<string:order_id>/confirm', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_orders')
    def confirm_order(self, order_id, **kwargs):
        order = self._get_pos_order(order_id)
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
        order = self._get_pos_order(order_id)
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
        order = self._get_pos_order(order_id)
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
        order = self._get_pos_order(order_id)
        if not order:
            return error_response('Order not found', 'ORDER_NOT_FOUND', 404)
        try:
            data = json.loads(request.httprequest.data) if request.httprequest.data else {}
            reason = data.get('reason', '')
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

        page = int(kwargs.get('page', 0))
        size = min(int(kwargs.get('size', 20)), 100)

        domain = [('x_tr_is_mobile_order', '=', True), ('x_tr_member_id', '=', member.id)]
        if kwargs.get('mode'):
            domain.append(('x_tr_order_mode', '=', kwargs['mode']))

        total = request.env['pos.order'].sudo().search_count(domain)
        orders = request.env['pos.order'].sudo().search(
            domain, offset=page * size, limit=size, order='create_date desc'
        )
        return paginated_response([o.to_order_api_dict() for o in orders], total, page, size)
