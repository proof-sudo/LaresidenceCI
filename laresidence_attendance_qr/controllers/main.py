# -*- coding: utf-8 -*-
import re
import logging
from odoo import http
from odoo.http import request
from odoo.addons.hr_attendance.controllers.main import HrAttendance

_logger = logging.getLogger(__name__)

_QR_URL_RE = re.compile(r'/laresidence/attendance/qr/scan/(att-[A-Za-z0-9_-]+)')


class HrAttendanceQr(HrAttendance):
    """Étend le contrôleur kiosque pour reconnaître les tokens QR att-..."""

    @http.route('/hr_attendance/attendance_barcode_scanned', type="jsonrpc", auth="public")
    def scan_barcode_with_geolocation(self, token, barcode, latitude=False, longitude=False):
        qr_token = self._extract_qr_token(barcode)
        if qr_token:
            company = self._get_company(token)
            if not company:
                return {}
            employee = request.env['hr.employee'].sudo().search(
                [('attendance_qr_token', '=', qr_token), ('company_id', '=', company.id)],
                limit=1,
            )
            if not employee:
                return {}
            employee._attendance_action_change(
                self._get_geoip_response('kiosk', latitude=latitude, longitude=longitude,
                                         device_tracking_enabled=company.attendance_device_tracking)
            )
            return self._get_employee_info_response(employee)
        return super().scan_barcode_with_geolocation(token=token, barcode=barcode,
                                                     latitude=latitude, longitude=longitude)

    @staticmethod
    def _extract_qr_token(barcode):
        """Retourne le token att-... depuis un token brut ou une URL legacy."""
        if not barcode:
            return None
        if barcode.startswith('att-'):
            return barcode.strip()
        m = _QR_URL_RE.search(barcode)
        return m.group(1) if m else None
