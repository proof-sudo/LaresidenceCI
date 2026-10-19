# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    exception_count = fields.Integer(string="Écarts à examiner", compute='_compute_exception_count')

    @api.depends('name')
    def _compute_exception_count(self):
        modele = self.env['laresidence.hr.exception']
        for employee in self:
            employee.exception_count = modele.search_count([
                ('employee_id', '=', employee.id),
                ('state', '=', 'to_review'),
            ])

    def action_view_exceptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Écarts de présence — %s" % self.name,
            'res_model': 'laresidence.hr.exception',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'create': False, 'search_default_to_review': 1},
        }
