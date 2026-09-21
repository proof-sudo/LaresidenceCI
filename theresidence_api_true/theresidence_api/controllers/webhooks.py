# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request
from .main import API_PREFIX, api_auth, success_response, error_response, paginated_response

_logger = logging.getLogger(__name__)


class WebhooksController(http.Controller):
    """Controller pour la gestion des webhooks."""

    @http.route(f'{API_PREFIX}/webhooks', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('manage_webhooks')
    def list_webhooks(self, **kwargs):
        webhooks = request.env['theresidence.webhook'].sudo().search([])
        data = []
        for wh in webhooks:
            data.append({
                'id': wh.id,
                'name': wh.name,
                'url': wh.url,
                'isActive': wh.is_active,
                'eventTypes': [et.code for et in wh.event_type_ids]
            })
        return success_response(data)

    @http.route(f'{API_PREFIX}/webhooks/<int:webhook_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('manage_webhooks')
    def get_webhook(self, webhook_id, **kwargs):
        webhook = request.env['theresidence.webhook'].sudo().browse(webhook_id)
        if not webhook.exists():
            return error_response('Webhook not found', 'NOT_FOUND', 404)
        return success_response({
            'id': webhook.id,
            'name': webhook.name,
            'url': webhook.url,
            'isActive': webhook.is_active,
            'eventTypes': [et.code for et in webhook.event_type_ids]
        })

    @http.route(f'{API_PREFIX}/webhooks', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('manage_webhooks')
    def create_webhook(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data)
            
            event_type_ids = []
            if data.get('eventTypes'):
                event_types = request.env['theresidence.webhook.event.type'].sudo().search([
                    ('code', 'in', data['eventTypes'])
                ])
                event_type_ids = [(6, 0, event_types.ids)]
            
            webhook = request.env['theresidence.webhook'].sudo().create({
                'name': data.get('name', 'Webhook'),
                'url': data['url'],
                'secret': data.get('secret', ''),
                'is_active': data.get('isActive', True),
                'event_type_ids': event_type_ids[0] if event_type_ids else False,
            })
            
            return success_response({
                'id': webhook.id,
                'name': webhook.name,
                'url': webhook.url,
                'isActive': webhook.is_active,
                'eventTypes': [et.code for et in webhook.event_type_ids]
            }, 201)
        except Exception as e:
            _logger.error(f"Error creating webhook: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/webhooks/<int:webhook_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    @api_auth('manage_webhooks')
    def update_webhook(self, webhook_id, **kwargs):
        webhook = request.env['theresidence.webhook'].sudo().browse(webhook_id)
        if not webhook.exists():
            return error_response('Webhook not found', 'NOT_FOUND', 404)
        
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            
            if 'name' in data:
                vals['name'] = data['name']
            if 'url' in data:
                vals['url'] = data['url']
            if 'secret' in data:
                vals['secret'] = data['secret']
            if 'isActive' in data:
                vals['is_active'] = data['isActive']
            if 'eventTypes' in data:
                event_types = request.env['theresidence.webhook.event.type'].sudo().search([
                    ('code', 'in', data['eventTypes'])
                ])
                vals['event_type_ids'] = [(6, 0, event_types.ids)]
            
            if vals:
                webhook.write(vals)
            
            return success_response({
                'id': webhook.id,
                'name': webhook.name,
                'url': webhook.url,
                'isActive': webhook.is_active,
                'eventTypes': [et.code for et in webhook.event_type_ids]
            })
        except Exception as e:
            _logger.error(f"Error updating webhook: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/webhooks/<int:webhook_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    @api_auth('manage_webhooks')
    def delete_webhook(self, webhook_id, **kwargs):
        webhook = request.env['theresidence.webhook'].sudo().browse(webhook_id)
        if not webhook.exists():
            return error_response('Webhook not found', 'NOT_FOUND', 404)
        
        webhook.unlink()
        return success_response({'deleted': True})

    @http.route(f'{API_PREFIX}/webhooks/<int:webhook_id>/events', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('manage_webhooks')
    def list_webhook_events(self, webhook_id, **kwargs):
        webhook = request.env['theresidence.webhook'].sudo().browse(webhook_id)
        if not webhook.exists():
            return error_response('Webhook not found', 'NOT_FOUND', 404)
        
        page = int(kwargs.get('page', 0))
        size = min(int(kwargs.get('size', 20)), 100)
        
        events = webhook.event_ids.sorted(key=lambda e: e.create_date, reverse=True)
        total = len(events)
        events = events[page * size:(page + 1) * size]
        
        data = [{
            'id': e.id,
            'eventType': e.event_type,
            'status': e.status,
            'responseCode': e.response_code,
            'sentAt': e.sent_at.isoformat() if e.sent_at else '',
            'createdAt': e.create_date.isoformat() if e.create_date else ''
        } for e in events]
        
        return paginated_response(data, total, page, size)

    @http.route(f'{API_PREFIX}/webhooks/<int:webhook_id>/test', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('manage_webhooks')
    def test_webhook(self, webhook_id, **kwargs):
        webhook = request.env['theresidence.webhook'].sudo().browse(webhook_id)
        if not webhook.exists():
            return error_response('Webhook not found', 'NOT_FOUND', 404)
        
        try:
            webhook.send_event(
                'TEST_EVENT',
                'test',
                'test-123',
                {'message': 'This is a test webhook event'},
                None,
                None
            )
            return success_response({'message': 'Test event sent'})
        except Exception as e:
            return error_response(str(e), 'WEBHOOK_ERROR', 500)
