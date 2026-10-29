from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    fne_tax_code = fields.Selection(
        selection=[
            ('TVA', "TVA normale (18 %)"),
            ('TVAB', "TVA réduite (9 %)"),
            ('TVAC', "TVA exonérée par convention (0 %)"),
            ('TVAD', "TVA exonérée légale (0 %)"),
        ],
        string="Code FNE",
        help="Code de TVA envoyé à la FNE pour cette taxe. Prioritaire sur la "
             "détection automatique (nom / taux). Une taxe sans code reconnu "
             "est envoyée comme taxe personnalisée.",
    )
