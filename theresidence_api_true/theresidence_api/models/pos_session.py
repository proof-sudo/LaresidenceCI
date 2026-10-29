from odoo import models, fields, api
from datetime import datetime, timezone

class PosConfig(models.Model):
    _inherit = 'pos.config'

    last_session_closing_date = fields.Date(
        string="Last Session Closing Date",
        compute='_compute_last_session',
        store=True
    )

    last_session_closing_cash = fields.Date(
        string="Last Session Closing Cash",
        compute='_compute_last_session_cash',
        store=True
    )

    # Date minimale pour trier les sessions sans stop_at
    MIN_DATETIME = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def _safe_dt(self, dt):
        """Convertit une datetime en UTC aware, ou renvoie MIN_DATETIME si vide"""
        if not dt:
            return self.MIN_DATETIME
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @api.depends('session_ids.stop_at')
    def _compute_last_session(self):
        for pos in self:
            # Trier les sessions par stop_at décroissant
            sessions = pos.session_ids.sorted(
                key=lambda s: self._safe_dt(s.stop_at),
                reverse=True
            )
            last_session = sessions[0] if sessions else None
            if last_session and last_session.stop_at:
                pos.last_session_closing_date = last_session.stop_at.date()
            else:
                pos.last_session_closing_date = False

    @api.depends('session_ids.stop_at')
    def _compute_last_session_cash(self):
        for pos in self:
            sessions = pos.session_ids.sorted(
                key=lambda s: self._safe_dt(s.stop_at),
                reverse=True
            )
            last_session = sessions[0] if sessions else None
            if last_session and last_session.stop_at:
                pos.last_session_closing_cash = last_session.stop_at.date()
            else:
                pos.last_session_closing_cash = False
