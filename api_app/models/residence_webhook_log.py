# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResidenceWebhookLog(models.Model):
    _name = 'residence.webhook.log'
    _description = 'Journal des Webhooks'
    _order = 'create_date desc'
    _rec_name = 'event_type'

    direction = fields.Selection([
        ('incoming', 'Entrant (Mobile → Odoo)'),
        ('outgoing', 'Sortant (Odoo → Mobile)')
    ], string='Direction', required=True, default='incoming')

    event_type = fields.Char(string='Type d\'Événement', index=True)
    entity_type = fields.Char(string='Type d\'Entité')
    entity_id = fields.Char(string='ID Entité')

    # Requête
    payload = fields.Text(string='Payload (JSON)')
    headers = fields.Text(string='Headers')

    # Réponse
    response_status = fields.Integer(string='Code HTTP')
    response_body = fields.Text(string='Corps Réponse')

    # État
    state = fields.Selection([
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('success', 'Succès'),
        ('failed', 'Échec'),
        ('ignored', 'Ignoré')
    ], string='État', default='pending')

    error_message = fields.Text(string='Message d\'Erreur')

    # Tentatives (pour les sortants)
    attempt_count = fields.Integer(string='Tentatives', default=0)
    next_retry = fields.Datetime(string='Prochaine Tentative')

    # Traitement
    processed_date = fields.Datetime(string='Date de Traitement')
    processing_time = fields.Float(string='Temps de Traitement (ms)')

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )

    def action_retry(self):
        """Relancer un webhook sortant échoué"""
        for rec in self:
            if rec.direction == 'outgoing' and rec.state == 'failed':
                import json
                config = self.env['residence.config'].get_config()
                if config and rec.payload:
                    try:
                        payload_dict = json.loads(rec.payload)
                        config.send_webhook(
                            event_type=rec.event_type,
                            entity_type=rec.entity_type,
                            entity_id=rec.entity_id,
                            data=payload_dict.get('data', {}),
                            previous_status=payload_dict.get('previousStatus'),
                            new_status=payload_dict.get('newStatus')
                        )
                    except Exception as e:
                        rec.error_message = str(e)

    def action_view_payload(self):
        """Afficher le payload dans une popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payload JSON',
            'res_model': 'residence.webhook.log',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def _cron_cleanup_old_logs(self):
        """Nettoyer les vieux logs (> 30 jours)"""
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=30)
        old_logs = self.search([
            ('create_date', '<', cutoff),
            ('state', 'in', ['success', 'ignored'])
        ])
        old_logs.unlink()

    @api.model
    def _cron_retry_failed_webhooks(self):
        """Relancer les webhooks sortants échoués"""
        from datetime import datetime
        failed = self.search([
            ('direction', '=', 'outgoing'),
            ('state', '=', 'failed'),
            ('attempt_count', '<', 5),
            '|',
            ('next_retry', '=', False),
            ('next_retry', '<=', datetime.now())
        ], limit=10)

        for log in failed:
            log.attempt_count += 1
            log.action_retry()
