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
            # 'sale.subscription': 'subscription',
            'pos.category': 'pos_category',
        }
        return mapping.get(self._name, self._name)

    def _prepare_residence_payload(self, event_type, record):
        """Format conforme à ODOO_WEBHOOK_SPECIFICATION.md"""
        entity_type = self._get_entity_type()
        payload = {
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
        _logger.debug(f"WEBHOOK PAYLOAD PREPARED: {json.dumps(payload)}")
        return payload

    def _send_to_residence(self, event_type, record):
        """Envoi avec X-API-Key et logs de débogage"""
        _logger.info(f"WEBHOOK TRIGGERED: Event '{event_type}' on {record._name}(ID: {record.id})")

        configs = self.env['webhook.config'].search([
            ('model_id.model', '=', self._name),
            ('active', '=', True)
        ])

        if not configs:
            _logger.warning(f"WEBHOOK ABORTED: No active configuration found for model '{self._name}'")
            return

        payload = self._prepare_residence_payload(event_type, record)

        for config in configs:
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': config.api_key or ''
            }
            _logger.info(f"WEBHOOK SENDING: To {config.url} (Timeout: {config.timeout}s)")
            
            try:
                response = requests.post(
                    config.url, 
                    headers=headers, 
                    json=payload, 
                    timeout=config.timeout
                )
                
                # Log du résultat
                if response.status_code in [200, 201, 202]:
                    _logger.info(f"WEBHOOK SUCCESS: Server returned {response.status_code}")
                else:
                    _logger.error(f"WEBHOOK FAILED: Server returned {response.status_code} - Response: {response.text}")
                    
            except requests.exceptions.Timeout:
                _logger.error(f"WEBHOOK TIMEOUT: Destination {config.url} did not respond within {config.timeout}s")
            except Exception as e:
                _logger.error(f"WEBHOOK CONNECTION ERROR: {str(e)}")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            _logger.debug(f"WEBHOOK DEBUG: Create detected on {record._name}")
            event = "updated" if record._name == 'res.partner' else "created"
            record._send_to_residence(event, record)
        return records

    def write(self, vals):
        """Gère les mises à jour et changements de statuts avec logs"""
        _logger.debug(f"WEBHOOK DEBUG: Write detected on {self._name} with vals: {vals}")
        
        states_before = {rec.id: getattr(rec, 'state', None) for rec in self}
        res = super().write(vals)
        
        for rec in self:
            event = None
            new_state = getattr(rec, 'state', None)
            old_state = states_before.get(rec.id)

            # Logique métier spécifique
            if rec._name == 'sale.order' and old_state != new_state:
                mapping = {'sale': 'confirmed', 'done': 'completed', 'cancel': 'cancelled'}
                event = mapping.get(new_state)
                _logger.debug(f"WEBHOOK DEBUG: SaleOrder state change {old_state} -> {new_state} (Event: {event})")
                
            elif rec._name == 'res.partner':
                event = "updated"
                
            elif rec._name == 'pos.category':
                event = "updated"
                _logger.debug("WEBHOOK DEBUG: PosCategory update detected")

            # Déclenchement si événement trouvé ou si champs critiques modifiés
            if event:
                rec._send_to_residence(event, rec)
            elif any(f in vals for f in ['name', 'email', 'phone', 'display_name']):
                _logger.debug(f"WEBHOOK DEBUG: Critical field change in {vals.keys()}")
                rec._send_to_residence("updated", rec)
            else:
                _logger.debug("WEBHOOK DEBUG: No relevant change detected for webhook")
                
        return res