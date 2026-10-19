
from odoo import models

class Reservation(models.Model):
    _name = "residence.reservation"
    _description = "Réservation"
    _inherit = ["webhook.mixin"]

    def write(self, vals):
        res = super().write(vals)

        mapping = {
            "approved": "reservation.approved",
            "cancelled": "reservation.cancelled",
            "rejected": "reservation.rejected"
        }

        for rec in self:
            if rec.state in mapping:
                rec._queue_webhook(mapping[rec.state], "reservation")

        return res
