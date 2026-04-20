# -*- coding: utf-8 -*-

import secrets
import base64
import logging
import io

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    attendance_qr_token = fields.Char(
        string='Token QR Presence',
        copy=False,
        readonly=True,
        index=True,
        groups='hr.group_hr_user',
        help="Token secret encode dans le QR du badge.",
    )

    # store=True  : image persistee en base — disponible sans recalcul au moment du rapport PDF
    # compute_sudo=True : calcul avec droits admin pour acceder a ir.config_parameter
    attendance_qr_image = fields.Binary(
        string='QR Code Presence',
        compute='_compute_attendance_qr_image',
        store=True,
        compute_sudo=True,
        help="Image PNG du QR code.",
    )

    def _generate_attendance_qr_token(self):
        return 'att-' + secrets.token_urlsafe(16)

    @api.depends('attendance_qr_token')
    def _compute_attendance_qr_image(self):
        try:
            import qrcode
        except ImportError:
            _logger.error("laresidence_attendance_qr: pip install qrcode[pil]")
            for emp in self:
                emp.attendance_qr_image = False
            return

        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', default='http://localhost:8069'
        ).rstrip('/')

        for emp in self:
            if not emp.attendance_qr_token:
                emp.attendance_qr_image = False
                continue

            scan_url = f"{base_url}/laresidence/attendance/qr/scan/{emp.attendance_qr_token}"

            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=6,
                border=2,
            )
            qr.add_data(scan_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color='black', back_color='white')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            emp.attendance_qr_image = base64.b64encode(buf.getvalue())

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('attendance_qr_token'):
                vals['attendance_qr_token'] = self._generate_attendance_qr_token()
        return super().create(vals_list)

    def action_regenerate_qr_token(self):
        for emp in self:
            emp.attendance_qr_token = self._generate_attendance_qr_token()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Token QR regenere',
                'message': f"{len(self)} token(s) regenere(s). Imprimez les nouveaux badges.",
                'type': 'success',
                'sticky': False,
            },
        }

    def action_print_attendance_badge(self):
        return self.env.ref(
            'laresidence_attendance_qr.action_report_attendance_badge'
        ).report_action(self)
