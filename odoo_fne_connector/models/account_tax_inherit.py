from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    fne_tax_code = fields.Selection(
        selection=[
            ('TVA', "TVA normale (18 %)"),
            ('TVAB', "TVA réduite (9 %)"),
            ('TVAC', "TVAC - Exonération conventionnelle (0 %)"),
            ('TVAD', "TVAD - Exonération légale (0 %)"),
        ],
        string="Code FNE",
        help="Code de TVA envoyé à la FNE (DGI) pour cette taxe.\n"
             "- TVA : taux normal 18 %.\n"
             "- TVAB : taux réduit 9 %.\n"
             "- TVAC : opération exonérée en vertu d'une convention (0 %).\n"
             "- TVAD : opération exonérée par la loi, par exemple la main d'oeuvre (0 %).\n"
             "La FNE n'accepte pas de ligne « sans TVA » : une ligne non taxée doit "
             "porter une taxe à 0 % avec le code TVAC ou TVAD.\n"
             "Une taxe à 0 % sans code est bloquée à la certification : "
             "choisissez TVAD (exonération prévue par la loi) ou TVAC (prévue par une convention).",
    )
