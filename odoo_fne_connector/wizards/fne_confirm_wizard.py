# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class FneConfirmWizard(models.TransientModel):
    _name = 'fne.confirm.wizard'
    _description = "Confirmation de certification FNE / DGI"

    invoice_ids = fields.Many2many(
        'account.move',
        'fne_confirm_wizard_invoice_rel',
        'wizard_id', 'invoice_id',
        string="Factures à certifier",
        readonly=True,
    )
    invoice_count = fields.Integer(compute='_compute_summary', string="Nombre de factures")
    total_amount = fields.Float(compute='_compute_summary', string="Montant total HT")
    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_summary',
    )

    @api.depends('invoice_ids')
    def _compute_summary(self):
        for wiz in self:
            wiz.invoice_count = len(wiz.invoice_ids)
            wiz.total_amount = sum(wiz.invoice_ids.mapped('amount_untaxed'))
            currencies = wiz.invoice_ids.mapped('currency_id')
            wiz.currency_id = currencies[0] if len(currencies) == 1 else False

    def action_confirm(self):
        """Déclenche l'envoi réel à la DGI après confirmation."""
        self.invoice_ids._execute_fne_send()
        return {'type': 'ir.actions.act_window_close'}
