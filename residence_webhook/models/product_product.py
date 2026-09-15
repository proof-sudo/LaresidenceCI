
from odoo import api, models

class Product(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "webhook.mixin"]

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._queue_webhook("product.updated", "product")
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._queue_webhook("product.created", "product")
        return records
