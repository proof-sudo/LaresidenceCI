# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    x_tr_uuid = fields.Char(string='UUID TR', copy=False, readonly=True, index=True)
    x_tr_is_mobile_order = fields.Boolean(string='Commande mobile TR', default=False)
    x_tr_order_status = fields.Selection([
        ('PENDING', 'En attente'),
        ('CONFIRMED', 'Confirmée'),
        ('READY', 'Prête'),
        ('COMPLETED', 'Terminée'),
        ('CANCELLED', 'Annulée'),
    ], string='Statut', default='PENDING')
    x_tr_order_mode = fields.Selection([
        ('PICKUP', 'Retrait'),
        ('DELIVERY', 'Livraison'),
        ('DINE_IN', 'Sur place'),
    ], string='Mode', default='PICKUP')
    x_tr_delivery_address = fields.Text(string='Adresse livraison')
    x_tr_qr_token = fields.Char(string='Token QR', copy=False)
    x_tr_member_id = fields.Many2one('res.partner', string='Membre', domain=[('x_tr_is_member', '=', True)])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('x_tr_is_mobile_order') and not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())
                vals['x_tr_qr_token'] = f"order-{uuid.uuid4().hex[:12]}"
        return super().create(vals_list)

    def to_order_api_dict(self):
        self.ensure_one()
        member = self.x_tr_member_id or self.partner_id
        
        items = [{
            'id': str(line.id),
            'menuItemId': str(line.product_id.id),
            'menuItemName': line.product_id.name or '',
            'quantity': line.qty,
            'unitPrice': line.price_unit,
            'amount': line.price_subtotal_incl
        } for line in self.lines]
        
        return {
            'id': self.x_tr_uuid or str(self.id),
            'memberId': member.x_tr_uuid if member else '',
            'memberFirstName': (member.name or '').split(' ')[0] if member else '',
            'memberLastName': ' '.join((member.name or '').split(' ')[1:]) if member else '',
            'memberEmail': member.email if member else '',
            'mode': self.x_tr_order_mode or 'PICKUP',
            'status': self.x_tr_order_status or 'PENDING',
            'totalAmount': self.amount_total or 0.0,
            'currency': self.currency_id.name if self.currency_id else 'XOF',
            'qrToken': self.x_tr_qr_token or '',
            'deliveryAddress': self.x_tr_delivery_address or '',
            'items': items,
            'notes': self.note or '',
            'createdAt': self.create_date.isoformat() if self.create_date else '',
            'updatedAt': self.write_date.isoformat() if self.write_date else ''
        }

    @api.model
    def create_order_from_api(self, data):
        member = None
        if data.get('memberId'):
            member = self.env['res.partner'].search([('x_tr_uuid', '=', data['memberId'])], limit=1)
        
        session = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
        if not session:
            raise ValidationError(_("Aucune session POS active."))
        amount_total = sum(
    item.get('quantity', 1) * item.get('unitPrice', 0)
    for item in data.get('items', [])
)
        order = self.create({
                'session_id': session.id,
                'partner_id': member.id if member else False,
                'x_tr_is_mobile_order': True,
                'x_tr_order_status': 'PENDING',
                'x_tr_order_mode': data.get('mode', 'PICKUP'),
                'x_tr_delivery_address': data.get('deliveryAddress', ''),
                'x_tr_member_id': member.id if member else False,
                'amount_tax': 0.0,
                'amount_total': amount_total,
                'amount_paid': 0.0,
                'amount_return': 0.0,
            })
        

        
        for item in data.get('items', []):
            product = self.env['product.product'].browse(int(item['menuItemId']))
            if product.exists():
                self.env['pos.order.line'].create({
                    'order_id': order.id,
                    'product_id': product.id,
                    'qty': item.get('quantity', 1),
                    'price_unit': item.get('unitPrice', product.lst_price),
                    'price_subtotal': item.get('quantity', 1) * item.get('unitPrice', product.lst_price),
                    'price_subtotal_incl': item.get('quantity', 1) * item.get('unitPrice', product.lst_price),
                })
        order._compute_prices()
        self.env['theresidence.webhook'].trigger_event(
            'ORDER_CREATED', 'order', order.x_tr_uuid,
            order.to_order_api_dict(), None, 'PENDING'
        )
        return order

    def action_confirm_order(self):
        for order in self:
            if order.x_tr_order_status != 'PENDING':
                raise ValidationError(_("Seules les commandes en attente peuvent être confirmées."))
            old = order.x_tr_order_status
            order.x_tr_order_status = 'CONFIRMED'
            self.env['theresidence.webhook'].trigger_event(
                'ORDER_STATUS_CHANGED', 'order', order.x_tr_uuid,
                order.to_order_api_dict(), old, 'CONFIRMED'
            )

    def action_ready_order(self):
        for order in self:
            if order.x_tr_order_status != 'CONFIRMED':
                raise ValidationError(_("Seules les commandes confirmées peuvent être marquées prêtes."))
            old = order.x_tr_order_status
            order.x_tr_order_status = 'READY'
            self.env['theresidence.webhook'].trigger_event(
                'ORDER_STATUS_CHANGED', 'order', order.x_tr_uuid,
                order.to_order_api_dict(), old, 'READY'
            )

    def action_complete_order(self):
        for order in self:
            if order.x_tr_order_status != 'READY':
                raise ValidationError(_("Seules les commandes prêtes peuvent être terminées."))
            old = order.x_tr_order_status
            order.x_tr_order_status = 'COMPLETED'
            self.env['theresidence.webhook'].trigger_event(
                'ORDER_STATUS_CHANGED', 'order', order.x_tr_uuid,
                order.to_order_api_dict(), old, 'COMPLETED'
            )

    def action_cancel_order(self, reason=None):
        for order in self:
            if order.x_tr_order_status == 'COMPLETED':
                raise ValidationError(_("Les commandes terminées ne peuvent pas être annulées."))
            old = order.x_tr_order_status
            order.x_tr_order_status = 'CANCELLED'
            self.env['theresidence.webhook'].trigger_event(
                'ORDER_CANCELLED', 'order', order.x_tr_uuid,
                order.to_order_api_dict(), old, 'CANCELLED'
            )
