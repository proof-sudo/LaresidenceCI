# -*- coding: utf-8 -*-
from odoo import models, api
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class WebhookMixin(models.AbstractModel):
    _name = "webhook.mixin"
    _description = "Mixin pour déclencher des webhooks CRUD avec suivi des champs modifiés"

    def _get_webhook_configs(self, event_type):
        """Récupère les configurations de webhook actives pour ce modèle et cet événement"""
        model_name = self._name
        domain = [
            ('model_id.model', '=', model_name),
            ('active', '=', True)
        ]
        
        # Filtre par type d'événement
        if event_type == 'create':
            domain.append(('listen_create', '=', True))
        elif event_type == 'write':
            domain.append(('listen_write', '=', True))
        elif event_type == 'unlink':
            domain.append(('listen_unlink', '=', True))
        
        return self.env['webhook.config'].search(domain)

    def _prepare_webhook_payload(self, record, changed_fields=None):
        """Prépare le payload avec gestion des types de champs complexes"""
        try:
            data = record.read()[0]
            
            # Convertir les objets non-sérialisables
            for key, value in data.items():
                if isinstance(value, (datetime,)):
                    data[key] = value.isoformat()
                elif isinstance(value, tuple) and len(value) == 2:
                    # Many2one: (id, name)
                    data[key] = {'id': value[0], 'name': value[1]}
                elif isinstance(value, list):
                    # Many2many ou One2many
                    data[key] = value
            
            return data
        except Exception as e:
            _logger.error(f"Erreur lors de la préparation du payload pour {record._name}: {e}")
            return {'id': record.id, 'error': str(e)}

    def _send_webhook(self, event_type, payload, changed_fields=None):
        """Envoie le webhook aux URLs configurées"""
        configs = self._get_webhook_configs(event_type)
        
        if not configs:
            _logger.debug(f"Aucun webhook actif configuré pour {self._name} ({event_type})")
            return

        for config in configs:
            self._send_single_webhook(config, event_type, payload, changed_fields)

    def _send_single_webhook(self, config, event_type, payload, changed_fields=None):
        """Envoie un webhook unique à une URL"""
        url = config.url
        headers = {'Content-Type': 'application/json'}
        
        if config.api_key:
            headers['Authorization'] = f'Bearer {config.api_key}'

        webhook_data = {
            "event": event_type,
            "model": self._name,
            "timestamp": datetime.now().isoformat(),
            "data": payload,
            "webhook_config": {
                "id": config.id,
                "name": config.name
            }
        }
        
        if changed_fields:
            webhook_data["changed_fields"] = changed_fields

        _logger.info(f"Envoi webhook [{event_type}] pour {self._name} à {url}")
        _logger.debug(f"Payload: {webhook_data}")

        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(webhook_data, default=str),
                timeout=config.timeout
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                _logger.info(f"Webhook envoyé avec succès à {url}, statut: {response.status_code}")
            else:
                _logger.warning(f"Webhook à {url} a retourné le statut: {response.status_code}")
                
        except requests.exceptions.Timeout:
            _logger.error(f"Timeout lors de l'envoi du webhook à {url} (timeout: {config.timeout}s)")
        except requests.exceptions.ConnectionError:
            _logger.error(f"Erreur de connexion lors de l'envoi du webhook à {url}")
        except Exception as e:
            _logger.error(f"Erreur lors de l'envoi du webhook à {url}: {e}", exc_info=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create pour envoyer des webhooks à la création"""
        records = super().create(vals_list)
        
        for record in records:
            try:
                payload = self._prepare_webhook_payload(record)
                record._send_webhook("create", payload)
            except Exception as e:
                _logger.error(f"Erreur webhook create pour {record._name}[{record.id}]: {e}")
        
        return records

    def write(self, vals):
        """Override write pour envoyer des webhooks avec les champs modifiés"""
        # Capturer l'état avant modification pour les champs complexes
        old_values = {}
        for rec in self:
            old_values[rec.id] = {}
            for field in vals:
                if field in rec._fields:
                    field_type = rec._fields[field].type
                    if field_type == 'many2many':
                        old_values[rec.id][field] = rec[field].ids
                    elif field_type == 'one2many':
                        old_values[rec.id][field] = rec[field].ids
                    elif field_type == 'many2one':
                        old_values[rec.id][field] = rec[field].id if rec[field] else False
        
        # Exécuter le write
        res = super().write(vals)
        
        # Envoyer les webhooks avec les changements
        for rec in self:
            try:
                changed_data = {}
                for field in vals:
                    if field in rec._fields:
                        field_type = rec._fields[field].type
                        
                        if field_type == 'many2many':
                            changed_data[field] = {
                                'old': old_values[rec.id].get(field, []),
                                'new': rec[field].ids,
                                'type': 'many2many'
                            }
                        elif field_type == 'one2many':
                            changed_data[field] = {
                                'old': old_values[rec.id].get(field, []),
                                'new': rec[field].ids,
                                'type': 'one2many'
                            }
                        elif field_type == 'many2one':
                            changed_data[field] = {
                                'old': old_values[rec.id].get(field),
                                'new': rec[field].id if rec[field] else False,
                                'type': 'many2one'
                            }
                        else:
                            changed_data[field] = {
                                'value': vals[field],
                                'type': field_type
                            }
                
                payload = self._prepare_webhook_payload(rec)
                rec._send_webhook("write", payload, changed_fields=changed_data)
                
            except Exception as e:
                _logger.error(f"Erreur webhook write pour {rec._name}[{rec.id}]: {e}")
        
        return res

    def unlink(self):
        """Override unlink pour envoyer des webhooks avant suppression"""
        for rec in self:
            try:
                payload = self._prepare_webhook_payload(rec)
                rec._send_webhook("unlink", payload)
            except Exception as e:
                _logger.error(f"Erreur webhook unlink pour {rec._name}[{rec.id}]: {e}")
        
        return super().unlink()