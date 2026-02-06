
from odoo import models

class Partner(models.Model):
    _inherit = ["res.partner", "webhook.mixin"]

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._queue_webhook("member.updated", "member")
        return res
