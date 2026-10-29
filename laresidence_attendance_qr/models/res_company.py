# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    attendance_kiosk_mode = fields.Selection(
        selection_add=[('barcode_qr', 'Badge code-barres / QR Code (tablette)')],
        ondelete={'barcode_qr': 'set default'},
    )
