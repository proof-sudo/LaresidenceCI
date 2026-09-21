
from odoo import models

class Partner(models.Model):
    # _name explicite : sans lui, un _inherit multiple crée un NOUVEAU modèle
    # nommé d'après la classe ("partner") au lieu d'étendre res.partner.
    _name = "res.partner"
    _inherit = ["res.partner", "webhook.mixin"]

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._queue_webhook("member.updated", "member")
        return res
