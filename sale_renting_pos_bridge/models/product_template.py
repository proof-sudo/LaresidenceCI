from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    est_disponible_comme_salle = fields.Boolean(
        string="Disponible comme salle (POS)"
    )

    pos_floor_id = fields.Many2one(
        'restaurant.floor',
        string="Salle POS associée",
        readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        for product in products:
            product._sync_pos_floor()
        return products

    def write(self, vals):
        res = super().write(vals)
        for product in self:
            product._sync_pos_floor()
        return res

    def _sync_pos_floor(self):
        for product in self:
            if not product.est_disponible_comme_salle:
                continue

            floor = self.env['restaurant.floor'].search(
                [('name', '=', product.name)], limit=1
            )

            if not floor:
                floor = self.env['restaurant.floor'].create({
                    'name': product.name,
                })

            product.pos_floor_id = floor.id
