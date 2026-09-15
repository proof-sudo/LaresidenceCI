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
            if product.est_disponible_comme_salle:
                product._sync_pos_floor()
        return products

    def write(self, vals):
        res = super().write(vals)

        # 🔐 On ne resynchronise QUE si le flag ou le nom change
        if 'est_disponible_comme_salle' in vals or 'name' in vals:
            for product in self:
                if product.est_disponible_comme_salle:
                    product._sync_pos_floor()

        return res

    def _sync_pos_floor(self):
        for product in self:

            # Sécurité
            if not product.est_disponible_comme_salle:
                continue

            # Éviter les writes inutiles
            if product.pos_floor_id:
                continue

            floor = self.env['restaurant.floor'].search(
                [('name', '=', product.name)],
                limit=1
            )

            if not floor:
                floor = self.env['restaurant.floor'].create({
                    'name': product.name,
                })

            # ⚠️ write explicite (pas assignment direct)
            product.with_context(skip_pos_sync=True).write({
                'pos_floor_id': floor.id
            })
