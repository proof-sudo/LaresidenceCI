# -*- coding: utf-8 -*-

import uuid
import json
import hmac
import hashlib
import requests
import logging
from datetime import datetime
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class TheResidenceWebhook(models.Model):
    _name = 'theresidence.webhook'
    _description = 'Webhook The Residence'
    _order = 'name'

    name = fields.Char(string='Nom', required=True)
    url = fields.Char(string='URL', required=True)
    secret = fields.Char(string='Secret (pour signature)')
    is_active = fields.Boolean(string='Actif', default=True)
    event_type_ids = fields.Many2many(
        'theresidence.webhook.event.type',
        string='Types d\'événements'
    )
    event_ids = fields.One2many('theresidence.webhook.event', 'webhook_id', string='Événements')

    def _compute_signature(self, payload):
        self.ensure_one()
        if not self.secret:
            return None
        return hmac.new(
            self.secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def send_event(self, event_type, entity_type, entity_id, data, previous_status=None, new_status=None):
        self.ensure_one()
        payload = {
            'id': str(uuid.uuid4()),
            'eventType': event_type,
            'entityType': entity_type,
            'entityId': entity_id,
            'data': data,
            'previousStatus': previous_status,
            'newStatus': new_status,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        payload_json = json.dumps(payload, default=str)
        headers = {'Content-Type': 'application/json'}
        
        if self.secret:
            headers['X-Webhook-Signature'] = f'sha256={self._compute_signature(payload_json)}'
        
        event = self.env['theresidence.webhook.event'].create({
            'webhook_id': self.id,
            'event_type': event_type,
            'payload': payload_json,
            'status': 'PENDING'
        })
        
        try:
            response = requests.post(self.url, data=payload_json, headers=headers, timeout=30)
            event.write({
                'status': 'SUCCESS' if response.status_code < 400 else 'FAILED',
                'response_code': response.status_code,
                'response_body': response.text[:2000] if response.text else '',
                'sent_at': fields.Datetime.now()
            })
        except Exception as e:
            _logger.error(f"Webhook error: {str(e)}")
            event.write({'status': 'FAILED', 'response_body': str(e)[:2000]})

    @api.model
    def trigger_event(self, event_type, entity_type, entity_id, data, previous_status=None, new_status=None):
        event_type_rec = self.env['theresidence.webhook.event.type'].search([('code', '=', event_type)], limit=1)
        if not event_type_rec:
            return
        webhooks = self.search([('is_active', '=', True), ('event_type_ids', 'in', [event_type_rec.id])])
        for webhook in webhooks:
            try:
                webhook.send_event(event_type, entity_type, entity_id, data, previous_status, new_status)
            except Exception as e:
                _logger.error(f"Error triggering webhook {webhook.id}: {str(e)}")


class TheResidenceWebhookEventType(models.Model):
    _name = 'theresidence.webhook.event.type'
    _description = 'Type d\'événement webhook'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code', required=True, index=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Séquence', default=10)

    _sql_constraints = [('code_unique', 'unique(code)', 'Le code doit être unique.')]


class TheResidenceWebhookEvent(models.Model):
    _name = 'theresidence.webhook.event'
    _description = 'Événement webhook'
    _order = 'create_date desc'

    webhook_id = fields.Many2one('theresidence.webhook', string='Webhook', required=True, ondelete='cascade')
    event_type = fields.Char(string='Type d\'événement')
    payload = fields.Text(string='Payload')
    status = fields.Selection([
        ('PENDING', 'En attente'),
        ('SUCCESS', 'Succès'),
        ('FAILED', 'Échec'),
    ], string='Statut', default='PENDING')
    response_code = fields.Integer(string='Code réponse')
    response_body = fields.Text(string='Réponse')
    sent_at = fields.Datetime(string='Envoyé le')
