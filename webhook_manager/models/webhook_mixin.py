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
    _description = "Mixin The Residence - Déclenchement Global & Debug"

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
            # Retourne l'ID ou la liste d'IDs pour éviter l'erreur de sérialisation
            return value.ids if len(value) > 1 else (value.id if value else False)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def _prepare_residence_payload(self, event_type, record, include_image=False):
        """Construction du payload avec tous les champs x_tr_ et les champs de base"""
        entity_type = self._get_entity_type()
        
        # On inclut systématiquement les champs custom x_tr_
        custom_data = {}
        for name, field in record._fields.items():
            if name.startswith('x_tr_'):
                val = getattr(record, name)
                custom_data[name] = self._format_field_value(val)

        # Ajout des champs de base essentiels (Name, etc.) pour le suivi
        if 'name' in record._fields:
            custom_data['display_name'] = record.name

        if include_image and hasattr(record, 'image_1920') and record.image_1920:
            custom_data['image_url'] = f"/web/image/{record._name}/{record.id}/image_1920"

        payload = {
            "event_type": f"{entity_type}.{event_type}",
            "event_id": f"evt_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "entity_type": entity_type,
            "entity_id": str(record.id),
            "data": custom_data
        }
        _logger.debug(f"[WEBHOOK DEBUG] Payload préparé pour {record._name} ID {record.id}")
        return payload

    def _send_to_residence(self, event_type, record, include_image=False):
        """Envoi HTTP avec traçabilité complète"""
        configs = self.env['webhook.config'].search([
            ('model_id.model', '=', self._name),
            ('active', '=', True)
        ])

        if not configs:
            _logger.info(f"[WEBHOOK SKIP] Aucune configuration active pour le modèle {self._name}")
            return

        payload = self._prepare_residence_payload(event_type, record, include_image)

        for config in configs:
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': config.api_key or ''
            }
            
            try:
                payload_json = json.dumps(payload, indent=2)
                _logger.info(f"[WEBHOOK ATTEMPT] Envoi vers {config.url} | Event: {payload['event_type']}")

                response = requests.post(
                    config.url, 
                    headers=headers, 
                    data=payload_json, 
                    timeout=config.timeout or 5
                )
                
                # Logging du résultat
                log_status = "SUCCESS" if response.status_code == 202 else "FAILED"
                _logger.info(f"[WEBHOOK {log_status}] Status Code: {response.status_code}")

                # Archivage en base
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
                _logger.error(f"[WEBHOOK FATAL ERROR] Erreur lors de l'envoi : {str(e)}")

    def write(self, vals):
        """Déclenchement sur TOUTE modification, sauf champs techniques exclus"""
        res = super().write(vals)
        
        # Liste des champs techniques à ignorer pour ne pas surcharger le serveur
        ignored_fields = ['write_date', 'write_uid', '__last_update', 'message_ids', 'activity_ids']
        
        # On vérifie s'il y a au moins un champ modifié qui n'est pas dans la liste ignorée
        relevant_fields = [k for k in vals.keys() if k not in ignored_fields]
        
        if relevant_fields:
            _logger.info(f"[WEBHOOK TRIGGER] Détection de modification sur {self._name} | Champs: {relevant_fields}")
            for rec in self:
                event = "updated"
                include_image = 'image_1920' in vals
                
                # Logique spécifique aux statuts pour Sale Order
                if rec._name == 'sale.order':
                    if getattr(rec, 'x_tr_is_reservation', False):
                        event = rec.x_tr_reservation_status.lower() if rec.x_tr_reservation_status else "updated"
                    elif getattr(rec, 'x_tr_is_subscription', False):
                        event = rec.x_tr_subscription_status.lower() if rec.x_tr_subscription_status else "updated"
                
                # Envoi
                rec._send_to_residence(event, rec, include_image=include_image)
        else:
            _logger.debug(f"[WEBHOOK DEBUG] Modification ignorée sur {self._name} (uniquement champs techniques)")
            
        return res