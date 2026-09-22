# -*- coding: utf-8 -*-
from odoo import fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    laresidence_facture_groupee_id = fields.Many2one(
        'account.move',
        string="Facture groupée",
        readonly=True, copy=False, index=True, ondelete='set null',
        help="Facture unique qui couvre cette commande, avec d'autres commandes "
             "du même client réglées en compte client.")
