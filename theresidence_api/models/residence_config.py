# -*- coding: utf-8 -*-

import uuid
import hmac
import hashlib
import requests
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResidenceConfig(models.Model):
    _name = 'residence.config'
    _description = 'The Residence API Configuration'
    _rec_name = 'name'

    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='Configuration Principale'
    )
    active = fields.Boolean(default=True)

    # ==========================================
    # API Externe The Residence (pour appeler leur API)
    # ==========================================
    api_base_url = fields.Char(
        string='URL API Externe',
        default='https://api.laresidence-abidjan.com/v1/external',
        help='URL de base de l\'API The Residence'
    )
    api_key = fields.Char(
        string='Clé API Externe',
        help='Clé API pour s\'authentifier auprès de The Residence'
    )

    # ==========================================
    # Notre API (pour que le mobile nous appelle)
    # ==========================================
    internal_api_key = fields.Char(
        string='Notre Clé API',
        default=lambda self: str(uuid.uuid4()),
        help='Clé API que le mobile doit utiliser pour nous appeler'
    )
    webhook_secret = fields.Char(
        string='Secret Webhook',
        default=lambda self: str(uuid.uuid4()),
        help='Secret pour vérifier les signatures des webhooks entrants'
    )
    webhook_url = fields.Char(
        string='URL Webhook (à donner au mobile)',
        compute='_compute_webhook_url',
        store=False
    )

    # ==========================================
    # Configuration comportement
    # ==========================================
    auto_confirm_reservation = fields.Boolean(
        string='Confirmer auto les réservations',
        default=False,
        help='Confirmer automatiquement les devis de réservation'
    )
    auto_confirm_order = fields.Boolean(
        string='Confirmer auto les commandes',
        default=True,
        help='Confirmer automatiquement les commandes restaurant'
    )
    send_webhook_on_change = fields.Boolean(
        string='Envoyer webhooks',
        default=True,
        help='Envoyer des webhooks au mobile lors des changements'
    )
    external_webhook_url = fields.Char(
        string='URL Webhook Mobile',
        help='URL du mobile pour recevoir nos webhooks'
    )

    # ==========================================
    # Produits et catégories par défaut
    # ==========================================
    default_space_categ_id = fields.Many2one(
        'product.category',
        string='Catégorie Salles',
        help='Catégorie de produit par défaut pour les salles'
    )
    default_menu_categ_id = fields.Many2one(
        'product.category',
        string='Catégorie Menu',
        help='Catégorie de produit par défaut pour les articles menu'
    )
    default_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Liste de prix par défaut'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        required=True
    )

    @api.depends('company_id')
    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.webhook_url = f"{base_url}/api/v1/webhook"

    # ==========================================
    # Méthodes utilitaires
    # ==========================================
    def generate_new_api_key(self):
        """Générer une nouvelle clé API interne"""
        self.ensure_one()
        self.internal_api_key = str(uuid.uuid4())
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Nouvelle clé API générée'),
                'type': 'success',
                'sticky': False,
            }
        }

    def generate_new_webhook_secret(self):
        """Générer un nouveau secret webhook"""
        self.ensure_one()
        self.webhook_secret = str(uuid.uuid4())
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Succès'),
                'message': _('Nouveau secret webhook généré'),
                'type': 'success',
                'sticky': False,
            }
        }

    def verify_webhook_signature(self, payload, signature):
        """Vérifier la signature HMAC-SHA256 d'un webhook entrant"""
        if not self.webhook_secret:
            return True  # Pas de secret configuré, on accepte

        if not signature:
            return False

        expected = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload if isinstance(payload, bytes) else payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        received = signature.replace('sha256=', '') if signature else ''
        return hmac.compare_digest(expected, received)

    def sign_payload(self, payload):
        """Signer un payload pour envoyer un webhook sortant"""
        if not self.webhook_secret:
            return None

        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload if isinstance(payload, bytes) else payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return f"sha256={signature}"

    @api.model
    def get_config(self, company_id=None):
        """Récupérer la configuration active pour une société"""
        domain = [('active', '=', True)]
        if company_id:
            domain.append(('company_id', '=', company_id))
        else:
            domain.append(('company_id', '=', self.env.company.id))
        config = self.search(domain, limit=1)
        if not config:
            # Créer une config par défaut si elle n'existe pas
            config = self.create({
                'name': 'Configuration Principale',
                'company_id': company_id or self.env.company.id,
            })
        return config

    def validate_api_key(self, api_key):
        """Valider une clé API entrante"""
        if not api_key:
            return False
        return self.search([
            ('internal_api_key', '=', api_key),
            ('active', '=', True)
        ], limit=1)

    # ==========================================
    # Test connexion
    # ==========================================
    def test_external_connection(self):
        """Tester la connexion à l'API externe The Residence"""
        self.ensure_one()
        if not self.api_base_url or not self.api_key:
            raise UserError(_('Veuillez configurer l\'URL et la clé API externe'))

        try:
            response = requests.get(
                f"{self.api_base_url}/reference/spaces",
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json'
                },
                timeout=10
            )

            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Succès'),
                        'message': _('Connexion à l\'API externe réussie!'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_(f'Erreur API: Status {response.status_code}'))

        except requests.exceptions.RequestException as e:
            raise UserError(_(f'Erreur de connexion: {str(e)}'))

    # ==========================================
    # Envoi webhook sortant
    # ==========================================
    def send_webhook(self, event_type, entity_type, entity_id, data, previous_status=None, new_status=None):
        """Envoyer un webhook au mobile"""
        self.ensure_one()

        if not self.send_webhook_on_change or not self.external_webhook_url:
            return False

        import json
        from datetime import datetime

        payload = {
            'id': str(uuid.uuid4()),
            'eventType': event_type,
            'entityType': entity_type,
            'entityId': str(entity_id),
            'data': data,
            'previousStatus': previous_status,
            'newStatus': new_status,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

        payload_str = json.dumps(payload)
        signature = self.sign_payload(payload_str)

        headers = {
            'Content-Type': 'application/json',
            'X-Webhook-Signature': signature or ''
        }

        try:
            response = requests.post(
                self.external_webhook_url,
                data=payload_str,
                headers=headers,
                timeout=30
            )

            # Logger le webhook
            self.env['residence.webhook.log'].sudo().create({
                'direction': 'outgoing',
                'event_type': event_type,
                'entity_type': entity_type,
                'entity_id': str(entity_id),
                'payload': payload_str,
                'response_status': response.status_code,
                'response_body': response.text[:1000] if response.text else '',
                'state': 'success' if response.status_code < 400 else 'failed'
            })

            return response.status_code < 400

        except Exception as e:
            _logger.error(f"Erreur envoi webhook: {str(e)}")
            self.env['residence.webhook.log'].sudo().create({
                'direction': 'outgoing',
                'event_type': event_type,
                'entity_type': entity_type,
                'entity_id': str(entity_id),
                'payload': payload_str,
                'response_body': str(e),
                'state': 'failed'
            })
            return False
