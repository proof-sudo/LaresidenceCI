# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosSession(models.Model):
    _inherit = 'pos.session'

    audit_count = fields.Integer(string="Événements d'audit", compute='_compute_audit_count')

    @api.depends('name')
    def _compute_audit_count(self):
        audit = self.env['laresidence.pos.audit']
        for session in self:
            session.audit_count = audit.search_count([('session_id', '=', session.id)])

    def action_view_audit(self):
        self.ensure_one()
        controle = self.env['laresidence.pos.audit.acces']
        if controle._code_defini() and not controle._acces_ouvert():
            return {
                'type': 'ir.actions.act_window',
                'name': "Accès au journal d'audit",
                'res_model': 'laresidence.pos.audit.unlock',
                'view_mode': 'form',
                'target': 'new',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': "Journal d'audit — %s" % self.name,
            'res_model': 'laresidence.pos.audit',
            'view_mode': 'list,form',
            'domain': [('session_id', '=', self.id)],
            'context': {'create': False},
        }
