# -*- coding: utf-8 -*-
from odoo import fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # --- Régularisation ------------------------------------------------
    # Odoo interdit de repasser une commande payée à l'état « annulé » :
    # le noyau n'autorise que paid, done et invoiced. On marque donc la
    # commande comme régularisée, ce qui dit la vérité — elle a existé,
    # elle a été extournée — au lieu de réécrire son état.
    laresidence_regularisee = fields.Boolean(
        string="Régularisée", readonly=True, copy=False, index=True,
        help="La commande a été extournée par un avoir.")
    laresidence_avoir_id = fields.Many2one(
        'account.move', string="Avoir d'extourne",
        readonly=True, copy=False, ondelete='set null')
    laresidence_regularisation_motif = fields.Char(
        string="Motif de régularisation", readonly=True, copy=False)
    laresidence_regularisation_date = fields.Datetime(
        string="Régularisée le", readonly=True, copy=False)
    laresidence_regularisation_user_id = fields.Many2one(
        'res.users', string="Régularisée par", readonly=True, copy=False)

    # --- Traçabilité des lignes de facture -----------------------------
    def _get_invoice_lines_values(self, line_values, line, move_type):
        """Ajoute la date de consommation et la référence du ticket.

        Odoo sait regrouper plusieurs commandes de caisse sur une facture
        unique, mais il se contente d'empiler les articles : rien ne dit de
        quel jour ni de quel ticket vient chaque ligne. Sur une facture qui
        couvre un mois de consommations, quatre articles identiques se
        suivent sans qu'on puisse les rattacher à un repas.

        Le complément est porté par le libellé de la ligne, et non par un
        intertitre, pour deux raisons : le libellé survit à n'importe quel
        modèle d'impression, et c'est lui que le connecteur DGI transmet
        comme description de l'article — un intertitre, dépourvu d'article,
        n'est pas envoyé du tout.
        """
        valeurs = super()._get_invoice_lines_values(line_values, line, move_type)
        libelle = valeurs.get('name') or (line.product_id and line.product_id.display_name)
        if not libelle:
            return valeurs
        repere = self._laresidence_repere_ticket()
        if repere and repere not in libelle:
            valeurs['name'] = "%s — %s" % (libelle, repere)
        return valeurs

    def _laresidence_repere_ticket(self):
        """« 27/07/2026, ticket Desk - 000144 », dans le fuseau de l'utilisateur."""
        self.ensure_one()
        if not self.date_order:
            return self.name or ""
        jour = fields.Datetime.context_timestamp(self, self.date_order).strftime('%d/%m/%Y')
        if not self.name or self.name == '/':
            return jour
        return "%s, ticket %s" % (jour, self.name)
