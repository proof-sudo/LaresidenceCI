# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class PosPrepState(models.Model):
    _inherit = 'pos.prep.state'

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers communs
    # ─────────────────────────────────────────────────────────────────────────

    def _tr_check_and_mark_ready(self, pos_orders):
        """
        Pour chaque pos.order mobile TR en statut CONFIRMED,
        vérifie si tous les articles sont terminés en cuisine.
        Si oui → READY + webhook.
        """
        for pos_order in pos_orders.filtered(
            lambda o: getattr(o, 'x_tr_is_mobile_order', False)
                      and o.x_tr_order_status == 'CONFIRMED'
        ):
            prep_orders = self.env['pos.prep.order'].search([
                ('pos_order_id', '=', pos_order.id),
            ])
            all_prep_lines = prep_orders.mapped('prep_line_ids')
            all_states = self.env['pos.prep.state'].search([
                ('prep_line_id', 'in', all_prep_lines.ids),
            ])

            _logger.info(
                "[TR KITCHEN] Commande %s — %d états, todo: %s",
                pos_order.x_tr_uuid,
                len(all_states),
                [s.todo for s in all_states],
            )

            if all_states and all(not s.todo for s in all_states):
                old = pos_order.x_tr_order_status
                pos_order.with_context(tr_skip_order_sync=True).write({
                    'x_tr_order_status': 'READY',
                })
                _logger.info(
                    "[TR KITCHEN] Commande %s → READY (webhook)",
                    pos_order.x_tr_uuid,
                )
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

    # ─────────────────────────────────────────────────────────────────────────
    # Hook 1 : toggle todo (cuisine simple 1 stage)
    # ─────────────────────────────────────────────────────────────────────────

    def change_state_status(self, todos, prep_display_id):
        res = super().change_state_status(todos, prep_display_id)

        pos_orders = self.mapped('prep_line_id.prep_order_id.pos_order_id')
        _logger.info(
            "[TR KITCHEN] change_state_status → %d commandes POS trouvées, mobiles: %s",
            len(pos_orders),
            [o.x_tr_is_mobile_order for o in pos_orders],
        )
        self._tr_check_and_mark_ready(pos_orders)
        return res

    # ─────────────────────────────────────────────────────────────────────────
    # Hook 2 : changement de stage (cuisine multi-stages)
    # Quand tous les articles atteignent le dernier stage, c'est "prêt"
    # ─────────────────────────────────────────────────────────────────────────

    def change_state_stage(self, stages, prep_display_id):
        res = super().change_state_stage(stages, prep_display_id)

        pos_orders = self.mapped('prep_line_id.prep_order_id.pos_order_id')
        _logger.info(
            "[TR KITCHEN] change_state_stage → %d commandes POS trouvées, mobiles: %s",
            len(pos_orders),
            [o.x_tr_is_mobile_order for o in pos_orders],
        )

        for pos_order in pos_orders.filtered(
            lambda o: getattr(o, 'x_tr_is_mobile_order', False)
                      and o.x_tr_order_status == 'CONFIRMED'
        ):
            prep_orders = self.env['pos.prep.order'].search([
                ('pos_order_id', '=', pos_order.id),
            ])
            all_prep_lines = prep_orders.mapped('prep_line_ids')
            all_states = self.env['pos.prep.state'].search([
                ('prep_line_id', 'in', all_prep_lines.ids),
            ])

            # Tous au dernier stage = prêt
            if all_states and all(s.stage_id.is_stage_position(-1) for s in all_states):
                old = pos_order.x_tr_order_status
                pos_order.with_context(tr_skip_order_sync=True).write({
                    'x_tr_order_status': 'READY',
                })
                _logger.info(
                    "[TR KITCHEN] Commande %s → READY via stage final (webhook)",
                    pos_order.x_tr_uuid,
                )
                try:
                    self.env['theresidence.webhook'].trigger_event(
                        'ORDER_STATUS_CHANGED', 'order', pos_order.x_tr_uuid,
                        pos_order.to_order_api_dict(), old, 'READY',
                    )
                except Exception as e:
                    _logger.warning(
                        "[TR KITCHEN] Webhook échec (stage final) commande %s : %s",
                        pos_order.x_tr_uuid, e,
                    )

        return res
