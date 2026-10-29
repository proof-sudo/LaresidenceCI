# -*- coding: utf-8 -*-

import uuid
import json
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WebhookQueue(models.Model):
    """Queue des webhooks à envoyer vers l'API The Residence."""
    _name = 'theresidence.webhook.queue'
    _description = 'Queue Webhooks Sortants'
    _order = 'create_date asc, priority desc'
    _rec_name = 'event_id'

    # Identification de l'événement
    event_id = fields.Char(
        string='Event ID',
        required=True,
        index=True,
        readonly=True,
        copy=False,
        default=lambda self: self._generate_event_id(),
        help='Identifiant unique de l\'événement (pour idempotence)'
    )
    
    event_type = fields.Selection(
        selection=[
            ('order.confirmed', 'Commande - Confirmée'),
            ('order.ready', 'Commande - Prête'),
            ('order.completed', 'Commande - Terminée'),
            ('order.cancelled', 'Commande - Annulée'),
            ('reservation.approved', 'Réservation - Approuvée'),
            ('reservation.rejected', 'Réservation - Rejetée'),
            ('reservation.cancelled', 'Réservation - Annulée'),
            ('reservation.checked_in', 'Réservation - Check-in'),
            ('subscription.activated', 'Abonnement - Activé'),
            ('subscription.paused', 'Abonnement - En pause'),
            ('subscription.resumed', 'Abonnement - Repris'),
            ('subscription.cancelled', 'Abonnement - Annulé'),
            ('subscription.expired', 'Abonnement - Expiré'),
            ('subscription.renewed', 'Abonnement - Renouvelé'),
            ('member.updated', 'Membre - Mis à jour'),
        ],
        string='Type d\'événement',
        required=True,
        index=True,
        help='Type de l\'événement selon la spécification API'
    )
    
    entity_type = fields.Selection(
        selection=[
            ('order', 'Commande'),
            ('reservation', 'Réservation'),
            ('subscription', 'Abonnement'),
            ('member', 'Membre'),
        ],
        string='Type d\'entité',
        required=True,
        index=True,
        help='Type de l\'entité concernée par l\'événement'
    )
    
    entity_id = fields.Char(
        string='Entity ID',
        required=True,
        index=True,
        help='UUID de l\'entité dans Odoo (x_tr_uuid)'
    )
    
    # Payload et métadonnées
    timestamp = fields.Char(
        string='Timestamp ISO',
        required=True,
        readonly=True,
        default=lambda self: datetime.utcnow().isoformat() + 'Z',
        help='Timestamp de l\'événement au format ISO 8601'
    )
    
    payload_data = fields.Text(
        string='Données (JSON)',
        help='Données additionnelles de l\'événement au format JSON'
    )
    
    full_payload = fields.Text(
        string='Payload complet',
        compute='_compute_full_payload',
        store=False,
        help='Payload JSON complet qui sera envoyé à l\'API'
    )
    
    # État et traitement
    state = fields.Selection(
        selection=[
            ('pending', 'En attente'),
            ('sending', 'Envoi en cours'),
            ('sent', 'Envoyé'),
            ('failed', 'Échoué'),
        ],
        string='État',
        default='pending',
        required=True,
        index=True,
        help='État actuel du webhook'
    )
    
    priority = fields.Selection(
        selection=[
            ('0', 'Normal'),
            ('1', 'Élevé'),
            ('2', 'Urgent'),
        ],
        string='Priorité',
        default='0',
        index=True,
        help='Priorité de traitement'
    )
    
    # Retry et erreurs
    retry_count = fields.Integer(
        string='Tentatives',
        default=0,
        readonly=True,
        help='Nombre de tentatives d\'envoi effectuées'
    )
    
    next_retry = fields.Datetime(
        string='Prochaine tentative',
        index=True,
        help='Date et heure de la prochaine tentative d\'envoi'
    )
    
    last_error = fields.Text(
        string='Dernière erreur',
        readonly=True,
        help='Message d\'erreur de la dernière tentative'
    )
    
    # Résultat
    response_code = fields.Integer(
        string='Code HTTP',
        readonly=True,
        help='Code de réponse HTTP de l\'API'
    )
    
    response_body = fields.Text(
        string='Réponse API',
        readonly=True,
        help='Corps de la réponse de l\'API'
    )
    
    sent_at = fields.Datetime(
        string='Envoyé le',
        readonly=True,
        help='Date et heure d\'envoi réussi'
    )
    
    # Métadonnées
    internal_event_type = fields.Char(
        string='Type événement interne',
        help='Type d\'événement original dans le code Odoo (ex: ORDER_STATUS_CHANGED)'
    )
    
    old_status = fields.Char(
        string='Ancien statut',
        help='Statut avant le changement'
    )
    
    new_status = fields.Char(
        string='Nouveau statut',
        help='Statut après le changement'
    )

    _sql_constraints = [
        ('event_id_unique', 'unique(event_id)', 'L\'Event ID doit être unique (idempotence).')
    ]

    @api.model
    def _generate_event_id(self):
        """Génère un event_id unique."""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_id = uuid.uuid4().hex[:8]
        return f"evt_{timestamp}_{unique_id}"

    @api.depends('event_type', 'entity_type', 'entity_id', 'timestamp', 'payload_data')
    def _compute_full_payload(self):
        """Construit le payload JSON complet."""
        for record in self:
            try:
                data = json.loads(record.payload_data) if record.payload_data else {}
            except (json.JSONDecodeError, TypeError):
                data = {}
            
            payload = {
                'event_type': record.event_type,
                'event_id': record.event_id,
                'timestamp': record.timestamp,
                'entity_type': record.entity_type,
                'entity_id': record.entity_id,
                'data': data
            }
            record.full_payload = json.dumps(payload, indent=2, ensure_ascii=False)

    def action_retry_now(self):
        """Force une nouvelle tentative d'envoi immédiate."""
        for record in self:
            if record.state == 'sent':
                raise UserError(_('Ce webhook a déjà été envoyé avec succès.'))
            
            # Réinitialiser pour permettre une nouvelle tentative
            record.write({
                'state': 'pending',
                'next_retry': False,
                'last_error': False,
            })
        
        # Déclencher le traitement
        self.env['theresidence.webhook.service']._process_queue()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Retry déclenché'),
                'message': _('Le webhook va être traité dans quelques instants.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_mark_as_failed(self):
        """Marque le webhook comme définitivement échoué."""
        for record in self:
            if record.state == 'sent':
                raise UserError(_('Ce webhook a déjà été envoyé avec succès.'))
            record.state = 'failed'

    def action_view_logs(self):
        """Affiche les logs associés à ce webhook."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Logs du webhook'),
            'res_model': 'theresidence.webhook.log',
            'view_mode': 'tree,form',
            'domain': [('event_id', '=', self.event_id)],
            'context': {},
        }

    def action_copy_payload(self):
        """Copie le payload dans le presse-papiers (via notification)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payload'),
                'message': self.full_payload,
                'type': 'info',
                'sticky': True,
            }
        }

    @api.model
    def cleanup_old_records(self, days=30):
        """Nettoie les anciens enregistrements envoyés avec succès."""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        old_records = self.search([
            ('state', '=', 'sent'),
            ('sent_at', '<', cutoff_date)
        ])
        count = len(old_records)
        old_records.unlink()
        return count
