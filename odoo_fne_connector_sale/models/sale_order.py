from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    fne_objet_marche = fields.Char(
        string="Objet du marché",
        copy=True,
        help="Repris automatiquement sur les factures créées depuis ce devis "
             "(modifiable sur la facture) et envoyé à la FNE dans le "
             "« Message commercial ».",
    )

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.fne_objet_marche:
            vals['fne_objet_marche'] = self.fne_objet_marche
        return vals
