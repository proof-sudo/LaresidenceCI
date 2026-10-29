from odoo import models, fields, _


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string="Bon de commande",
        readonly=True,
        copy=False,
        ondelete='set null',
    )

    def write(self, vals):
        res = super().write(vals)
        if 'request_status' not in vals:
            return res

        for req in self.filtered(lambda r: r.purchase_order_id):
            po = req.purchase_order_id
            if req.request_status == 'approved' and po.state == 'draft':
                po.with_context(skip_approval_check=True).button_confirm()
                po.message_post(
                    body=_(
                        "Bon de commande confirmé automatiquement après approbation "
                        "de la demande <b>%s</b>."
                    ) % req.name
                )

            elif req.request_status == 'refused':
                po.message_post(
                    body=_(
                        "La demande d'approbation <b>%s</b> a été refusée. "
                        "Le bon de commande reste en brouillon."
                    ) % req.name
                )

        return res
