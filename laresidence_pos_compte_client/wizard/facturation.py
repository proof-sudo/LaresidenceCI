# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class Facturation(models.TransientModel):
    """Écran guidé pour facturer un compte client.

    Ne refait pas la facturation : il prépare la sélection, prévient de ce
    qui mérite un regard, puis confie le travail à l'assistant natif
    ``pos.make.invoice``, qui produit la facture, extourne l'écriture de
    clôture des sessions fermées et valide la pièce.
    """

    _name = 'laresidence.pos.facturation'
    _description = "Facturer un compte client"

    partner_id = fields.Many2one(
        'res.partner', string="Client", required=True,
        help="Les commandes de ses contacts sont proposées avec les siennes.")
    date_debut = fields.Date(string="Du", required=True)
    date_fin = fields.Date(
        string="Au", required=True,
        default=lambda self: fields.Date.context_today(self))
    order_ids = fields.Many2many('pos.order', string="Consommations à facturer")
    regrouper_societe = fields.Boolean(
        string="Établir une facture unique au nom de la société",
        help="Sans cette option, une consommation enregistrée au nom d'un "
             "contact donne une facture distincte de celle de sa société.")
    montant_total = fields.Monetary(
        string="Total", compute='_compute_synthese', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    avertissement = fields.Text(compute='_compute_synthese')

    @api.model
    def _methodes_differe(self):
        """pos.payment.method.type est calculé et non stocké : on résout en Python."""
        return self.env['pos.payment.method'].search([]).filtered(
            lambda m: m.type == 'pay_later')

    def _domaine_eligibles(self):
        self.ensure_one()
        societe = self.partner_id.commercial_partner_id
        return [
            ('partner_id.commercial_partner_id', '=', societe.id),
            ('state', 'in', ('paid', 'done')),
            ('payment_ids.payment_method_id', 'in', self._methodes_differe().ids),
            ('account_move', '=', False),
            ('laresidence_regularisee', '=', False),
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

    @api.depends('order_ids', 'regrouper_societe')
    def _compute_synthese(self):
        """Annonce à l'avance ce qui empêchera une facture unique.

        Odoo regroupe sur la clé (point de vente, client, vendeur, position
        fiscale). Deux causes de découpage se rencontrent ici : des
        consommations réparties sur la société et ses contacts, que l'option
        ci-contre résout ; et des positions fiscales différentes, qu'il ne
        faut surtout pas forcer — la position « National » remappe les taxes,
        donc fusionner produirait une facture fausse.
        """
        for fiche in self:
            fiche.montant_total = sum(fiche.order_ids.mapped('amount_total'))
            messages = []
            fiches_clients = fiche.order_ids.mapped('partner_id')
            if len(fiches_clients) > 1 and not fiche.regrouper_societe:
                messages.append(
                    "Ces consommations sont réparties sur %s fiches : %s.\n"
                    "En l'état, Odoo produira une facture par fiche. Cochez "
                    "l'option ci-dessous pour n'en avoir qu'une, au nom de la "
                    "société — les commandes concernées seront alors "
                    "rattachées à la société."
                    % (len(fiches_clients), ', '.join(fiches_clients.mapped('display_name'))))
            positions = {c.fiscal_position_id for c in fiche.order_ids}
            if len(positions) > 1:
                noms = sorted(p.display_name if p else "aucune position fiscale"
                              for p in positions)
                messages.append(
                    "Ces consommations relèvent de positions fiscales "
                    "différentes : %s.\n"
                    "Odoo produira une facture par position, et c'est "
                    "volontaire : une position fiscale remappe les taxes, les "
                    "réunir donnerait une facture fausse. Si ces commandes "
                    "auraient dû relever de la même position, c'est la fiche "
                    "des commandes qu'il faut corriger, pas la facture."
                    % ', '.join(noms))
            fiche.avertissement = '\n\n'.join(messages) or False

    def action_facturer(self):
        self.ensure_one()
        if not self.order_ids:
            raise UserError("Aucune consommation sélectionnée.")
        deja = self.order_ids.filtered(lambda c: c.account_move or c.laresidence_regularisee)
        if deja:
            raise UserError(
                "Ces commandes sont déjà facturées ou régularisées : %s"
                % ', '.join(deja.mapped('name')))

        if self.regrouper_societe:
            societe = self.partner_id.commercial_partner_id
            a_rattacher = self.order_ids.filtered(lambda c: c.partner_id != societe)
            if a_rattacher:
                _logger.info(
                    "Facturation compte client : %s commande(s) rattachée(s) à %s par %s.",
                    len(a_rattacher), societe.display_name, self.env.user.login)
                a_rattacher.write({'partner_id': societe.id})

        # Le travail est confié à l'assistant natif : facture, extourne des
        # écritures de clôture et validation sont de son ressort.
        contexte = {'active_ids': self.order_ids.ids, 'active_model': 'pos.order'}
        assistant = self.env['pos.make.invoice'].with_context(**contexte).create({
            'consolidated_billing': True,
        })
        return assistant.with_context(**contexte).action_create_invoices()
