# -*- coding: utf-8 -*-
from . import models
from . import controllers


def post_init_hook(env):
    """Génère les tokens QR pour les employés existants qui n'en ont pas."""
    employees = env['hr.employee'].search([('attendance_qr_token', '=', False)])
    for emp in employees:
        emp.attendance_qr_token = emp._generate_attendance_qr_token()
