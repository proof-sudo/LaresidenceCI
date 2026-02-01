from odoo import models, fields, api
from pytz import UTC

class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.depends('_get_last_session')
    def _compute_last_session(self):
        for pos_config in self:
            session = pos_config._get_last_session()
            if session and session[0]['stop_at']:
                # Convertir avec timezone de l'utilisateur si possible
                tz = self.env.user.tz or 'UTC'
                pos_config.last_session_closing_date = session[0]['stop_at'].astimezone(UTC).date()
            else:
                pos_config.last_session_closing_date = False
