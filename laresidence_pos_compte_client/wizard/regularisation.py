# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class Regularisation(models.TransientModel):
    """Extourne des commandes de caisse par un avoir client.

    La caisse impute toutes les méthodes de règlement — espèces, carte et
    compte client — au compte de tiers 411100, tiers renseigné. L'avoir au
    client est donc la contrepartie correcte dans tous les cas ; seule la
    suite diffère : les lignes « compte client » sont ouvertes et se soldent
    directement, celles déjà lettrées demandent un rapprochement manuel avec
    l'écriture d'origine.
    """

    _name = 'laresidence.pos.regularisation'
    _description = "Régularisation de commandes de caisse"

    order_ids = fields.Many2many(
        'pos.order', string="Commandes à régulariser", required=True)
    motif = fields.Char(
        string="Motif", required=True,
        help="Conservé sur chaque commande et repris sur l'avoir.")
    journal_id = fields.Many2one(
        'account.journal', string="Journal de vente",
        domain="[('type', '=', 'sale')]",
        default=lambda self: self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1))
    montant_total = fields.Monetary(
        string="Total à extourner", compute='_compute_montant_total',
        currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    avertissement = fields.Text(compute='_compute_avertissement')

    @api.depends('order_ids')
    def _compute_montant_total(self):
        for fiche in self:
            fiche.montant_total = sum(fiche.order_ids.mapped('amount_total'))

    @api.depends('order_ids')
    def _compute_avertissement(self):
        """Signale les commandes dont le règlement est déjà lettré."""
        for fiche in self:
            lettrees = fiche.order_ids.filtered(
                lambda c: any(
                    p.payment_method_id.type != 'pay_later' for p in c.payment_ids))
            if lettrees:
                fiche.avertissement = (
                    "Ces commandes ont été réglées autrement qu'en compte client : %s.\n"
                    "Leur ligne de tiers est déjà lettrée : l'avoir créera un solde "
                    "créditeur qu'il faudra rapprocher à la main de l'écriture d'origine, "
                    "et l'encaissement correspondant reste à défaire."
                    % ', '.join(lettrees.mapped('name')))
            else:
                fiche.avertissement = False

    @api.model
    def default_get(self, champs):
        valeurs = super().default_get(champs)
        actifs = self.env.context.get('active_ids')
        if actifs and self.env.context.get('active_model') == 'pos.order':
            valeurs['order_ids'] = [(6, 0, actifs)]
        return valeurs

    def _lignes_avoir(self, commande):
        """Reprend les lignes de la commande, article par article.

        En reprenant les articles d'origine, Odoo retrouve seul les comptes
        de produit et les taxes : l'avoir tombe sur le montant encaissé.
        """
        valeurs = []
        for ligne in commande.lines:
            valeurs.append((0, 0, {
                'product_id': ligne.product_id.id,
                'quantity': ligne.qty,
                'price_unit': ligne.price_unit,
                'discount': ligne.discount or 0.0,
                'tax_ids': [(6, 0, ligne.tax_ids_after_fiscal_position.ids)],
            }))
        return valeurs

    def _lettrer(self, commande, avoir):
        """Solde l'avoir contre la créance ouverte de la commande.

        La caisse impute le règlement différé au compte de tiers, sous le
        libellé « <session> - <mode de règlement> ». On ne rapproche que
        lorsqu'une seule ligne ouverte correspond, au nom du même tiers et
        pour le montant exact : en cas de doute on s'abstient et on le
        journalise, plutôt que de solder la mauvaise créance.
        """
        ligne_avoir = avoir.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable' and not l.reconciled)
        if len(ligne_avoir) != 1:
            return False
        candidates = self.env['account.move.line'].search([
            ('account_id', '=', ligne_avoir.account_id.id),
            ('partner_id', '=', ligne_avoir.partner_id.id),
            ('parent_state', '=', 'posted'),
            ('reconciled', '=', False),
            ('debit', '=', commande.amount_total),
            ('move_id', '=', commande.session_id.move_id.id),
        ])
        if len(candidates) != 1:
            _logger.info(
                "Régularisation de %s : lettrage non fait, %s créance(s) "
                "correspondante(s) au lieu d'une.", commande.name, len(candidates))
            return False
        (ligne_avoir | candidates).reconcile()
        _logger.info("Régularisation de %s : avoir %s lettré contre la créance.",
                     commande.name, avoir.name)
        return True

    def action_regulariser(self):
        self.ensure_one()
        if not self.journal_id:
            raise UserError("Aucun journal de vente n'est disponible.")
        deja = self.order_ids.filtered('laresidence_regularisee')
        if deja:
            raise UserError(
                "Ces commandes sont déjà régularisées : %s" % ', '.join(deja.mapped('name')))
        sans_client = self.order_ids.filtered(lambda c: not c.partner_id)
        if sans_client:
            raise UserError(
                "Sans client, l'avoir n'a pas de destinataire. Commandes concernées : %s"
                % ', '.join(sans_client.mapped('name')))
        # Une commande déjà facturée ne porte plus sa créance à la caisse :
        # c'est la facture qui la porte. L'extourner ici créerait un avoir
        # sans contrepartie à solder, et la facture resterait due.
        facturees = self.order_ids.filtered('account_move')
        if facturees:
            raise UserError(
                "Ces commandes sont déjà facturées : %s.\n\n"
                "Leur montant est porté par la facture, plus par la caisse. "
                "Pour les annuler, passez par un avoir sur la facture "
                "elle-même (%s), ce qu'Odoo fait nativement."
                % (', '.join(facturees.mapped('name')),
                   ', '.join(facturees.mapped('account_move.name'))))

        avoirs = self.env['account.move']
        maintenant = fields.Datetime.now()
        for commande in self.order_ids:
            avoir = self.env['account.move'].create({
                'move_type': 'out_refund',
                'partner_id': commande.partner_id.id,
                'journal_id': self.journal_id.id,
                'invoice_date': fields.Date.context_today(self),
                'ref': "Extourne %s" % commande.name,
                'invoice_origin': "Commande point de vente %s — %s" % (commande.name, self.motif),
                'invoice_line_ids': self._lignes_avoir(commande),
            })
            commande.write({
                'laresidence_regularisee': True,
                'laresidence_avoir_id': avoir.id,
                'laresidence_regularisation_motif': self.motif,
                'laresidence_regularisation_date': maintenant,
                'laresidence_regularisation_user_id': self.env.user.id,
            })
            avoir.action_post()
            self._lettrer(commande, avoir)
            avoirs |= avoir
            _logger.info(
                "Régularisation de %s par %s : avoir %s — %s",
                commande.name, self.env.user.login, avoir.name, self.motif)

        return {
            'type': 'ir.actions.act_window',
            'name': "Avoirs d'extourne",
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', avoirs.ids)],
        }
