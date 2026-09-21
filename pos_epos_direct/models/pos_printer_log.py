# -*- coding: utf-8 -*-
from odoo import models, fields


class PosPrinterLog(models.Model):
    _name = 'pos.printer.log'
    _description = "Log d'impression ePOS"
    _order = 'create_date desc'
    _rec_name = 'create_date'

    printer_id = fields.Many2one('pos.printer', string='Imprimante', ondelete='set null', index=True)
    printer_name = fields.Char(string='Imprimante', help="Nom conservé même si l'imprimante est supprimée")
    order_name = fields.Char(string='Commande')
    job_type = fields.Selection([
        ('receipt', 'Reçu client'),
        ('kitchen', 'Ticket cuisine'),
    ], string='Type', required=True)
    status = fields.Selection([
        ('success', 'Succès'),
        ('error',   'Erreur'),
    ], string='Statut', required=True)
    duration_ms = fields.Integer(string='Durée (ms)')
    ip = fields.Char(string='IP imprimante')
    message = fields.Text(string='Détails')
    create_date = fields.Datetime(string='Date', readonly=True)
