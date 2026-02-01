# -*- coding: utf-8 -*-

from odoo import models, api

class PosConfig(models.Model):
    _inherit = 'pos.config'

    def action_close_all_pos_sessions(self):
        """
        Bouton UI : ferme TOUTES les sessions POS ouvertes
        """
        sessions = self.env['pos.session'].search([
            ('state', '!=', 'closed')
        ])

        for session in sessions:
            try:
                # Fermeture standard Odoo
                session.action_pos_session_close()
            except Exception:
                # Sécurité : forcer si bloquée
                session.write({'state': 'closed'})

        return True
