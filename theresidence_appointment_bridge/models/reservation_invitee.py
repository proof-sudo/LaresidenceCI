# -*- coding: utf-8 -*-
from odoo import models


class TheResidenceReservationInvitee(models.Model):
    _inherit = 'theresidence.reservation.invitee'

    def _tr_refresh_calendar_event_description(self):
        """Remet à jour la description du calendar.event miroir quand les invités changent."""
        reservations = self.mapped('reservation_id').filtered(
            lambda r: r.x_tr_is_reservation and r.x_tr_calendar_event_id
        )
        for reservation in reservations:
            try:
                reservation.sudo()._sync_update_calendar_event()
            except Exception:
                pass

    def write(self, vals):
        res = super().write(vals)
        self._tr_refresh_calendar_event_description()
        return res

    def create(self, vals_list):
        records = super().create(vals_list)
        records._tr_refresh_calendar_event_description()
        return records

    def unlink(self):
        reservations = self.mapped('reservation_id').filtered(
            lambda r: r.x_tr_is_reservation and r.x_tr_calendar_event_id
        )
        res = super().unlink()
        for reservation in reservations:
            try:
                reservation.sudo()._sync_update_calendar_event()
            except Exception:
                pass
        return res
