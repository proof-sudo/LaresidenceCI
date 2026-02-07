# -*- coding: utf-8 -*-
from odoo import models, api, fields
import requests
import json
import logging
import uuid
from datetime import datetime

_logger = logging.getLogger(__name__)

class WebhookMixin(models.AbstractModel):
    _name = "webhook.mixin"
    _description = "Mixin The Residence API - CRUD & Métier"

    def _get_entity_type(self):
        mapping = {
            'sale.order': 'order',
            'res.partner': 'member',
            'sale.subscription': 'subscription',
        }
        return mapping.get(self._name, self._name)

    def _prepare_residence_payload(self, event_type, record):
        """Format conforme à ODOO_WEBHOOK_SPECIFICATION.md"""
        entity_type = self._get_entity_type()
        return {
            "event_type": f"{entity_type}.{event_type}",
            "event_id": f"evt_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now().isoformat() + "Z",
            "entity_type": entity_type,
            "entity_id": str(record.id),
            "data": {
                "display_name": record.display_name,
                "state": getattr(record, 'state', False)
            }
        }

    def _send_to_residence(self, event_type, record):
        """Envoi avec X-API-Key"""
        configs = self.env['webhook.config'].search([
            ('model_id.model', '=', self._name),
            ('active', '=', True)
        ])
        
        payload = self._prepare_residence_payload(event_type, record)

        for config in configs:
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': config.api_key or ''
            }
            try:
                # Utilisation du timeout configuré
                requests.post(config.url, headers=headers, json=payload, timeout=config.timeout)
            except Exception as e:
                _logger.error(f"Webhook Error: {e}")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            # Déclenche un événement de création/mise à jour
            record._send_to_residence("updated" if record._name == 'res.partner' else "created", record)
        return records

    def write(self, vals):
        """Gère les mises à jour et changements de statuts"""
        states_before = {rec.id: getattr(rec, 'state', None) for rec in self}
        res = super().write(vals)
        
        for rec in self:
            event = None
            new_state = getattr(rec, 'state', None)
            old_state = states_before.get(rec.id)

            # Logique de mapping des statuts
            if rec._name == 'sale.order' and old_state != new_state:
                mapping = {'sale': 'confirmed', 'done': 'completed', 'cancel': 'cancelled'}
                event = mapping.get(new_state)
            elif rec._name == 'res.partner':
                event = "updated"

            if event:
                rec._send_to_residence(event, rec)
            elif any(f in vals for f in ['name', 'email', 'phone']):
                # Mise à jour d'info générale
                rec._send_to_residence("updated", rec)
        return res