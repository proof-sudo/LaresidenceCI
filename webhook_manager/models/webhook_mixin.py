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
    _description = "Mixin Final The Residence - CRUD Universel (Membres, Produits, POS)"

    def _get_entity_type(self):
        """Mapping dynamique vers la spécification API"""
        if self._name == 'sale.order':
            if getattr(self, 'x_tr_is_reservation', False): return 'reservation'
            if getattr(self, 'x_tr_is_subscription', False): return 'subscription'
            return 'order'
        
        if self._name == 'product.template':
            if getattr(self, 'x_tr_is_space', False): return 'space'
            if getattr(self, 'x_tr_is_subscription_plan', False): return 'subscription_plan'
            return 'product' # Standard pour le POS
            
        mapping = {
            'res.partner': 'member',
            'pos.order': 'order',
            'pos.category': 'pos_category',
        }
        return mapping.get(self._name, self._name)

    def _get_entity_uuid(self, record):
        """Retourne l'UUID métier du record selon le modèle, fallback sur l'ID Odoo"""
        if self._name == 'product.template':
            return getattr(record, 'x_tr_space_uuid', None) or str(record.id)
        return getattr(record, 'x_tr_uuid', None) or str(record.id)

    def _format_field_value(self, value):
        """Séreilisation sécurisée des types Odoo (Dates, Relations)"""
        if isinstance(value, models.BaseModel):
            return value.ids if len(value) > 1 else (value.id if value else False)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def _prepare_residence_payload(self, event_type, record, include_image=False):
        """Construction du JSON avec champs TR et champs standards (POS/Contact)"""
        entity_type = self._get_entity_type()
        custom_data = {}
        
        # 1. Extraction de tous les champs préfixés x_tr_
        for name, field in record._fields.items():
            if name.startswith('x_tr_'):
                val = getattr(record, name)
                custom_data[name] = self._format_field_value(val)

        # 2. Champs standards critiques (Membres & Catalogue POS)
        standard_fields = [
            'name', 'display_name', 'email', 'phone', 'mobile', 
            'list_price', 'available_in_pos', 'barcode', 'default_code', 'active'
        ]
        for f in standard_fields:
            if f in record._fields:
                custom_data[f] = getattr(record, f)

        # 3. Lien vers l'image Odoo
        if include_image and hasattr(record, 'image_1920') and record.image_1920:
            custom_data['image_url'] = f"/web/image/{record._name}/{record.id}/image_1920"

        # 4. UUIDs des modèles liés (non couverts par x_tr_* automatique)
        if self._name == 'res.partner':
            if hasattr(record, 'x_tr_membership_type_id') and record.x_tr_membership_type_id:
                custom_data['x_tr_membership_type_uuid'] = record.x_tr_membership_type_id.x_uuid

        elif self._name == 'sale.order':
            custom_data['x_tr_member_uuid'] = record.partner_id.x_tr_uuid if record.partner_id else False
            if getattr(record, 'x_tr_is_reservation', False) and record.x_tr_space_id:
                custom_data['x_tr_space_uuid'] = record.x_tr_space_id.x_tr_space_uuid
            elif getattr(record, 'x_tr_is_subscription', False) and record.x_tr_plan_id:
                custom_data['x_tr_plan_uuid'] = record.x_tr_plan_id.x_tr_space_uuid

        elif self._name == 'pos.order':
            member = getattr(record, 'x_tr_member_id', None)
            if member:
                custom_data['x_tr_member_uuid'] = member.x_tr_uuid

        elif self._name == 'pos.category':
            if record.parent_id and hasattr(record.parent_id, 'x_tr_uuid'):
                custom_data['x_tr_parent_uuid'] = record.parent_id.x_tr_uuid

        return {
            "event_type": f"{entity_type}.{event_type}",
            "event_id": f"evt_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            "entity_type": entity_type,
            "entity_id": self._get_entity_uuid(record),
            "data": custom_data
        }

    def _send_to_residence(self, event_type, record, include_image=False):
        """Envoi HTTP avec logging complet en base"""
        configs = self.env['webhook.config'].search([
            ('model_id.model', '=', self._name),
            ('active', '=', True)
        ])
        if not configs: return

        payload = self._prepare_residence_payload(event_type, record, include_image)

        for config in configs:
            try:
                payload_json = json.dumps(payload, indent=2)
                _logger.info(
                    f"[WEBHOOK SEND] url={config.url} | event={payload['event_type']} | ID={record.id}\n"
                    f"[WEBHOOK DATA] {payload_json}"
                )
                
                response = requests.post(
                    config.url, 
                    headers={'Content-Type': 'application/json', 'X-API-Key': config.api_key or ''}, 
                    data=payload_json, 
                    timeout=config.timeout or 5
                )
                
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
                _logger.error(f"[WEBHOOK ERROR] {str(e)}")

    @api.model_create_multi
    def create(self, vals_list):
        """Déclenchement automatique à la création"""
        records = super().create(vals_list)
        for rec in records:
            # Sécurité Membres
            if rec._name == 'res.partner' and not getattr(rec, 'x_tr_is_member', False):
                continue
            
            _logger.info(f"[WEBHOOK CREATE] Nouveau record {rec._name} ID {rec.id}")
            rec._send_to_residence("created", rec, include_image=True)
        return records

    def write(self, vals):
        """Déclenchement sur modification (Nom, Prix, Photo, Statut...)"""
        res = super().write(vals)
        ignored = ['write_date', 'write_uid', '__last_update', 'message_ids', 'activity_ids']
        relevant_fields = [k for k in vals.keys() if k not in ignored]
        
        if relevant_fields:
            for rec in self:
                # Sécurité Membres : n'envoyer que si c'est un membre TR
                if rec._name == 'res.partner' and not getattr(rec, 'x_tr_is_member', False):
                    continue

                event = "updated"
                include_image = any(img in vals for img in ['image_1920', 'image_128', 'image_512'])
                
                # Mapping intelligent des statuts pour les events
                if rec._name == 'sale.order':
                    if getattr(rec, 'x_tr_is_reservation', False):
                        event = rec.x_tr_reservation_status.lower() if rec.x_tr_reservation_status else "updated"
                    elif getattr(rec, 'x_tr_is_subscription', False):
                        event = rec.x_tr_subscription_status.lower() if rec.x_tr_subscription_status else "updated"
                elif rec._name == 'res.partner':
                    event = rec.x_tr_member_status.lower() if rec.x_tr_member_status else "updated"
                elif rec._name == 'pos.order':
                    if getattr(rec, 'x_tr_is_mobile_order', False) and 'x_tr_order_status' in vals:
                        event = rec.x_tr_order_status.lower() if rec.x_tr_order_status else "updated"

                rec._send_to_residence(event, rec, include_image=include_image)
        return res

    def unlink(self):
        """Déclenchement sur suppression (Archivage API externe)"""
        for rec in self:
            if rec._name == 'res.partner' and not getattr(rec, 'x_tr_is_member', False):
                continue
            
            _logger.info(f"[WEBHOOK DELETE] Notification pour {rec._name} ID {rec.id}")
            rec._send_to_residence("deleted", rec)
        return super().unlink()