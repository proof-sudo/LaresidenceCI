# -*- coding: utf-8 -*-
import logging
from collections import OrderedDict

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FactureGroupee(models.TransientModel):
    """Assistant : une facture unique pour plusieurs commandes de caisse."""

    _name = 'laresidence.pos.facture.groupee'
    _description = "Facture groupée des commandes en compte client"

    partner_id = fields.Many2one(
        'res.partner', string="Client", required=True,
        help="Les commandes de ses contacts sont reprises avec les siennes : "
             "la facture est établie au nom de la société.")
    date_debut = fields.Date(string="Du", required=True)
    date_fin = fields.Date(string="Au", required=True,
                           default=lambda self: fields.Date.context_today(self))
    order_ids = fields.Many2many('pos.order', string="Commandes à facturer")
    montant_total = fields.Monetary(
        string="Total à facturer", compute='_compute_montant_total',
        currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string="Devise",
        default=lambda self: self.env.company.currency_id)
    journal_id = fields.Many2one(
        'account.journal', string="Journal de vente",
        domain="[('type', '=', 'sale')]",
        default=lambda self: self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1))

    @api.depends('order_ids')
    def _compute_montant_total(self):
        for fiche in self:
            fiche.montant_total = sum(fiche.order_ids.mapped('amount_total'))

    def _domaine_eligibles(self):
        """Commandes réglées en compte client, non encore facturées.

        Le regroupement se fait sur l'entité commerciale : les commandes
        passées au nom d'un contact remontent avec celles de sa société.
        """
        self.ensure_one()
        societe = self.partner_id.commercial_partner_id
        return [
            ('partner_id.commercial_partner_id', '=', societe.id),
            ('state', 'in', ('paid', 'done', 'invoiced')),
            ('payment_ids.payment_method_id.type', '=', 'pay_later'),
            ('account_move', '=', False),
            ('laresidence_facture_groupee_id', '=', False),
            ('date_order', '>=', self.date_debut),
            ('date_order', '<=', self.date_fin),
        ]

    @api.onchange('partner_id', 'date_debut', 'date_fin')
    def _onchange_selection(self):
        for fiche in self:
            if not (fiche.partner_id and fiche.date_debut and fiche.date_fin):
                fiche.order_ids = False
                continue
            fiche.order_ids = self.env['pos.order'].search(fiche._domaine_eligibles())

    def _compte_produit(self, ligne):
        """Compte de produit de l'article, position fiscale comprise."""
        produit = ligne.product_id
        if not produit:
            return False
        comptes = produit.product_tmpl_id.get_product_accounts(
            fiscal_pos=ligne.order_id.fiscal_position_id)
        return comptes.get('income')

    def _lignes_facture(self):
        """Une ligne par commande, dédoublée si la commande mélange des taxes.

        Le montant repris est le prix de vente que la caisse a elle-même
        utilisé (prix unitaire x quantité, remise déduite), et non le montant
        hors taxes : les taxes 18 % et 9 % étant incluses dans les prix, c'est
        cette valeur que le moteur de taxes attend pour retrouver le total.
        """
        self.ensure_one()
        valeurs = []
        for commande in self.order_ids.sorted('date_order'):
            groupes = OrderedDict()
            for ligne in commande.lines:
                compte = self._compte_produit(ligne)
                if not compte:
                    raise UserError(
                        "L'article « %s » de la commande %s n'a pas de compte de "
                        "produit. Complétez sa catégorie comptable avant de "
                        "relancer la facturation." % (
                            ligne.full_product_name or ligne.product_id.display_name,
                            commande.name))
                cle = (tuple(sorted(ligne.tax_ids_after_fiscal_position.ids)), compte.id)
                montant = ligne.price_unit * ligne.qty * (1 - (ligne.discount or 0.0) / 100.0)
                groupes[cle] = groupes.get(cle, 0.0) + montant
            if not groupes:
                continue
            multiple = len(groupes) > 1
            for (taxes, compte_id), montant in groupes.items():
                libelle = "Ticket %s du %s" % (
                    commande.name,
                    fields.Datetime.context_timestamp(self, commande.date_order).strftime('%d/%m/%Y'))
                if multiple:
                    noms = self.env['account.tax'].browse(list(taxes)).mapped('name')
                    libelle = "%s — %s" % (libelle, ', '.join(noms) or "sans taxe")
                valeurs.append((0, 0, {
                    'name': libelle,
                    'quantity': 1.0,
                    'price_unit': montant,
                    'account_id': compte_id,
                    'tax_ids': [(6, 0, list(taxes))],
                }))
        return valeurs

    def action_generer(self):
        self.ensure_one()
        if not self.order_ids:
            raise UserError("Aucune commande sélectionnée.")
        deja = self.order_ids.filtered(
            lambda c: c.laresidence_facture_groupee_id or c.account_move)
        if deja:
            raise UserError(
                "Ces commandes sont déjà rattachées à une facture : %s"
                % ', '.join(deja.mapped('name')))
        if not self.journal_id:
            raise UserError("Aucun journal de vente n'est disponible.")

        societe = self.partner_id.commercial_partner_id
        facture = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': societe.id,
            'journal_id': self.journal_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': "Point de vente — commandes du %s au %s" % (
                self.date_debut.strftime('%d/%m/%Y'), self.date_fin.strftime('%d/%m/%Y')),
            'invoice_line_ids': self._lignes_facture(),
        })
        self.order_ids.write({'laresidence_facture_groupee_id': facture.id})
        _logger.info(
            "Facture groupée %s créée pour %s : %s commande(s).",
            facture.id, societe.display_name, len(self.order_ids))
        return {
            'type': 'ir.actions.act_window',
            'name': "Facture groupée",
            'res_model': 'account.move',
            'res_id': facture.id,
            'view_mode': 'form',
        }
