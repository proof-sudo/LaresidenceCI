
from odoo import models

class Subscription(models.Model):
    _inherit = ["sale.subscription", "webhook.mixin"]

    def write(self, vals):
        res = super().write(vals)

        mapping = {
            "open": "subscription.activated",
            "cancel": "subscription.cancelled",
            "close": "subscription.expired"
        }

        for rec in self:
            if rec.stage_id:
                event = mapping.get(rec.stage_id.category)
                if event:
                    rec._queue_webhook(event, "subscription")

        return res
