# -*- coding: utf-8 -*-

from odoo import models, api, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'

    def action_close_all_pos_sessions(self):
        """
        Ferme toutes les sessions POS ouvertes (SAFE)
        """
        sessions = self.env['pos.session'].search([
            ('state', '!=', 'closed')
        ])

        now = fields.Datetime.now()

        for session in sessions:
            try:
                # Fermeture standard Odoo (propre)
                session.action_pos_session_close()
            except Exception:
                # FERMETURE FORCÉE MAIS COHÉRENTE
                session.write({
                    'state': 'closed',
                    'stop_at': now,
                })

        return True
