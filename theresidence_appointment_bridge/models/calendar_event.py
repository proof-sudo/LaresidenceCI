# -*- coding: utf-8 -*-
import logging
from odoo import models, api

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

    def write(self, vals):
        res = super().write(vals)

        # Sync inverse : changement de statut dans le calendrier POS → sale.order
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
