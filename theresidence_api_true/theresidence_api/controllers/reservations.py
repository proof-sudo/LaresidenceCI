# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request
from .main import API_PREFIX, api_auth, success_response, error_response, paginated_response

_logger = logging.getLogger(__name__)


class ReservationsController(http.Controller):
    """Controller pour les réservations."""

    @http.route(f'{API_PREFIX}/reservations', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_reservations')
    def list_reservations(self, **kwargs):
        page = int(kwargs.get('page', 0))
        size = min(int(kwargs.get('size', 20)), 100)
        
        domain = [('x_tr_is_reservation', '=', True)]
        if kwargs.get('memberId'):
            domain.append(('partner_id.x_tr_uuid', '=', kwargs['memberId']))
        if kwargs.get('spaceId'):
            domain.append(('x_tr_space_id.x_tr_space_uuid', '=', kwargs['spaceId']))
        if kwargs.get('status'):
            domain.append(('x_tr_reservation_status', '=', kwargs['status']))
        
        total = request.env['sale.order'].sudo().search_count(domain)
        reservations = request.env['sale.order'].sudo().search(domain, offset=page * size, limit=size, order='create_date desc')
        return paginated_response([r.to_reservation_api_dict() for r in reservations], total, page, size)

    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_reservations')
    def get_reservation(self, reservation_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        return success_response(reservation.to_reservation_api_dict())

    @http.route(f'{API_PREFIX}/reservations', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_reservations')
    def create_reservation(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data)

            # ── Pre-check disponibilité AVANT toute création ──────────────
            space_uuid = data.get('spaceId')
            if space_uuid:
                space = request.env['product.template'].sudo().search([
                    ('x_tr_space_uuid', '=', space_uuid),
                    ('x_tr_is_space', '=', True),
                ], limit=1)
                if space and data.get('startTime') and data.get('endTime'):
                    avail = space.check_availability(data['startTime'], data['endTime'])
                    if not avail.get('isAvailable'):
                        return error_response(
                            f"L'espace '{space.name}' n'est pas disponible pour ce créneau.",
                            'SPACE_NOT_AVAILABLE', 409
                        )
            # ─────────────────────────────────────────────────────────────

            reservation = request.env['sale.order'].sudo().create_reservation_from_api(data)
            return success_response(reservation.to_reservation_api_dict(), 201)
        except Exception as e:
            _logger.error(f"Error creating reservation: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    @api_auth('write_reservations')
    def update_reservation(self, reservation_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        if reservation.x_tr_reservation_status != 'PENDING':
            return error_response('Only PENDING reservations can be updated', 'INVALID_STATUS_TRANSITION', 400)
        
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            if 'startTime' in data:
                from datetime import datetime
                vals['x_tr_start_time'] = datetime.fromisoformat(data['startTime'].replace('Z', '+00:00'))
            if 'endTime' in data:
                from datetime import datetime
                vals['x_tr_end_time'] = datetime.fromisoformat(data['endTime'].replace('Z', '+00:00'))
            if 'guestCount' in data:
                vals['x_tr_guest_count'] = data['guestCount']
            if 'notes' in data:
                vals['x_tr_notes'] = data['notes']
            
            if vals:
                reservation.write(vals)
            return success_response(reservation.to_reservation_api_dict())
        except Exception as e:
            _logger.error(f"Error updating reservation: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    @api_auth('write_reservations')
    def delete_reservation(self, reservation_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        
        try:
            reservation.action_cancel_reservation()
            return success_response({'id': reservation.x_tr_uuid, 'status': 'CANCELLED'})
        except Exception as e:
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_reservations')
    def cancel_reservation(self, reservation_id, **kwargs):
        return self.delete_reservation(reservation_id, **kwargs)

    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>/approve', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_reservations')
    def approve_reservation(self, reservation_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        
        try:
            reservation.action_approve_reservation()
            return success_response(reservation.to_reservation_api_dict())
        except Exception as e:
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>/reject', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_reservations')
    def reject_reservation(self, reservation_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        
        try:
            reason = kwargs.get('reason', '')
            reservation.action_reject_reservation(reason)
            return success_response(reservation.to_reservation_api_dict())
        except Exception as e:
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>/check-in', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_reservations')
    def checkin_reservation(self, reservation_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        
        try:
            reservation.action_checkin_reservation()
            return success_response(reservation.to_reservation_api_dict())
        except Exception as e:
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    # === OPTIONS ===
    
    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>/options', type='http', auth='public', methods=['PATCH'], csrf=False)
    @api_auth('write_reservations')
    def add_reservation_option(self, reservation_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        if reservation.x_tr_reservation_status not in ('PENDING', 'APPROVED'):
            return error_response('Options can only be modified for PENDING or APPROVED reservations', 'INVALID_STATUS_TRANSITION', 400)
        
        try:
            data = json.loads(request.httprequest.data)
            opt_id = data.get('optionId')
            quantity = data.get('quantity', 1)
            
            opt_def = request.env['theresidence.reservation.option.def'].sudo().search([
                '|', ('x_uuid', '=', opt_id), ('code', '=', opt_id)
            ], limit=1)
            if not opt_def:
                return error_response('Option not found', 'NOT_FOUND', 404)
            
            # Vérifier si l'option existe déjà
            existing = reservation.x_tr_option_ids.filtered(lambda o: o.option_def_id.id == opt_def.id)
            if existing:
                existing.write({'quantity': quantity})
            else:
                request.env['theresidence.reservation.option'].sudo().create({
                    'reservation_id': reservation.id,
                    'option_def_id': opt_def.id,
                    'name': opt_def.name,
                    'quantity': quantity,
                    'unit_price': opt_def.price,
                })
            
            reservation.invalidate_recordset()
            return success_response({
                'reservationId': reservation.x_tr_uuid,
                'options': [o.to_api_dict() for o in reservation.x_tr_option_ids],
                'totalAmount': reservation.amount_total
            })
        except Exception as e:
            _logger.error(f"Error adding option: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>/options/<string:option_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    @api_auth('write_reservations')
    def remove_reservation_option(self, reservation_id, option_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        if reservation.x_tr_reservation_status not in ('PENDING', 'APPROVED'):
            return error_response('Options can only be modified for PENDING or APPROVED reservations', 'INVALID_STATUS_TRANSITION', 400)
        
        option = reservation.x_tr_option_ids.filtered(
            lambda o: o.option_def_id.x_uuid == option_id or o.option_def_id.code == option_id or str(o.id) == option_id
        )
        if not option:
            return error_response('Option not found in reservation', 'NOT_FOUND', 404)
        
        option.unlink()
        reservation.invalidate_recordset()
        return success_response({
            'reservationId': reservation.x_tr_uuid,
            'removedOptionId': option_id,
            'totalAmount': reservation.amount_total
        })

    # === INVITEES ===
    
    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>/invitees', type='http', auth='public', methods=['PATCH'], csrf=False)
    @api_auth('write_reservations')
    def add_reservation_invitee(self, reservation_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        if reservation.x_tr_reservation_status not in ('PENDING', 'APPROVED'):
            return error_response('Invitees can only be modified for PENDING or APPROVED reservations', 'INVALID_STATUS_TRANSITION', 400)
        
        try:
            data = json.loads(request.httprequest.data)
            invitee = request.env['theresidence.reservation.invitee'].sudo().create({
                'reservation_id': reservation.id,
                'name': data.get('fullName') or data.get('name', ''),
                'email': data.get('email', ''),
                'phone': data.get('phone', ''),
            })
            
            reservation.invalidate_recordset()
            return success_response({
                'reservationId': reservation.x_tr_uuid,
                'invitee': invitee.to_api_dict(),
                'invitees': [i.to_api_dict() for i in reservation.x_tr_invitee_ids]
            })
        except Exception as e:
            _logger.error(f"Error adding invitee: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/reservations/<string:reservation_id>/invitees/<string:invitee_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    @api_auth('write_reservations')
    def remove_reservation_invitee(self, reservation_id, invitee_id, **kwargs):
        reservation = request.env['sale.order'].sudo().search([
            ('x_tr_is_reservation', '=', True),
            '|', ('x_tr_uuid', '=', reservation_id), ('id', '=', int(reservation_id) if reservation_id.isdigit() else 0)
        ], limit=1)
        if not reservation:
            return error_response('Reservation not found', 'RESERVATION_NOT_FOUND', 404)
        if reservation.x_tr_reservation_status not in ('PENDING', 'APPROVED'):
            return error_response('Invitees can only be modified for PENDING or APPROVED reservations', 'INVALID_STATUS_TRANSITION', 400)
        
        invitee = reservation.x_tr_invitee_ids.filtered(lambda i: i.x_uuid == invitee_id or str(i.id) == invitee_id)
        if not invitee:
            return error_response('Invitee not found in reservation', 'NOT_FOUND', 404)
        
        invitee.unlink()
        reservation.invalidate_recordset()
        return success_response({
            'reservationId': reservation.x_tr_uuid,
            'removedInviteeId': invitee_id,
            'invitees': [i.to_api_dict() for i in reservation.x_tr_invitee_ids]
        })

    # === MEMBER RESERVATIONS ===
    
    @http.route(f'{API_PREFIX}/members/<string:member_id>/reservations', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_reservations')
    def get_member_reservations(self, member_id, **kwargs):
        member = request.env['res.partner'].sudo().search([
            ('x_tr_is_member', '=', True),
            '|', ('x_tr_uuid', '=', member_id), ('id', '=', int(member_id) if member_id.isdigit() else 0)
        ], limit=1)
        if not member:
            return error_response('Member not found', 'MEMBER_NOT_FOUND', 404)
        
        kwargs['memberId'] = member.x_tr_uuid
        return self.list_reservations(**kwargs)
