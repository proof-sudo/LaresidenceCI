# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    laresidence_pos_order_ids = fields.One2many(
        'pos.order', 'laresidence_avoir_id',
        string="Commandes régularisées par cet avoir", readonly=True)
