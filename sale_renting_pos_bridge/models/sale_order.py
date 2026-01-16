from odoo import models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()

        for order in self:
            for line in order.order_line:
                product = line.product_id.product_tmpl_id

                if not product.est_disponible_comme_salle:
                    continue

                floor = product.pos_floor_id
                if not floor:
                    continue

                tables = self.env['restaurant.table'].search([
                    ('floor_id', '=', floor.id),
                    ('is_reserved', '=', False)
                ])

                if not tables:
                    continue

                reservation = self.env['pos.room.reservation'].create({
                    'partner_id': order.partner_id.id,
                    'sale_order_id': order.id,
                    'floor_id': floor.id,
                    'table_ids': [(6, 0, tables.ids)],
                    'date_start': line.start_date,
                    'date_end': line.end_date,
                })

                tables.write({'is_reserved': True})

        return res
