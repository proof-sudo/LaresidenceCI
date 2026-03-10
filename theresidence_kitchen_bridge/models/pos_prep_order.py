# -*- coding: utf-8 -*-
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class PosPrepOrder(models.Model):
    _inherit = 'pos.prep.order'

    @api.model
    def process_order(self, order_id, options={}):
        """
        Surcharge : quand une commande mobile TR est envoyée en cuisine,
        on passe son statut de PENDING → CONFIRMED et on déclenche le webhook.
        """
        res = super().process_order(order_id, options)

        # Commandes annulées : pas de changement de statut
        if options.get('cancelled'):
            return res

        order = self.env['pos.order'].browse(order_id)
        if not order or not getattr(order, 'x_tr_is_mobile_order', False):
            return res

        if order.x_tr_order_status == 'PENDING':
            old = order.x_tr_order_status
            order.with_context(tr_skip_order_sync=True).write({
                'x_tr_order_status': 'CONFIRMED',
            })
            try:
                self.env['theresidence.webhook'].trigger_event(
                    'ORDER_STATUS_CHANGED', 'order', order.x_tr_uuid,
                    order.to_order_api_dict(), old, 'CONFIRMED',
                )
            except Exception as e:
                _logger.warning(
                    "[TR KITCHEN] Webhook échec (envoi cuisine) commande %s : %s",
                    order.x_tr_uuid, e,
                )

        return res
