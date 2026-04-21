# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request
from odoo.addons.hr_attendance.controllers.main import HrAttendance

_logger = logging.getLogger(__name__)


class HrAttendanceQr(HrAttendance):
    """Étend le contrôleur kiosque pour reconnaître les tokens QR att-..."""

    @http.route('/hr_attendance/attendance_barcode_scanned', type="json", auth="public")
    def scan_barcode(self, token, barcode):
        if barcode and barcode.startswith('att-'):
            company = self._get_company(token)
            if not company:
                return {}
            employee = request.env['hr.employee'].sudo().search(
                [('attendance_qr_token', '=', barcode), ('company_id', '=', company.id)],
                limit=1,
            )
            if not employee:
                return {}
            employee._attendance_action_change(self._get_geoip_response('kiosk'))
            return self._get_employee_info_response(employee)
        return super().scan_barcode(token=token, barcode=barcode)
