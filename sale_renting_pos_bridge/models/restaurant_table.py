from odoo import models, fields

class RestaurantTable(models.Model):
    _inherit = 'restaurant.table'

    is_reserved = fields.Boolean(
        string="Réservée",
        default=False
    )
