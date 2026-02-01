# -*- coding: utf-8 -*-

from odoo import models, api

class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def action_close_all_pos_sessions(self):
        """
        Ferme toutes les sessions POS non fermées
        """
        sessions = self.search([('state', '!=', 'closed')])

        for session in sessions:
            try:
                session.action_pos_session_close()
            except Exception:
                # fallback si la fermeture standard échoue
                session.write({'state': 'closed'})

        return True
