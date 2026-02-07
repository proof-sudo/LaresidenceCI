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
    _description = "Mixin pour The Residence API - Gestion des événements métiers"

    def _get_entity_type(self):
        """Mappe le nom technique Odoo vers le type d'entité de la SPEC"""
        mapping = {
            'sale.order': 'order',
            'res.partner': 'member',
            'sale.subscription': 'subscription',
            'hotel.reservation': 'reservation',
            'restaurant.reservation': 'reservation'
        }
        return mapping.get(self._name, self._name)

    def _prepare_residence_payload(self, event_type, record):
        """Prépare le payload JSON restreint selon la SPEC"""
        entity_type = self._get_entity_type()
        
        # Génération d'un event_id unique pour l'idempotence côté API
        event_unique_id = f"evt_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
        
        return {
            "event_type": f"{entity_type}.{event_type}",
            "event_id": event_unique_id,
            "timestamp": datetime.now().isoformat() + "Z", # Format ISO 8601 UTC
            "entity_type": entity_type,
            "entity_id": str(record.id), # L'ID Odoo doit correspondre à odoo_id en face
            "data": {
                "display_name": record.display_name,
                "state": getattr(record, 'state', False),
                "last_update": record.write_date.isoformat() if hasattr(record, 'write_date') else None
            }
        }

    def _send_to_residence(self, event_type, record):
        """Recherche la configuration et envoie le webhook"""
        configs = self.env['webhook.config'].search([
            ('model_id.model', '=', self._name),
            ('active', '=', True)
        ])

        if not configs:
            return

        payload = self._prepare_residence_payload(event_type, record)

        for config in configs:
            # Header X-API-Key requis par la spécification
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': config.api_key or ''
            }
            
            try:
                _logger.info(f"Envoi Webhook {payload['event_type']} (ID: {payload['event_id']}) vers {config.url}")
                response = requests.post(
                    config.url,
                    headers=headers,
                    json=payload,
                    timeout=config.timeout
                )
                
                # Succès si 202 Accepted selon la SPEC
                if response.status_code == 202:
                    _logger.info(f"Webhook {payload['event_id']} accepté avec succès.")
                else:
                    _logger.warning(f"Réponse API inattendue ({response.status_code}): {response.text}")
                    
            except Exception as e:
                _logger.error(f"Échec de connexion au webhook à {config.url}: {str(e)}")

    @api.model_create_multi
    def create(self, vals_list):
        """Déclenchement lors de la création d'un enregistrement"""
        records = super(WebhookMixin, self).create(vals_list)
        for record in records:
            # On considère la création comme un événement 'updated' ou spécifique
            event_type = "created"
            if record._name == 'res.partner':
                event_type = "updated" # SPEC: member.updated
            
            record._send_to_residence(event_type, record)
        return records

    def write(self, vals):
        """Logique de détection des changements de statut métier"""
        # Capture de l'état avant modification
        old_states = {rec.id: getattr(rec, 'state', None) for rec in self}
        
        res = super(WebhookMixin, self).write(vals)
        
        for rec in self:
            new_state = getattr(rec, 'state', None)
            old_state = old_states.get(rec.id)
            event_to_send = None

            # 1. Gestion des Ventes (Sale Order)
            if rec._name == 'sale.order' and old_state != new_state:
                mapping = {
                    'sale': 'confirmed',
                    'done': 'completed',
                    'cancel': 'cancelled'
                }
                event_to_send = mapping.get(new_state)

            # 2. Gestion des Réservations
            elif rec._name in ['hotel.reservation', 'restaurant.reservation'] and old_state != new_state:
                mapping = {
                    'confirmed': 'approved',
                    'refused': 'rejected',
                    'cancelled': 'cancelled',
                    'checked_in': 'checked_in'
                }
                event_to_send = mapping.get(new_state)

            # 3. Gestion des Abonnements (Subscription)
            elif rec._name == 'sale.subscription' and old_state != new_state:
                mapping = {
                    'open': 'activated',
                    'pending': 'paused',
                    'close': 'expired',
                    'cancel': 'cancelled'
                }
                event_to_send = mapping.get(new_state)

            # 4. Gestion des Membres (Partner) - Toujours 'updated'
            elif rec._name == 'res.partner':
                event_to_send = "updated"

            # Envoi si un événement métier est identifié ou si c'est une mise à jour générique
            if event_to_send:
                rec._send_to_residence(event_to_send, rec)
            elif any(f in vals for f in ['name', 'email', 'phone', 'active']):
                # Pour les autres cas, on envoie un 'updated' générique
                rec._send_to_residence("updated", rec)

        return res

    def unlink(self):
        """Notification avant suppression"""
        for rec in self:
            rec._send_to_residence("cancelled", rec)
        return super(WebhookMixin, self).unlink()