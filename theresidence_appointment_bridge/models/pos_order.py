# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') in ('paid', 'done'):
            for order in self:
                self._cancel_reservation_picking(order)
        return res

    def _cancel_reservation_picking(self, pos_order):
        """
        Quand une commande POS liée à une réservation est payée,
        annule le bon de livraison de la sale.order correspondante.
        Le POS gère lui-même les sorties de stock — on évite la double déduction.
        """
        sale_order = self.env['sale.order'].sudo().search([
            ('x_tr_pos_order_id', '=', pos_order.id),
            ('x_tr_is_reservation', '=', True),
        ], limit=1)
        if not sale_order:
            return

        pickings_to_cancel = sale_order.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel')
        )
        if not pickings_to_cancel:
            return

        for picking in pickings_to_cancel:
            try:
                picking.sudo().action_cancel()
                _logger.info(
                    "[TR BRIDGE] stock.picking %s annulé (réservation %s payée dans le POS)",
                    picking.name, sale_order.x_tr_uuid,
                )
            except Exception as e:
                _logger.warning(
                    "[TR BRIDGE] Impossible d'annuler le picking %s : %s",
                    picking.name, str(e),
                )
