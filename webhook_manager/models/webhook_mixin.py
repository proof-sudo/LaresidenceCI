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
    _description = "Mixin The Residence - Gestion CRUD & Membres"

    def _get_entity_type(self):
        """Mapping des entités selon la spécification TR"""
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
        """Transforme les objets Odoo complexes en JSON sérialisable"""
        if isinstance(value, models.BaseModel):
            # Pour les relations, on renvoie les IDs
            return value.ids if len(value) > 1 else (value.id if value else False)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def _prepare_residence_payload(self, event_type, record, include_image=False):
        """Construction du payload avec champs TR et champs standards essentiels"""
        entity_type = self._get_entity_type()
        custom_data = {}
        
        # 1. Extraction automatique de tous les champs x_tr_*
        for name, field in record._fields.items():
            if name.startswith('x_tr_'):
                val = getattr(record, name)
                custom_data[name] = self._format_field_value(val)

        # 2. Ajout des champs standards critiques (Nom, Contact, etc.)
        standard_fields = ['name', 'display_name', 'email', 'phone', 'mobile']
        for field_name in standard_fields:
            if field_name in record._fields:
                custom_data[field_name] = getattr(record, field_name)

        # 3. Gestion de l'URL de l'image
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
        """Envoi HTTP et archivage des logs"""
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
                payload_json = json.dumps(payload, indent=2)
                _logger.info(f"[WEBHOOK SEND] {payload['event_type']} ID {record.id}")

                response = requests.post(
                    config.url, 
                    headers=headers, 
                    data=payload_json, 
                    timeout=config.timeout or 5
                )
                
                # Création du log en base de données
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
                _logger.error(f"[WEBHOOK FATAL] Erreur sur {self._name}: {str(e)}")

    def write(self, vals):
        """Déclenchement sur modification (Nom, Photo, Email, etc.)"""
        res = super().write(vals)
        
        # Ignorer les mises à jour purement techniques
        ignored = ['write_date', 'write_uid', '__last_update', 'message_ids', 'activity_ids']
        relevant_fields = [k for k in vals.keys() if k not in ignored]
        
        if relevant_fields:
            for rec in self:
                # FILTRE : Si res.partner, envoyer UNIQUEMENT si c'est un membre TR
                if rec._name == 'res.partner' and not getattr(rec, 'x_tr_is_member', False):
                    continue

                event = "updated"
                # Déclenchement de l'image si un champ image est dans vals
                include_image = any(img in vals for img in ['image_1920', 'image_128', 'image_512'])
                
                # Mapping des statuts TR
                if rec._name == 'sale.order':
                    if getattr(rec, 'x_tr_is_reservation', False):
                        event = rec.x_tr_reservation_status.lower() if rec.x_tr_reservation_status else "updated"
                    elif getattr(rec, 'x_tr_is_subscription', False):
                        event = rec.x_tr_subscription_status.lower() if rec.x_tr_subscription_status else "updated"
                elif rec._name == 'res.partner':
                    event = rec.x_tr_member_status.lower() if rec.x_tr_member_status else "updated"
                
                _logger.info(f"[WEBHOOK TRIGGER] {rec._name} modif sur: {relevant_fields}")
                rec._send_to_residence(event, rec, include_image=include_image)
        
        return res

    def unlink(self):
        """Déclenchement sur suppression"""
        for rec in self:
            # On ne notifie la suppression que pour les membres TR
            if rec._name == 'res.partner' and not getattr(rec, 'x_tr_is_member', False):
                continue
            
            _logger.info(f"[WEBHOOK DELETE] Notification pour {rec._name} ID {rec.id}")
            try:
                rec._send_to_residence("deleted", rec)
            except Exception as e:
                _logger.error(f"Erreur lors de la notification de suppression: {e}")
                
        return super().unlink()