from odoo import models, fields

class RestaurantFloor(models.Model):
    _inherit = 'restaurant.floor'

    product_template_id = fields.Many2one(
        'product.template',
        string="Produit de location",
        compute="_compute_product",
        store=False
    )

    reservation_ids = fields.One2many(
        'pos.room.reservation',
        'floor_id',
        string="Réservations"
    )

    def _compute_product(self):
        for floor in self:
            product = self.env['product.template'].search(
                [('pos_floor_id', '=', floor.id)],
                limit=1
            )
            floor.product_template_id = product.id if product else False
