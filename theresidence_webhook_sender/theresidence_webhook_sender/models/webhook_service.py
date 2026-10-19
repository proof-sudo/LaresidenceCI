# -*- coding: utf-8 -*-

import json
import logging
import time
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError

try:
    import requests
except ImportError:
    requests = None

_logger = logging.getLogger(__name__)


class WebhookService(models.AbstractModel):
    """Service d'envoi de webhooks vers l'API The Residence."""
    _name = 'theresidence.webhook.service'
    _description = 'Service Webhook Sortant'

    # ========================================================================
    # MAPPING DES ÉVÉNEMENTS INTERNES → ÉVÉNEMENTS API
    # ========================================================================

    EVENT_MAPPING = {
        'ORDER_STATUS_CHANGED': {
            'CONFIRMED': 'order.confirmed',
            'READY': 'order.ready',
            'COMPLETED': 'order.completed',
        },
        'ORDER_CANCELLED': 'order.cancelled',
        'RESERVATION_STATUS_CHANGED': {
            'APPROVED': 'reservation.approved',
            'REJECTED': 'reservation.rejected',
            'CHECKED_IN': 'reservation.checked_in',
        },
        'RESERVATION_CANCELLED': 'reservation.cancelled',
        'SUBSCRIPTION_STATUS_CHANGED': {
            'ACTIVE': None,  # Sera déterminé contextuellement (activated vs resumed)
            'PAUSED': 'subscription.paused',
        },
        'SUBSCRIPTION_CANCELLED': 'subscription.cancelled',
        'SUBSCRIPTION_CREATED': 'subscription.created',
        'SUBSCRIPTION_UPDATED': 'subscription.updated',
        
        # NOUVEAUX ÉVÉNEMENTS - Espaces
        'SPACE_CREATED': 'space.created',
        'SPACE_UPDATED': 'space.updated',
        'SPACE_DELETED': 'space.deleted',
        'SPACE_AVAILABILITY_CHANGED': 'space.availability_changed',
        
        # NOUVEAUX ÉVÉNEMENTS - Catégories POS
        'POS_CATEGORY_CREATED': 'pos_category.created',
        'POS_CATEGORY_UPDATED': 'pos_category.updated',
        'POS_CATEGORY_DELETED': 'pos_category.deleted',
        
        # NOUVEAUX ÉVÉNEMENTS - Membres
        'MEMBER_CREATED': 'member.created',
        'MEMBER_UPDATED': 'member.updated',
        'MEMBER_DELETED': 'member.deleted',
        'MEMBER_MEMBERSHIP_CHANGED': 'member.membership_changed',
    }

    # ========================================================================
    # POINT D'ENTRÉE PRINCIPAL (appelé depuis les modèles métier)
    # ========================================================================

    @api.model
    def trigger_event(self, internal_event, entity_type, entity_id, data=None, old_status=None, new_status=None):
        """
        Point d'entrée pour déclencher l'envoi d'un webhook.
        
        Args:
            internal_event (str): Type d'événement interne (ex: 'ORDER_STATUS_CHANGED')
            entity_type (str): Type d'entité ('order', 'reservation', 'subscription', 'member', 'space', 'pos_category')
            entity_id (str): UUID de l'entité (x_tr_uuid)
            data (dict): Données additionnelles de l'événement
            old_status (str): Ancien statut (None si création)
            new_status (str): Nouveau statut
        """
        try:
            # Vérifier que la configuration existe et est active
            config = self.env['theresidence.webhook.config'].get_active_config()
            if not config:
                _logger.warning("Aucune configuration webhook active. Événement ignoré.")
                return

            # Mapper l'événement interne vers l'événement API
            api_event_type = self._map_event_type(internal_event, old_status, new_status, config)
            
            if not api_event_type:
                if config.enable_debug_logs:
                    _logger.debug(f"Événement {internal_event} (old={old_status}, new={new_status}) non mappé ou ignoré")
                return

            # Créer l'entrée dans la queue
            queue_item = self.env['theresidence.webhook.queue'].create({
                'event_type': api_event_type,
                'entity_type': entity_type,
                'entity_id': entity_id,
                'payload_data': json.dumps(data or {}, default=str, ensure_ascii=False),
                'state': 'pending',
                'internal_event_type': internal_event,
                'old_status': old_status,
                'new_status': new_status,
            })

            if config.enable_debug_logs:
                _logger.info(f"Webhook créé: {api_event_type} pour {entity_type} {entity_id} (queue_id={queue_item.id})")

            # Tenter l'envoi immédiat (asynchrone via commit)
            self.env.cr.commit()
            self._process_queue()

        except Exception as e:
            _logger.error(f"Erreur lors du déclenchement du webhook: {str(e)}", exc_info=True)

    def _map_event_type(self, internal_event, old_status, new_status, config):
        """
        Mappe un événement interne vers un événement API.
        
        Returns:
            str or None: Type d'événement API, ou None si l'événement doit être ignoré
        """
        # Ignorer les événements de création sauf si explicitement activé
        if internal_event.endswith('_CREATED') and not config.send_created_events:
            return None

        # Récupérer le mapping
        mapping = self.EVENT_MAPPING.get(internal_event)
        
        if not mapping:
            return None

        # Si le mapping est un dict, utiliser le nouveau statut comme clé
        if isinstance(mapping, dict):
            event_type = mapping.get(new_status)
            
            # Cas spécial: ACTIVE peut être activated OU resumed
            if new_status == 'ACTIVE' and internal_event == 'SUBSCRIPTION_STATUS_CHANGED':
                if old_status == 'PAUSED':
                    event_type = 'subscription.resumed'
                else:
                    event_type = 'subscription.activated'
            
            return event_type
        
        # Sinon, le mapping est direct
        return mapping

    # ========================================================================
    # TRAITEMENT DE LA QUEUE
    # ========================================================================

    @api.model
    def _process_queue(self):
        """
        Traite la queue des webhooks en attente.
        
        Returns:
            int: Nombre de webhooks traités
        """
        config = self.env['theresidence.webhook.config'].get_active_config()
        if not config or not config.is_active:
            return 0

        # Récupérer les webhooks à traiter
        domain = [
            '|',
            ('state', '=', 'pending'),
            '&',
            ('state', '=', 'failed'),
            ('retry_count', '<', config.max_retries),
            '|',
            ('next_retry', '=', False),
            ('next_retry', '<=', fields.Datetime.now())
        ]
        
        queue_items = self.env['theresidence.webhook.queue'].search(domain, limit=50, order='priority desc, create_date asc')
        
        processed_count = 0
        for item in queue_items:
            try:
                self._send_webhook(item, config)
                processed_count += 1
                self.env.cr.commit()  # Commit après chaque envoi réussi
            except Exception as e:
                _logger.error(f"Erreur lors du traitement du webhook {item.event_id}: {str(e)}", exc_info=True)
                self.env.cr.rollback()

        return processed_count

    def _send_webhook(self, queue_item, config):
        """
        Envoie un webhook individuel.
        
        Args:
            queue_item: Enregistrement de la queue
            config: Configuration active
        """
        if not requests:
            raise UserError(_("La bibliothèque 'requests' n'est pas installée. Veuillez l'installer avec: pip install requests"))

        # Marquer comme en cours d'envoi
        queue_item.state = 'sending'

        start_time = time.time()
        
        try:
            # Construire l'URL
            url = f"{config.base_url}/v1/external/webhooks/odoo"
            
            # Construire les headers
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': config.api_key,
                'User-Agent': 'Odoo-TheResidence-Webhook/1.0',
            }
            
            # Construire le payload
            payload_data = json.loads(queue_item.payload_data) if queue_item.payload_data else {}
            payload = {
                'event_type': queue_item.event_type,
                'event_id': queue_item.event_id,
                'timestamp': queue_item.timestamp,
                'entity_type': queue_item.entity_type,
                'entity_id': queue_item.entity_id,
                'data': payload_data
            }
            
            if config.enable_debug_logs:
                _logger.info(f"Envoi webhook {queue_item.event_id} vers {url}")
                _logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            # Envoyer la requête
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=config.timeout
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Logger la réponse
            if config.enable_debug_logs:
                _logger.info(f"Réponse webhook {queue_item.event_id}: HTTP {response.status_code} ({duration_ms}ms)")
            
            # Traiter la réponse
            response_body = response.text[:1000]  # Limiter la taille stockée
            
            if response.status_code == 202:
                # Succès!
                queue_item.write({
                    'state': 'sent',
                    'sent_at': fields.Datetime.now(),
                    'response_code': response.status_code,
                    'response_body': response_body,
                    'last_error': False,
                })
                
                # Logger le succès
                self.env['theresidence.webhook.log'].log_attempt(
                    queue_item,
                    status='success',
                    http_code=response.status_code,
                    response_body=response_body,
                    duration_ms=duration_ms
                )
                
                _logger.info(f"✓ Webhook {queue_item.event_id} envoyé avec succès")
                
            else:
                # Erreur HTTP
                error_msg = f"HTTP {response.status_code}: {response_body}"
                self._handle_send_failure(queue_item, config, error_msg, response.status_code, duration_ms)
                
        except requests.exceptions.Timeout:
            error_msg = f"Timeout après {config.timeout} secondes"
            self._handle_send_failure(queue_item, config, error_msg, duration_ms=int((time.time() - start_time) * 1000))
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Erreur de connexion: {str(e)}"
            self._handle_send_failure(queue_item, config, error_msg, duration_ms=int((time.time() - start_time) * 1000))
            
        except Exception as e:
            error_msg = f"Erreur inattendue: {str(e)}"
            self._handle_send_failure(queue_item, config, error_msg, duration_ms=int((time.time() - start_time) * 1000))

    def _handle_send_failure(self, queue_item, config, error_msg, http_code=None, duration_ms=None):
        """Gère l'échec d'envoi d'un webhook."""
        queue_item.retry_count += 1
        
        # Calculer le prochain retry
        next_retry = None
        if queue_item.retry_count < config.max_retries:
            delays = [int(d.strip()) for d in config.retry_delays.split(',')]
            delay_index = min(queue_item.retry_count - 1, len(delays) - 1)
            delay_seconds = delays[delay_index] if delays else 5
            next_retry = fields.Datetime.now() + timedelta(seconds=delay_seconds)
            new_state = 'failed'  # Mais sera retenté
        else:
            new_state = 'failed'  # Définitivement échoué
        
        # Mettre à jour le webhook
        queue_item.write({
            'state': new_state,
            'last_error': error_msg,
            'response_code': http_code,
            'next_retry': next_retry,
        })
        
        # Logger l'échec
        self.env['theresidence.webhook.log'].log_attempt(
            queue_item,
            status='retry' if queue_item.retry_count < config.max_retries else 'error',
            http_code=http_code,
            error_message=error_msg,
            duration_ms=duration_ms,
            next_retry_at=next_retry
        )
        
        if queue_item.retry_count < config.max_retries:
            _logger.warning(f"⚠ Webhook {queue_item.event_id} échoué (tentative {queue_item.retry_count}/{config.max_retries}): {error_msg}")
            if next_retry:
                _logger.info(f"  → Prochaine tentative: {next_retry}")
        else:
            _logger.error(f"✗ Webhook {queue_item.event_id} définitivement échoué après {queue_item.retry_count} tentatives: {error_msg}")

    # ========================================================================
    # TEST DE CONNEXION
    # ========================================================================

    def _send_test_webhook(self, config):
        """
        Envoie un webhook de test pour vérifier la connexion.
        
        Returns:
            dict: {'success': bool, 'message': str, 'error': str}
        """
        if not requests:
            return {
                'success': False,
                'error': "La bibliothèque 'requests' n'est pas installée."
            }

        try:
            url = f"{config.base_url}/v1/external/webhooks/odoo"
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': config.api_key,
            }
            
            payload = {
                'event_type': 'test.connection',
                'event_id': f"test_{int(time.time())}",
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'entity_type': 'test',
                'entity_id': 'test-123',
                'data': {
                    'message': 'Test de connexion depuis Odoo',
                    'odoo_version': '19.0',
                }
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=config.timeout)
            
            if response.status_code == 202:
                return {
                    'success': True,
                    'message': f"Connexion réussie! (HTTP {response.status_code})"
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': f"Timeout après {config.timeout} secondes"
            }
        except requests.exceptions.ConnectionError as e:
            return {
                'success': False,
                'error': f"Erreur de connexion: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Erreur: {str(e)}"
            }

    # ========================================================================
    # MÉTHODES UTILITAIRES
    # ========================================================================
    # Dans webhook_service.py
    
    @api.model
    def is_event_enabled(self, internal_event):
        """Vérifie si un événement est actif dans la config."""
        config = self.env['theresidence.webhook.config'].get_active_config()
        if not config or not config.is_active:
            return False
            
        # On vérifie si l'événement de création est autorisé
        if internal_event.endswith('_CREATED') and not config.send_created_events:
            return False
            
        return internal_event in self.EVENT_MAPPING
    
    @api.model
    def get_statistics(self):
        """Retourne des statistiques sur les webhooks."""
        queue_model = self.env['theresidence.webhook.queue']
        
        return {
            'total_sent': queue_model.search_count([('state', '=', 'sent')]),
            'total_pending': queue_model.search_count([('state', '=', 'pending')]),
            'total_failed': queue_model.search_count([('state', '=', 'failed')]),
            'last_24h_sent': queue_model.search_count([
                ('state', '=', 'sent'),
                ('sent_at', '>=', fields.Datetime.now() - timedelta(hours=24))
            ]),
            'last_24h_failed': queue_model.search_count([
                ('state', '=', 'failed'),
                ('create_date', '>=', fields.Datetime.now() - timedelta(hours=24))
            ]),
        }