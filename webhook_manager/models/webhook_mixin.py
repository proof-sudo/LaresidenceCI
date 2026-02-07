# -*- coding: utf-8 -*-
from odoo import models, api, fields
import requests
import json
import logging
import uuid
from datetime import datetime, date

_logger = logging.getLogger(__name__)

class WebhookMixin(models.AbstractModel):
    _name = "webhook.mixin"
    _description = "Mixin The Residence - Gestion Robuste JSON"

    def _get_entity_type(self):
        """Mapping conforme à ODOO_WEBHOOK_SPECIFICATION.md"""
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

    def _format_field_value(self, value):
        """Transforme les objets Odoo complexes en formats JSON sérialisables"""
        if isinstance(value, models.BaseModel):
            # Pour les relations (Many2one, One2many, Many2many), on retourne les IDs
            return value.ids if len(value) > 1 else (value.id if value else False)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def _prepare_residence_payload(self, event_type, record, include_image=False):
        """Construction du payload avec formatage des données"""
        entity_type = self._get_entity_type()
        
        custom_data = {}
        for name, field in record._fields.items():
            if name.startswith('x_tr_'):
                # Correction cruciale : formater la valeur avant l'insertion
                val = getattr(record, name)
                custom_data[name] = self._format_field_value(val)

        if include_image and hasattr(record, 'image_1920') and record.image_1920:
            custom_data['image_url'] = f"/web/image/{record._name}/{record.id}/image_1920"

        return {
            "event_type": f"{entity_type}.{event_type}",
            "event_id": f"evt_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "entity_type": entity_type,
            "entity_id": str(record.id),
            "data": custom_data
        }

    def _send_to_residence(self, event_type, record, include_image=False):
        """Envoi HTTP avec capture des logs en base de données"""
        configs = self.env['webhook.config'].search([
            ('model_id.model', '=', self._name),
            ('active', '=', True)
        ])

        if not configs:
            return

        payload = self._prepare_residence_payload(event_type, record, include_image)

        for config in configs:
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': config.api_key or ''
            }
            
            try:
                # Debug Logger avant envoi
                payload_json = json.dumps(payload, indent=2)
                _logger.info(f"WEBHOOK SENDING {payload['event_id']}")

                response = requests.post(
                    config.url, 
                    headers=headers, 
                    data=payload_json, 
                    timeout=config.timeout or 5
                )
                
                # Archivage dans webhook.log (Nécessite les accès CSV)
                self.env['webhook.log'].create({
                    'name': payload['event_id'],
                    'model_name': self._name,
                    'res_id': record.id,
                    'status_code': str(response.status_code),
                    'request_payload': payload_json,
                    'response_body': response.text,
                    'success': response.status_code == 202
                })

            except Exception as e:
                _logger.error(f"WEBHOOK FATAL: {str(e)}")

    def write(self, vals):
        res = super().write(vals)
        # On déclenche si un champ custom, le statut ou l'image change
        trigger_fields = [k for k in vals.keys() if k.startswith('x_tr_') or k in ['state', 'image_1920']]
        
        if trigger_fields:
            for rec in self:
                event = "updated"
                include_image = 'image_1920' in vals
                
                # Logique spécifique aux statuts The Residence
                if rec._name == 'sale.order':
                    if getattr(rec, 'x_tr_is_reservation', False):
                        event = rec.x_tr_reservation_status.lower() if rec.x_tr_reservation_status else "updated"
                    elif getattr(rec, 'x_tr_is_subscription', False):
                        event = rec.x_tr_subscription_status.lower() if rec.x_tr_subscription_status else "updated"
                
                rec._send_to_residence(event, rec, include_image=include_image)
        return res