from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    printer_type = fields.Selection(
        selection_add=[
            ('network_escpos', 'Use a network ESC/POS printer'),
        ],
        ondelete={'network_escpos': 'set default'},
    )
    escpos_printer_ip = fields.Char(
        string='Printer IP Address',
        help='IP address of the ESC/POS network printer (e.g. 192.168.1.6)',
        default='0.0.0.0',
    )
    escpos_printer_port = fields.Integer(
        string='Printer Port',
        help='TCP port of the ESC/POS network printer',
        default=9100,
    )
    duplicate_printer_ids = fields.Many2many(
        'pos.printer',
        'pos_printer_duplicate_rel',
        'printer_id',
        'duplicate_printer_id',
        string='Mirror Printers',
        help='Other preparation printers that should also receive a copy of this '
             "printer's tickets. Mirror printers receive the same items based on "
             "this printer's category filter, not their own.",
    )

    @api.constrains('escpos_printer_ip', 'escpos_printer_port')
    def _constrains_escpos_printer(self):
        for record in self:
            if record.printer_type == 'network_escpos':
                if not record.escpos_printer_ip or record.escpos_printer_ip == '0.0.0.0':
                    raise ValidationError(_("Printer IP Address must be configured."))
                if not record.escpos_printer_port or record.escpos_printer_port <= 0:
                    raise ValidationError(_("Printer Port must be a positive number."))

    @api.constrains('duplicate_printer_ids')
    def _constrains_duplicate_printer_ids(self):
        for record in self:
            if record in record.duplicate_printer_ids:
                raise ValidationError(_("A printer cannot mirror to itself."))

    @api.model
    def _load_pos_data_fields(self, config):
        result = super()._load_pos_data_fields(config)
        result += ['escpos_printer_ip', 'escpos_printer_port', 'duplicate_printer_ids']
        return result

    @api.model
    def _load_pos_data_domain(self, data, config):
        base_ids = config.printer_ids.ids
        duplicate_ids = config.printer_ids.mapped('duplicate_printer_ids').ids
        all_ids = list(set(base_ids + duplicate_ids))
        return [('id', 'in', all_ids)]
