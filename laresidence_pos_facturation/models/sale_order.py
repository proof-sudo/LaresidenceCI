# -*- coding: utf-8 -*-
"""Empêche qu'une commande de caisse soit comptée deux fois sur son devis.

Le standard ``pos_sale`` ajoute la quantité et le montant des lignes de caisse
à ce qui est déjà facturé sur la ligne de vente. Tant que la facture n'est pas
rattachée au devis, ce calcul est juste. Dès qu'on la rattache — ce que fait
``pos_order.py`` — la même quantité arrive par deux chemins et le devis
repasse en « à facturer », ce qui invite à émettre une seconde facture.

Mesuré sur une commande de 10 unités : quantité facturée 10 → 20, montant HT
33 898 → 67 796, statut « facturé » → « à facturer ».

Deux corrections ici :

1. on retire l'apport des lignes de caisse **déjà facturées**, puisque leur
   facture les porte désormais ;
2. on retire aussi celui des commandes en brouillon ou annulées, que le
   standard oublie de filtrer sur les montants — une commande simplement
   ouverte en caisse suffisait à ramener le reste à facturer du devis à zéro.
"""
from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _laresidence_lignes_a_retirer(self, sur_montant=False):
        """Lignes de caisse dont l'apport ferait double emploi.

        :param sur_montant: True pour le calcul des montants, qui doit en plus
            écarter les brouillons et les annulées.
        """
        self.ensure_one()
        lignes = self.sudo().pos_order_line_ids
        if sur_montant:
            return lignes.filtered(
                lambda l: l.order_id.account_move
                or l.order_id.state in ('draft', 'cancel'))
        return lignes.filtered(
            lambda l: l.order_id.account_move
            and l.order_id.state not in ('draft', 'cancel'))

    @api.depends('pos_order_line_ids.order_id.account_move')
    def _compute_qty_invoiced(self):
        super()._compute_qty_invoiced()

    def _prepare_qty_invoiced(self):
        quantites = super()._prepare_qty_invoiced()
        for ligne in self:
            doublons = ligne._laresidence_lignes_a_retirer()
            if not doublons:
                continue
            quantites[ligne] -= sum(
                (self._convert_qty(ligne, caisse.qty, 'p2s') for caisse in doublons), 0)
        return quantites

    @api.depends('pos_order_line_ids.order_id.account_move',
                 'pos_order_line_ids.order_id.state')
    def _compute_untaxed_amount_invoiced(self):
        super()._compute_untaxed_amount_invoiced()
        for ligne in self:
            doublons = ligne._laresidence_lignes_a_retirer(sur_montant=True)
            if doublons:
                ligne.untaxed_amount_invoiced -= sum(doublons.mapped('price_subtotal'))


class SaleOrder(models.Model):
    """Même correction, au niveau du devis.

    ``pos_sale`` retranche du reste à facturer le montant de toutes les lignes
    de caisse rattachées. Une fois la facture reliée au devis, ce montant est
    retiré deux fois : le reste à facturer devient négatif et le devis se
    déclare « à facturer » alors qu'il ne l'est plus.

    Mesuré sur un devis de 8 625 : reste à facturer −8 625 avant cette
    correction, 0 après.

    ``amount_unpaid`` n'est pas corrigé ici : le calcul standard le borne à
    zéro, ce qui rend toute reprise après coup fausse dans un sens ou dans
    l'autre. Il reste juste dans le cas courant — devis entièrement consommé
    en caisse — et c'est un champ de paiement en ligne, non utilisé ici.
    """

    _inherit = 'sale.order'

    @api.depends('order_line.pos_order_line_ids.order_id.account_move',
                 'order_line.pos_order_line_ids.order_id.state')
    def _compute_amount_to_invoice(self):
        super()._compute_amount_to_invoice()
        for commande in self:
            lignes = commande.sudo().pos_order_line_ids.filtered(
                lambda l: l.order_id.account_move
                or l.order_id.state in ('draft', 'cancel'))
            # Le standard exclut déjà les acomptes facturés : ne pas les
            # remettre, ils n'ont jamais été retranchés.
            lignes = lignes.filtered(
                lambda l: not (l.sale_order_line_id.is_downpayment and any(
                    aml.move_id.state == 'posted'
                    for aml in l.sale_order_line_id.invoice_lines)))
            if lignes:
                commande.amount_to_invoice += sum(lignes.mapped('price_subtotal_incl'))
