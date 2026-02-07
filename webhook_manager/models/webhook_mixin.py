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
        """Mapping conforme à la spécification The Residence"""
        mapping = {
            'sale.order': 'order',
            'res.partner': 'member',
            'sale.subscription': 'subscription',
        }
        # Retourne le mapping ou le nom technique si non listé (ex: pos.category)
        return mapping.get(self._name, self._name)

    def _prepare_residence_payload(self, event_type, record):
        """Formatage du JSON selon ODOO_WEBHOOK_SPECIFICATION.md"""
        entity_type = self._get_entity_type()
        
        payload = {
            "event_type": f"{entity_type}.{event_type}",
            "event_id": f"evt_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}", # Idempotence
            "timestamp": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'), # Format ISO 8601
            "entity_type": entity_type,
            "entity_id": str(record.id), # Doit correspondre à odoo_id
            "data": {
                "display_name": record.display_name,
                "state": getattr(record, 'state', False),
                "context_user": self.env.user.name
            }
        }
        return payload

    def _send_to_residence(self, event_type, record):
        """Envoi HTTP avec capture des logs de retour pour débogage"""
        configs = self.env['webhook.config'].search([
            ('model_id.model', '=', self._name),
            ('active', '=', True)
        ])

        if not configs:
            _logger.info(f"WEBHOOK: Pas de configuration active pour {self._name}")
            return

        payload = self._prepare_residence_payload(event_type, record)

        for config in configs:
            # Préparation des headers selon la spec
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': config.api_key or ''
            }
            
            _logger.info(f"--- WEBHOOK SENDING ({self._name}) ---")
            _logger.info(f"URL: {config.url}")
            _logger.info(f"Payload: {json.dumps(payload)}")

            try:
                # L'API est censée répondre en moins de 100ms
                response = requests.post(
                    config.url, 
                    headers=headers, 
                    json=payload, 
                    timeout=config.timeout or 5
                )
                
                # Log précis du retour de l'API
                if response.status_code == 202:
                    _logger.info(f"WEBHOOK SUCCESS: 202 Accepted - Event {payload['event_id']}")
                else:
                    _logger.error(f"WEBHOOK FAILED: {response.status_code}")
                    _logger.error(f"API Response Content: {response.text}") # Pour voir les erreurs 401/400
                    
            except Exception as e:
                _logger.error(f"WEBHOOK CONNECTION ERROR: {str(e)}")
            _logger.info("--- END WEBHOOK ---")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            event = "updated" if record._name == 'res.partner' else "created"
            record._send_to_residence(event, record)
        return records

    def write(self, vals):
        states_before = {rec.id: getattr(rec, 'state', None) for rec in self}
        res = super().write(vals)
        
        for rec in self:
            event = None
            new_state = getattr(rec, 'state', None)
            old_state = states_before.get(rec.id)

            # Mapping des statuts selon la spécification
            if rec._name == 'sale.order' and old_state != new_state:
                mapping = {'sale': 'confirmed', 'done': 'completed', 'cancel': 'cancelled'}
                event = mapping.get(new_state)
            elif rec._name == 'res.partner':
                event = "updated"
            elif any(f in vals for f in ['name', 'display_name', 'email']):
                event = "updated"

            if event:
                rec._send_to_residence(event, rec)
        return res