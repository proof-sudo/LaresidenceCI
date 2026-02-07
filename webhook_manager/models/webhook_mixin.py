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
    _description = "Mixin The Residence - Intégration Complète"

    def _get_entity_type(self):
        """Mapping vers les entités de la spécification"""
        if self._name == 'sale.order':
            if getattr(self, 'x_tr_is_reservation', False): return 'reservation'
            if getattr(self, 'x_tr_is_subscription', False): return 'subscription'
            return 'order'
        
        mapping = {
            'res.partner': 'member',
            'pos.order': 'order',
            'pos.category': 'pos_category',
            'product.template': 'product'
        }
        return mapping.get(self._name, self._name)

    def _prepare_residence_payload(self, event_type, record, include_image=False):
        """Construction du payload JSON"""
        entity_type = self._get_entity_type()
        
        # Extraction dynamique des champs x_tr_*
        custom_data = {}
        for name, field in record._fields.items():
            if name.startswith('x_tr_'):
                val = getattr(record, name)
                if field.type == 'many2one':
                    custom_data[name] = val.id if val else False
                elif field.type in ['datetime', 'date']:
                    custom_data[name] = val.isoformat() if val else False
                else:
                    custom_data[name] = val

        # Inclusion de l'URL de l'image seulement si nécessaire
        if include_image or self._context.get('force_image'):
            if hasattr(record, 'image_1920') and record.image_1920:
                custom_data['image_url'] = f"/web/image/{record._name}/{record.id}/image_1920"

        payload = {
            "event_type": f"{entity_type}.{event_type}",
            "event_id": f"evt_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}", # Idempotency
            "timestamp": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'), # ISO 8601
            "entity_type": entity_type,
            "entity_id": str(record.id), # Odoo ID
            "data": custom_data
        }
        return payload

    def _send_to_residence(self, event_type, record, include_image=False):
        """Envoi HTTP avec logs de débogage exhaustifs"""
        configs = self.env['webhook.config'].search([
            ('model_id.model', '=', self._name),
            ('active', '=', True)
        ])

        if not configs:
            _logger.debug(f"WEBHOOK SKIP: Aucune config active pour {self._name}")
            return

        payload = self._prepare_residence_payload(event_type, record, include_image)

        for config in configs:
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': config.api_key or '' # Header requis
            }
            
            _logger.info(f"--- START WEBHOOK DEBUG ---")
            _logger.info(f"URL: {config.url}")
            _logger.info(f"Headers: {headers}")
            _logger.info(f"Payload: {json.dumps(payload, indent=2)}")

            try:
                response = requests.post(
                    config.url, 
                    headers=headers, 
                    json=payload, 
                    timeout=config.timeout or 5
                )
                
                # Vérification du code 202 selon la spec
                if response.status_code == 202:
                    _logger.info(f"WEBHOOK SUCCESS: 202 Accepted")
                    _logger.debug(f"API Response: {response.text}")
                else:
                    _logger.error(f"WEBHOOK FAILED ({response.status_code})")
                    _logger.error(f"API Error Body: {response.text}")
                    
            except Exception as e:
                _logger.error(f"WEBHOOK FATAL ERROR: {str(e)}")
            _logger.info(f"--- END WEBHOOK DEBUG ---")

    def write(self, vals):
        """Détection des changements de statut et d'images"""
        res = super().write(vals)
        
        # Liste des champs déclencheurs
        trigger_fields = [k for k in vals.keys() if k.startswith('x_tr_') or k in ['state', 'image_1920']]
        
        if not trigger_fields:
            return res

        for rec in self:
            entity = self._get_entity_type()
            event = "updated"
            include_image = 'image_1920' in vals

            # Logique de statut spécifique (Order & Reservation)
            if rec._name == 'sale.order':
                if getattr(rec, 'x_tr_is_reservation', False):
                    # reservation.approved, reservation.cancelled, etc.
                    status = rec.x_tr_reservation_status.lower() if rec.x_tr_reservation_status else "updated"
                    event = status
                elif getattr(rec, 'x_tr_is_subscription', False):
                    status = rec.x_tr_subscription_status.lower() if rec.x_tr_subscription_status else "updated"
                    event = status
                else:
                    # Mapping standard Sale Order
                    mapping = {'sale': 'confirmed', 'done': 'completed', 'cancel': 'cancelled'}
                    event = mapping.get(rec.state, "updated")

            _logger.debug(f"DEBUG: Triggered by fields {trigger_fields} on {rec._name}")
            rec._send_to_residence(event, rec, include_image=include_image)
            
        return res