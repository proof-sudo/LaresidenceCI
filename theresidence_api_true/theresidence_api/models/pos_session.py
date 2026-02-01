from odoo import models, fields, api
from datetime import datetime, timezone

class PosConfig(models.Model):
    _inherit = 'pos.config'

    # Champ existant, recalculé de manière safe
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

    @api.depends('session_ids.stop_at')  # on dépend des sessions réelles
    def _compute_last_session(self):
        for pos in self:
            # trier les sessions par stop_at décroissant
            sessions = pos.session_ids.sorted(
                key=lambda s: s.stop_at if s.stop_at else datetime(1970, 1, 1, tzinfo=timezone.utc),
                reverse=True
            )
            last_session = sessions[0] if sessions else None
            if last_session and last_session.stop_at:
                pos.last_session_closing_date = last_session.stop_at.date()
            else:
                pos.last_session_closing_date = False

    @api.depends('session_ids.stop_at')  # idem pour le cash
    def _compute_last_session_cash(self):
        for pos in self:
            sessions = pos.session_ids.sorted(
                key=lambda s: s.stop_at if s.stop_at else datetime(1970, 1, 1, tzinfo=timezone.utc),
                reverse=True
            )
            last_session = sessions[0] if sessions else None
            if last_session and last_session.stop_at:
                pos.last_session_closing_cash = last_session.stop_at.date()
            else:
                pos.last_session_closing_cash = False
