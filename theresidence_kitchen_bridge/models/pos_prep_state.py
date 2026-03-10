# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class PosPrepState(models.Model):
    _inherit = 'pos.prep.state'

    def change_state_status(self, todos, prep_display_id):
        """
        Surcharge : quand tous les articles d'une commande mobile TR sont marqués
        prêts en cuisine (todo=False), on passe le statut CONFIRMED → READY
        et on déclenche le webhook.
        """
        res = super().change_state_status(todos, prep_display_id)

        # Récupérer les pos.order affectés par ce changement d'état
        pos_orders = self.mapped('prep_line_id.prep_order_id.pos_order_id')

        for pos_order in pos_orders.filtered(
            lambda o: getattr(o, 'x_tr_is_mobile_order', False)
                      and o.x_tr_order_status == 'CONFIRMED'
        ):
            # Vérifier si TOUS les prep.state de cette commande sont done (todo=False)
            prep_orders = self.env['pos.prep.order'].search([
                ('pos_order_id', '=', pos_order.id),
            ])
            all_prep_lines = prep_orders.mapped('prep_line_ids')
            all_states = self.env['pos.prep.state'].search([
                ('prep_line_id', 'in', all_prep_lines.ids),
            ])

            if all_states and all(not s.todo for s in all_states):
                old = pos_order.x_tr_order_status
                pos_order.with_context(tr_skip_order_sync=True).write({
                    'x_tr_order_status': 'READY',
                })
                try:
                    self.env['theresidence.webhook'].trigger_event(
                        'ORDER_STATUS_CHANGED', 'order', pos_order.x_tr_uuid,
                        pos_order.to_order_api_dict(), old, 'READY',
                    )
                except Exception as e:
                    _logger.warning(
                        "[TR KITCHEN] Webhook échec (prêt cuisine) commande %s : %s",
                        pos_order.x_tr_uuid, e,
                    )

        return res
