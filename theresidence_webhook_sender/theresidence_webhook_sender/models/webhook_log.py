# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from odoo import models, fields, api


class WebhookLog(models.Model):
    """Logs des tentatives d'envoi de webhooks."""
    _name = 'theresidence.webhook.log'
    _description = 'Logs Webhooks'
    _order = 'create_date desc'
    _rec_name = 'event_id'

    event_id = fields.Char(
        string='Event ID',
        required=True,
        index=True,
        help='Identifiant de l\'événement'
    )
    
    event_type = fields.Char(
        string='Type événement',
        required=True,
        help='Type de l\'événement'
    )
    
    entity_type = fields.Char(
        string='Type entité',
        help='Type de l\'entité'
    )
    
    entity_id = fields.Char(
        string='Entity ID',
        help='UUID de l\'entité'
    )
    
    attempt_number = fields.Integer(
        string='Tentative n°',
        required=True,
        help='Numéro de la tentative d\'envoi'
    )
    
    status = fields.Selection(
        selection=[
            ('success', 'Succès'),
            ('error', 'Erreur'),
            ('retry', 'Nouvelle tentative'),
        ],
        string='Statut',
        required=True,
        index=True,
    )
    
    http_code = fields.Integer(
        string='Code HTTP',
        help='Code de réponse HTTP'
    )
    
    request_url = fields.Char(
        string='URL',
        help='URL de la requête'
    )
    
    request_payload = fields.Text(
        string='Payload envoyé',
        help='Données JSON envoyées'
    )
    
    response_body = fields.Text(
        string='Réponse',
        help='Corps de la réponse de l\'API'
    )
    
    error_message = fields.Text(
        string='Message d\'erreur',
        help='Message d\'erreur en cas d\'échec'
    )
    
    duration_ms = fields.Integer(
        string='Durée (ms)',
        help='Durée de la requête en millisecondes'
    )
    
    next_retry_at = fields.Datetime(
        string='Prochaine tentative',
        help='Date de la prochaine tentative planifiée'
    )

    @api.model
    def log_attempt(self, queue_item, status, http_code=None, response_body=None, 
                   error_message=None, duration_ms=None, next_retry_at=None):
        """Enregistre une tentative d'envoi."""
        return self.create({
            'event_id': queue_item.event_id,
            'event_type': queue_item.event_type,
            'entity_type': queue_item.entity_type,
            'entity_id': queue_item.entity_id,
            'attempt_number': queue_item.retry_count + 1,
            'status': status,
            'http_code': http_code,
            'request_url': self._get_webhook_url(),
            'request_payload': queue_item.full_payload,
            'response_body': response_body,
            'error_message': error_message,
            'duration_ms': duration_ms,
            'next_retry_at': next_retry_at,
        })

    @api.model
    def _get_webhook_url(self):
        """Récupère l'URL du webhook configuré."""
        config = self.env['theresidence.webhook.config'].get_active_config()
        if config:
            return f"{config.base_url}/v1/external/webhooks/odoo"
        return ''

    @api.model
    def cleanup_old_logs(self, days=90):
        """Nettoie les anciens logs."""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_logs = self.search([('create_date', '<', cutoff_date)])
        count = len(old_logs)
        old_logs.unlink()
        return count

    def action_view_queue_item(self):
        """Affiche l'élément de la queue associé."""
        self.ensure_one()
        queue_item = self.env['theresidence.webhook.queue'].search([
            ('event_id', '=', self.event_id)
        ], limit=1)
        
        if not queue_item:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Non trouvé',
                    'message': 'L\'élément de la queue n\'existe plus.',
                    'type': 'warning',
                }
            }
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Élément de la queue',
            'res_model': 'theresidence.webhook.queue',
            'res_id': queue_item.id,
            'view_mode': 'form',
            'target': 'current',
        }
