# -*- coding: utf-8 -*-
"""
pos.print.job — file d'attente d'impression.

Remplace l'envoi direct navigateur → imprimante (bloqué sur iOS/Safari par la
restriction "Local Network Access") par un relais :

  1. Le navigateur appelle _enqueue_epos_receipt / _enqueue_epos_kitchen
     (RPC léger vers Odoo.sh, aucune connexion réseau locale requise → OK sur iOS).
  2. Odoo génère le XML ePOS et crée une ligne pos.print.job (status='pending').
  3. Un agent Python tournant sur un PC du réseau local de l'imprimante
     interroge périodiquement /pos_print_relay/pending (connexion SORTANTE
     depuis le PC vers Odoo.sh → aucun port forwarding requis).
  4. L'agent envoie le XML en HTTP POST à l'imprimante en local, puis
     confirme via /pos_print_relay/ack.
"""

from odoo import api, fields, models


class PosPrintJob(models.Model):
    _name = 'pos.print.job'
    _description = "File d'attente d'impression ePOS (relais PC local)"
    _order = 'create_date desc'
    _rec_name = 'id'

    printer_id = fields.Many2one('pos.printer', string='Imprimante', ondelete='set null', index=True)
    order_id = fields.Many2one('pos.order', string='Commande', ondelete='set null', index=True)
    order_name = fields.Char(string='Commande (nom)')
    job_type = fields.Selection([
        ('receipt', 'Reçu client'),
        ('kitchen', 'Ticket cuisine/bar'),
    ], string='Type', required=True)

    ip = fields.Char(string='IP imprimante', required=True)
    xml = fields.Text(string='XML ePOS', required=True)

    status = fields.Selection([
        ('pending', 'En attente'),
        ('sent', 'Envoyé'),
        ('error', 'Erreur'),
    ], string='Statut', default='pending', required=True, index=True)

    error_message = fields.Text(string="Détail de l'erreur")
    sent_date = fields.Datetime(string='Date envoi')
    duration_ms = fields.Integer(string='Durée agent (ms)')

    @api.model
    def _cleanup_old_jobs(self, days=7):
        """A appeler via cron : purge les jobs traités depuis plus de N jours."""
        domain = [
            ('status', 'in', ['sent', 'error']),
            ('create_date', '<', fields.Datetime.subtract(fields.Datetime.now(), days=days)),
        ]
        self.search(domain).unlink()
