from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    escpos_receipt_printer_ip = fields.Char(
        string='ESC/POS Receipt Printer IP',
        help='IP address of the ESC/POS network receipt printer (e.g. 192.168.1.6)',
    )
    escpos_receipt_printer_port = fields.Integer(
        string='ESC/POS Receipt Printer Port',
        help='TCP port of the ESC/POS network receipt printer',
        default=9100,
    )
