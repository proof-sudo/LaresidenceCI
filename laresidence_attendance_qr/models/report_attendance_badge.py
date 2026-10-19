# -*- coding: utf-8 -*-
from odoo import models


class AttendanceBadgeReport(models.AbstractModel):
    _name = 'report.laresidence_attendance_qr.print_employee_badge_custom'
    _description = 'Badge QR Présence'

    def _get_report_values(self, docids, data=None):
        employees = self.env['hr.employee'].sudo().browse(docids)
        for emp in employees:
            if not emp.attendance_qr_token:
                token = emp._generate_attendance_qr_token()
                emp.write({
                    'attendance_qr_token': token,
                    'attendance_qr_image': emp._generate_qr_image(token),
                })
            elif not emp.attendance_qr_image:
                emp.write({
                    'attendance_qr_image': emp._generate_qr_image(emp.attendance_qr_token),
                })
        return {
            'doc_ids': docids,
            'doc_model': 'hr.employee',
            'docs': employees,
        }
