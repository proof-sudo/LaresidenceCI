# -*- coding: utf-8 -*-
from odoo import models, fields, api

TVA = 1.18


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_cost_ttc = fields.Float(
        string='Coût TTC (18%)',
        compute='_compute_cost_ttc',
        digits='Product Price',
        help="Coût HT × 1.18 — calculé automatiquement, non stocké.",
    )

    @api.depends('standard_price')
    def _compute_cost_ttc(self):
        for product in self:
            product.x_cost_ttc = product.standard_price * TVA

    def action_apply_tva_to_cost(self):
        """Applique la TVA 18% au coût HT et écrase standard_price avec le TTC."""
        products = self.filtered(lambda p: p.standard_price > 0)
        for product in products:
            product.standard_price = product.standard_price * TVA
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Coûts mis à jour',
                'message': '%d produit(s) mis à jour avec TVA 18%%.' % len(products),
                'type': 'success',
                'sticky': False,
            },
        }
