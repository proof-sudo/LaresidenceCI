
from odoo import models

class SaleOrder(models.Model):
    _inherit = ["sale.order", "webhook.mixin"]

    def write(self, vals):
        res = super().write(vals)

        for order in self:
            if "state" in vals:
                mapping = {
                    "sale": "order.confirmed",
                    "done": "order.completed",
                    "cancel": "order.cancelled"
                }

                if order.state in mapping:
                    order._queue_webhook(mapping[order.state], "order")

        return res
