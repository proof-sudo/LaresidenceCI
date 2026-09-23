# -*- coding: utf-8 -*-
import logging

from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)

STATUTS = [
    ('aucune', "Aucune facture liée"),
    ('a_faire', "Facture FNE à réaliser"),
    ('odoo_faite', "Facture Odoo faite"),
    ('fne_faite', "Facture FNE réalisée"),
]

REGLEMENTS = [
    ('non', "Non réglé"),
    ('partiel', "Réglé partiellement"),
    ('total', "Réglé en totalité"),
]


class PosOrder(models.Model):
    """La caisse enregistre une demande, la comptabilité produit la facture.

    Un seul champ porte l'avancement, et il ne se contredit jamais : les deux
    premiers états viennent du comptoir, les deux derniers se lisent sur la
    facture. Personne n'a donc à tenir ce statut à jour à la main — c'est la
    seule façon qu'il reste vrai au bout de trois mois.
    """

    _inherit = 'pos.order'

    laresidence_facture_demandee = fields.Boolean(
        string="Facture demandée en caisse", copy=False, index=True,
        help="Posé au comptoir quand le client demande une facture. "
             "Le caissier peut passer la question : le champ reste alors faux.")

    laresidence_statut_facture = fields.Selection(
        STATUTS, string="Statut de facturation", default='aucune',
        compute='_compute_laresidence_statut_facture', store=True, index=True)

    @api.depends('laresidence_facture_demandee', 'account_move',
                 'account_move.state', 'account_move.fne_sent')
    def _compute_laresidence_statut_facture(self):
        for commande in self:
            facture = commande.account_move
            if facture and facture.state == 'posted':
                commande.laresidence_statut_facture = (
                    'fne_faite' if facture.fne_sent else 'odoo_faite')
            elif commande.laresidence_facture_demandee:
                commande.laresidence_statut_facture = 'a_faire'
            else:
                commande.laresidence_statut_facture = 'aucune'

    laresidence_reglement = fields.Selection(
        REGLEMENTS, string="Règlement", default='non',
        compute='_compute_laresidence_reglement', store=True, index=True,
        help="Dit si l'argent est rentré, ce que le statut de facturation ne "
             "dit pas : une commande en compte client est « payée » en caisse "
             "alors que le client doit encore.")

    @api.depends('amount_total', 'currency_id',
                 'payment_ids', 'payment_ids.amount',
                 'payment_ids.payment_method_id',
                 'account_move', 'account_move.state',
                 'account_move.amount_residual', 'account_move.amount_total')
    def _compute_laresidence_reglement(self):
        """Une facture fait foi ; sinon on regarde ce qui est entré en caisse.

        Le paiement « Compte client » n'est pas un encaissement : il ouvre une
        créance. Une commande réglée ainsi reste donc non réglée tant que sa
        facture n'est pas payée — c'est toute la différence entre l'état de la
        caisse et l'état du compte du client.
        """
        for commande in self:
            devise = commande.currency_id or commande.company_id.currency_id
            facture = commande.account_move
            if facture and facture.state == 'posted':
                restant, reference = facture.amount_residual, facture.amount_total
            else:
                differes = commande.payment_ids.payment_method_id.filtered(
                    lambda m: m.type == 'pay_later')
                encaisse = sum(commande.payment_ids.filtered(
                    lambda p: p.payment_method_id not in differes).mapped('amount'))
                restant, reference = commande.amount_total - encaisse, commande.amount_total

            if not devise or devise.is_zero(restant):
                commande.laresidence_reglement = 'total'
            elif devise.compare_amounts(restant, reference) >= 0:
                commande.laresidence_reglement = 'non'
            else:
                commande.laresidence_reglement = 'partiel'

    def _get_invoice_lines_values(self, line_values, line, move_type):
        """Rattache la ligne de facture à la ligne de devis dont elle provient.

        Le standard recopie le libellé et l'analytique de la ligne de vente mais
        laisse la facture orpheline : le devis affiche 0 facture alors que la
        pièce existe et porte sa référence. On pose ici le lien qui manque.

        Ce lien seul ferait compter la quantité deux fois — une fois par la
        facture, une fois par ``pos_sale``. La soustraction correspondante est
        faite dans ``sale_order.py`` ; les deux vont ensemble.
        """
        valeurs = super()._get_invoice_lines_values(line_values, line, move_type)
        if line.sale_order_line_id:
            valeurs['sale_line_ids'] = [Command.set(line.sale_order_line_id.ids)]
        return valeurs
