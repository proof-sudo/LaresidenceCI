# -*- coding: utf-8 -*-

import logging

from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class HrAttendanceQrController(http.Controller):
    """Endpoint public pour le pointage par QR code."""

    @http.route(
        '/laresidence/attendance/qr/scan/<string:token>',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        website=False,
    )
    def qr_scan(self, token, **kwargs):
        # Validation basique du token (longueur max pour éviter les abus)
        if not token or len(token) > 64:
            return self._html_error('Token invalide.')

        Employee = request.env['hr.employee'].sudo()
        employee = Employee.search(
            [('attendance_qr_token', '=', token)], limit=1
        )

        if not employee:
            return self._html_error(
                'QR code non reconnu. Contactez votre responsable RH.'
            )

        try:
            with request.env.cr.savepoint():
                result = self._toggle_attendance(employee)
        except Exception:
            _logger.exception(
                'hr_attendance_qr: erreur pointage employé id=%s', employee.id
            )
            return self._html_error(
                'Une erreur est survenue. Veuillez réessayer.'
            )

        return self._html_success(
            employee_name=employee.name,
            status=result['status'],
            timestamp=result['timestamp'],
        )

    # ── Logique bascule ───────────────────────────────────────────────────────

    def _toggle_attendance(self, employee):
        Attendance = request.env['hr.attendance'].sudo()
        now = fields.Datetime.now()

        open_attendance = Attendance.search(
            [
                ('employee_id', '=', employee.id),
                ('check_out', '=', False),
            ],
            order='check_in desc',
            limit=1,
        )

        if open_attendance:
            open_attendance.write({'check_out': now})
            _logger.info(
                'QR pointage DÉPART  employé=%s id=%s à %s',
                employee.name, employee.id, now,
            )
            return {'status': 'check_out', 'timestamp': now}
        else:
            Attendance.create({
                'employee_id': employee.id,
                'check_in': now,
            })
            _logger.info(
                'QR pointage ARRIVÉE employé=%s id=%s à %s',
                employee.name, employee.id, now,
            )
            return {'status': 'check_in', 'timestamp': now}

    # ── Pages HTML de réponse ────────────────────────────────────────────────

    def _html_success(self, employee_name, status, timestamp):
        is_checkin = status == 'check_in'
        label = 'Arrivée enregistrée' if is_checkin else 'Départ enregistré'
        icon = '✅' if is_checkin else '👋'
        color = '#28a745' if is_checkin else '#007bff'
        time_str = timestamp.strftime('%H:%M:%S') if timestamp else ''
        date_str = timestamp.strftime('%d/%m/%Y') if timestamp else ''

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>Présence — La Résidence</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f4f6f8;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: #fff;
            border-radius: 16px;
            padding: 40px 32px;
            max-width: 380px;
            width: 100%;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .icon {{ font-size: 64px; margin-bottom: 16px; }}
        .badge {{
            display: inline-block;
            background: {color};
            color: #fff;
            border-radius: 24px;
            padding: 6px 20px;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 20px;
        }}
        h1 {{ font-size: 22px; color: #1a1a2e; margin-bottom: 8px; }}
        .time {{ font-size: 36px; font-weight: 700; color: {color}; margin: 12px 0 4px; }}
        .date {{ font-size: 14px; color: #6c757d; }}
        .footer {{ margin-top: 28px; font-size: 12px; color: #adb5bd; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">{icon}</div>
        <div class="badge">{label}</div>
        <h1>{employee_name}</h1>
        <div class="time">{time_str}</div>
        <div class="date">{date_str}</div>
        <div class="footer">La Résidence — Pointage QR</div>
    </div>
</body>
</html>"""
        return Response(html, content_type='text/html; charset=utf-8', status=200)

    def _html_error(self, message):
        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>Erreur — Présence QR</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f4f6f8;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: #fff;
            border-radius: 16px;
            padding: 40px 32px;
            max-width: 380px;
            width: 100%;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .icon {{ font-size: 64px; margin-bottom: 16px; }}
        h1 {{ font-size: 18px; color: #dc3545; margin-bottom: 12px; }}
        p {{ font-size: 15px; color: #495057; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">❌</div>
        <h1>Accès refusé</h1>
        <p>{message}</p>
    </div>
</body>
</html>"""
        return Response(html, content_type='text/html; charset=utf-8', status=400)
