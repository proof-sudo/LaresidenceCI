# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class WebhookConfig(models.Model):
    """Configuration du webhook sortant vers l'API The Residence."""
    _name = 'theresidence.webhook.config'
    _description = 'Configuration Webhook API The Residence'
    _rec_name = 'name'

    name = fields.Char(
        string='Nom',
        required=True,
        default='The Residence API',
        help='Nom de la configuration'
    )
    
    base_url = fields.Char(
        string='URL de base',
        required=True,
        default='https://api.laresidence-abidjan.com',
        help='URL de base de l\'API (sans le /v1/external/webhooks/odoo)'
    )
    
    api_key = fields.Char(
        string='API Key',
        required=True,
        help='Clé API fournie par The Residence (header X-API-Key)'
    )
    
    is_active = fields.Boolean(
        string='Actif',
        default=True,
        help='Activer/désactiver l\'envoi des webhooks'
    )
    
    # Configuration des timeouts et retry
    timeout = fields.Integer(
        string='Timeout (secondes)',
        default=10,
        required=True,
        help='Délai d\'attente maximum pour la requête HTTP'
    )
    
    max_retries = fields.Integer(
        string='Tentatives maximum',
        default=5,
        required=True,
        help='Nombre maximum de tentatives en cas d\'échec'
    )
    
    retry_delays = fields.Char(
        string='Délais entre tentatives (secondes)',
        default='1,2,4,8,16',
        required=True,
        help='Délais en secondes entre chaque tentative, séparés par des virgules (backoff exponentiel)'
    )
    
    # Statistiques
    total_sent = fields.Integer(
        string='Total envoyés',
        compute='_compute_statistics',
        store=False,
        help='Nombre total de webhooks envoyés avec succès'
    )
    
    total_failed = fields.Integer(
        string='Total échoués',
        compute='_compute_statistics',
        store=False,
        help='Nombre total de webhooks définitivement échoués'
    )
    
    total_pending = fields.Integer(
        string='En attente',
        compute='_compute_statistics',
        store=False,
        help='Nombre de webhooks en attente d\'envoi'
    )
    
    # Options avancées
    send_created_events = fields.Boolean(
        string='Envoyer les événements de création',
        default=False,
        help='Si activé, envoie aussi les événements *_CREATED (non requis par la spec)'
    )
    
    enable_debug_logs = fields.Boolean(
        string='Logs de débogage',
        default=False,
        help='Activer les logs détaillés pour le débogage'
    )

    @api.depends()
    def _compute_statistics(self):
        """Calcule les statistiques d'envoi."""
        for config in self:
            queue_model = self.env['theresidence.webhook.queue']
            config.total_sent = queue_model.search_count([('state', '=', 'sent')])
            config.total_failed = queue_model.search_count([
                ('state', '=', 'failed'),
                ('retry_count', '>=', config.max_retries)
            ])
            config.total_pending = queue_model.search_count([
                ('state', 'in', ['pending', 'failed']),
                ('retry_count', '<', config.max_retries)
            ])

    @api.constrains('timeout')
    def _check_timeout(self):
        """Vérifie que le timeout est valide."""
        for config in self:
            if config.timeout < 1 or config.timeout > 300:
                raise ValidationError(_('Le timeout doit être entre 1 et 300 secondes.'))

    @api.constrains('max_retries')
    def _check_max_retries(self):
        """Vérifie que le nombre de retries est valide."""
        for config in self:
            if config.max_retries < 0 or config.max_retries > 10:
                raise ValidationError(_('Le nombre de tentatives doit être entre 0 et 10.'))

    @api.constrains('retry_delays')
    def _check_retry_delays(self):
        """Vérifie que les délais sont valides."""
        for config in self:
            try:
                delays = [int(d.strip()) for d in config.retry_delays.split(',')]
                if not delays or any(d < 0 for d in delays):
                    raise ValueError
            except (ValueError, AttributeError):
                raise ValidationError(_('Les délais doivent être des nombres entiers positifs séparés par des virgules.'))

    def action_test_connection(self):
        """Teste la connexion à l'API."""
        self.ensure_one()
        service = self.env['theresidence.webhook.service']
        
        try:
            result = service._send_test_webhook(self)
            if result['success']:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connexion réussie'),
                        'message': _('La connexion à l\'API The Residence a été établie avec succès.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Échec de connexion'),
                        'message': result.get('error', _('Erreur inconnue')),
                        'type': 'warning',
                        'sticky': True,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Erreur'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_view_queue(self):
        """Ouvre la vue de la queue des webhooks."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Queue des webhooks'),
            'res_model': 'theresidence.webhook.queue',
            'view_mode': 'tree,form',
            'domain': [],
            'context': {'default_config_id': self.id},
        }

    def action_view_logs(self):
        """Ouvre la vue des logs."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Logs des webhooks'),
            'res_model': 'theresidence.webhook.log',
            'view_mode': 'tree,form',
            'domain': [],
            'context': {},
        }

    def action_process_queue_now(self):
        """Force le traitement immédiat de la queue."""
        self.ensure_one()
        service = self.env['theresidence.webhook.service']
        processed = service._process_queue()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Traitement terminé'),
                'message': _('%d webhook(s) traité(s)') % processed,
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def get_active_config(self):
        """Récupère la configuration active."""
        return self.search([('is_active', '=', True)], limit=1)
