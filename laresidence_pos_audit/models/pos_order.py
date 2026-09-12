# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    audit_count = fields.Integer(string="Événements d'audit", compute='_compute_audit_count')

    @api.depends('pos_reference')
    def _compute_audit_count(self):
        audit = self.env['laresidence.pos.audit']
        for order in self:
            order.audit_count = audit.search_count(
                [('order_reference', '=', order.pos_reference)]) if order.pos_reference else 0

    def action_view_audit(self):
        self.ensure_one()
        controle = self.env['laresidence.pos.audit.acces']
        if controle.code_defini() and not controle.acces_ouvert():
            return {
                'type': 'ir.actions.act_window',
                'name': "Accès au journal d'audit",
                'res_model': 'laresidence.pos.audit.unlock',
                'view_mode': 'form',
                'target': 'new',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': "Journal d'audit — %s" % (self.pos_reference or self.display_name),
            'res_model': 'laresidence.pos.audit',
            'view_mode': 'list,form',
            'domain': [('order_reference', '=', self.pos_reference)],
            'context': {'create': False},
        }
