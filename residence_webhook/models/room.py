
from odoo import models

class Room(models.Model):
    _name = "residence.room"
    _description = "Chambre"
    _inherit = ["webhook.mixin"]

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            rec._queue_webhook("room.updated", "room")
        return res
