# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    laresidence_pos_order_ids = fields.One2many(
        'pos.order', 'laresidence_facture_groupee_id',
        string="Commandes point de vente couvertes", readonly=True)
    laresidence_pos_order_count = fields.Integer(
        string="Nombre de commandes", compute='_compute_laresidence_pos_order_count')

    def _compute_laresidence_pos_order_count(self):
        for facture in self:
            facture.laresidence_pos_order_count = len(facture.laresidence_pos_order_ids)

    def action_laresidence_voir_commandes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Commandes couvertes",
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [('laresidence_facture_groupee_id', '=', self.id)],
        }
