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
        copy=False,
        readonly=True,
        index=True,
        groups='hr.group_hr_user',
    )

    # Champ binaire simple stocké — pas de compute, généré explicitement
    attendance_qr_image = fields.Binary(
        copy=False,
        groups='hr.group_hr_user',
    )

    def _generate_attendance_qr_token(self):
        return 'att-' + secrets.token_urlsafe(16)

    def _generate_qr_image(self, token):
        try:
            import qrcode
        except ImportError:
            _logger.error("laresidence_attendance_qr: pip install qrcode[pil]")
            return False

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(token)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue())

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('attendance_qr_token'):
                vals['attendance_qr_token'] = self._generate_attendance_qr_token()
        records = super().create(vals_list)
        for rec in records:
            try:
                rec.attendance_qr_image = rec._generate_qr_image(rec.attendance_qr_token)
            except Exception:
                _logger.exception("Erreur génération QR employé id=%s", rec.id)
        return records
