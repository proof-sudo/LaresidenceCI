from odoo import models, fields, _
from odoo.exceptions import ValidationError


class WizardRejectOrder(models.TransientModel):
    _name = "mobile.order.reject.wizard"
    _description = "Motif de rejet"

    order_id = fields.Many2one('mobile.order', required=True)
    rejection_reason = fields.Text(string="Motif de rejet", required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if self.order_id.x_tr_order_status == 'SENT_TO_POS':
            raise ValidationError(
                _("Impossible de rejeter une commande déjà envoyée au POS.")
            )
        self.order_id.write({
            'x_tr_order_status': 'REJECTED',
            'rejection_reason':  self.rejection_reason,
        })