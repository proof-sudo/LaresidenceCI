
from odoo import models

class Product(models.Model):
    _inherit = ["product.product", "webhook.mixin"]

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._queue_webhook("product.updated", "product")
        return res

    def create(self, vals):
        rec = super().create(vals)
        rec._queue_webhook("product.created", "product")
        return rec
