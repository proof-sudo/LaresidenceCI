from odoo import models, fields, api

class PosRoomReservation(models.Model):
    _name = 'pos.room.reservation'
    _description = 'Réservation Salle POS'
    _order = 'date_start desc'

    name = fields.Char(
        required=False,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('pos.room.reservation')
    )

    partner_id = fields.Many2one(
        'res.partner',
        required=False
    )

    sale_order_id = fields.Many2one(
        'sale.order',
        string="Commande de location"
    )

    floor_id = fields.Many2one(
        'restaurant.floor',
        required=False
    )

    table_ids = fields.Many2many(
        'restaurant.table',
        string="Tables réservées"
    )

    date_start = fields.Datetime(required=True)
    date_end = fields.Datetime(required=True)

    state = fields.Selection([
        ('reserved', 'Réservée'),
        ('done', 'Terminée'),
        ('cancel', 'Annulée'),
    ], default='reserved')

    def action_cancel(self):
        for rec in self:
            rec.table_ids.write({'is_reserved': False})
            rec.state = 'cancel'

    def action_done(self):
        for rec in self:
            rec.table_ids.write({'is_reserved': False})
            rec.state = 'done'
