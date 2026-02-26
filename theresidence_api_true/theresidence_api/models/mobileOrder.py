from odoo import models, fields, api
from odoo.exceptions import ValidationError

class MobileOrder(models.Model):
    _name = "mobile.order"
    _description = "Commande Mobile"
    _inherit = 'pos.order'  

    x_tr_order_status = fields.Selection(selection_add=[
        ('SENT_TO_POS', 'Envoyée au POS')
    ], default='PENDING', string="Statut commande mobile")

    def action_validate(self):
        for order in self:
            if order.x_tr_order_status != 'PENDING':
                raise ValidationError("Seules les commandes PENDING peuvent être validées.")
            order.x_tr_order_status = 'CONFIRMED'


    def action_send_to_pos(self):
        PosOrder = self.env['pos.order']
        for order in self:
            if order.x_tr_order_status != 'CONFIRMED':
                raise ValidationError("Seules les commandes CONFIRME peuvent être envoyées au POS.")
            pos_vals = order._prepare_pos_order_valeur()
            PosOrder.create(pos_vals)
            order.x_tr_order_status = 'SENT_TO_POS'

    def _prepare_pos_order_valeur(self):
        lines = [(0, 0, {
            'product_id': line.product_id.id,
            'qty': line.qty,
            'price_unit': line.price_unit,
            'discount': line.discount,
            'tax_ids': [(6, 0, line.tax_ids.ids)],
        }) for line in self.lines]

        vals = {
            'partner_id': self.partner_id.id,
            'date_order': self.date_order,
            'lines': lines,
            'session_id': self.session_id.id or self.env['pos.session'].search([], limit=1).id,
            'note': self.note or '',
            'x_tr_order_mode': self.x_tr_order_mode or 'PICKUP',
            'x_tr_order_status': 'PENDING',  # POS aura son statut initial
            'x_tr_member_id': self.x_tr_member_id.id if self.x_tr_member_id else False,
            'x_tr_uuid': self.x_tr_uuid or '',
            'x_tr_qr_token': self.x_tr_qr_token or '',
            'amount_total': self.amount_total,
            'amount_tax': self.amount_tax,
        }
        return vals

class MobileOrderLine(models.Model):
    _name = "mobile.order.line"
    _inherit = "pos.order.line"  # Hérite directement pour avoir tous les champs POS

    mobile_order_id = fields.Many2one('mobile.order', string="Commande Mobile", required=True)