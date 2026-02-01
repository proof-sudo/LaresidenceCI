from odoo import models, fields, api

class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.depends('session_ids.stop_at')  # <- dépend des sessions réelles
    def _compute_last_session(self):
        for pos_config in self:
            sessions = pos_config.session_ids.sorted(lambda s: s.stop_at or fields.Datetime.min, reverse=True)
            last_session = sessions[0] if sessions else None
            if last_session and last_session.stop_at:
                pos_config.last_session_closing_date = last_session.stop_at.date()
            else:
                pos_config.last_session_closing_date = False
