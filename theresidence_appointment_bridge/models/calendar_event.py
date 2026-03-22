# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Mapping appointment_status (calendar.event) → x_tr_reservation_status (sale.order)
APT_STATUS_TO_TR = {
    'booked':    'RESERVED',
    'attended':  'ARRIVED',
    'no_show':   'CANCELLED',
    'cancelled': 'CANCELLED',
}


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    x_tr_reservation_status = fields.Char(
        string='Statut réservation TR',
        compute='_compute_tr_reservation_status',
        store=False,
    )

    def _compute_tr_reservation_status(self):
        for event in self:
            order = self.env['sale.order'].sudo().search([
                ('x_tr_calendar_event_id', '=', event.id),
                ('x_tr_is_reservation', '=', True),
            ], limit=1)
            event.x_tr_reservation_status = order.x_tr_reservation_status if order else False

    def write(self, vals):
        res = super().write(vals)

        # Sync inverse : changement de statut dans le calendrier POS → sale.order
        # Ignoré si c'est notre propre code qui écrit (évite les boucles)
        if self.env.context.get('tr_skip_calendar_sync'):
            return res

        apt_status = vals.get('appointment_status')
        going_inactive = vals.get('active') is False

        if not apt_status and not going_inactive:
            return res

        for event in self:
            order = self.env['sale.order'].sudo().search([
                ('x_tr_calendar_event_id', '=', event.id),
                ('x_tr_is_reservation', '=', True),
            ], limit=1)
            if not order:
                continue

            new_status = None
            if going_inactive:
                # N'écraser que si la réservation est encore active
                # (évite COMPLETED → CANCELLED lors du sync interne qui archive l'event)
                if order.x_tr_reservation_status not in ('COMPLETED', 'CANCELLED'):
                    new_status = 'CANCELLED'
            elif apt_status and apt_status in APT_STATUS_TO_TR:
                new_status = APT_STATUS_TO_TR[apt_status]

            if not new_status or order.x_tr_reservation_status == new_status:
                continue

            # On écrit directement pour éviter la boucle de sync
            # (super().write() sur sale.order déclencherait _sync_update_calendar_event)
            order.sudo().with_context(tr_skip_calendar_sync=True).write({
                'x_tr_reservation_status': new_status,
            })

            _logger.info(
                "[TR BRIDGE] Sync inverse : calendar.event %s → sale.order %s statut %s",
                event.id, order.x_tr_uuid, new_status,
            )

        return res

    # ─────────────────────────────────────────────────────────────
    # Boutons TR dans la vue formulaire POS Appointments
    # ─────────────────────────────────────────────────────────────
    def _get_tr_order(self):
        self.ensure_one()
        return self.env['sale.order'].sudo().search([
            ('x_tr_calendar_event_id', '=', self.id),
            ('x_tr_is_reservation', '=', True),
        ], limit=1)

    def action_tr_reserve(self):
        order = self._get_tr_order()
        if not order:
            raise ValidationError(_("Aucune réservation TR liée à cet événement."))
        order.action_reserve_reservation()

    def action_tr_arrive(self):
        order = self._get_tr_order()
        if not order:
            raise ValidationError(_("Aucune réservation TR liée à cet événement."))
        order.action_arrive_reservation()

    def action_tr_release(self):
        order = self._get_tr_order()
        if not order:
            raise ValidationError(_("Aucune réservation TR liée à cet événement."))
        order.action_release_reservation()

    def action_tr_cancel(self):
        order = self._get_tr_order()
        if not order:
            raise ValidationError(_("Aucune réservation TR liée à cet événement."))
        order.action_cancel_reservation()

    def action_tr_load_to_pos(self):
        order = self._get_tr_order()
        if not order:
            raise ValidationError(_("Aucune réservation TR liée à cet événement."))
        return order.action_load_to_pos()
