# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def sync_from_ui(self, orders):
        """
        Surcharge : pour les commandes mobiles TR envoyées en cuisine,
        on passe PENDING → CONFIRMED AVANT que super().sync_from_ui()
        n'exécute ses writes (qui déclencheraient des webhooks avec le
        statut PENDING encore en place).
        """
        if self.env.context.get('preparation'):
            for order_data in orders:
                pos_uuid = order_data.get('uuid')
                if not pos_uuid:
                    continue
                order = self.sudo().search([
                    ('uuid', '=', pos_uuid),
                    ('x_tr_is_mobile_order', '=', True),
                    ('x_tr_order_status', '=', 'PENDING'),
                ], limit=1)
                if not order:
                    continue

                old = order.x_tr_order_status
                order.with_context(tr_skip_order_sync=True).write({
                    'x_tr_order_status': 'CONFIRMED',
                })
                _logger.info(
                    "[TR KITCHEN] sync_from_ui : commande %s PENDING → CONFIRMED (avant sync)",
                    order.x_tr_uuid,
                )
                try:
                    self.env['theresidence.webhook'].trigger_event(
                        'ORDER_STATUS_CHANGED', 'order', order.x_tr_uuid,
                        order.to_order_api_dict(), old, 'CONFIRMED',
                    )
                except Exception as e:
                    _logger.warning(
                        "[TR KITCHEN] Webhook échec (pre-sync) commande %s : %s",
                        order.x_tr_uuid, e,
                    )

        return super().sync_from_ui(orders)
