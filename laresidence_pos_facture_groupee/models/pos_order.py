# -*- coding: utf-8 -*-
from odoo import fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    laresidence_facture_groupee_id = fields.Many2one(
        'account.move',
        string="Facture groupée",
        readonly=True, copy=False, index=True, ondelete='set null',
        help="Facture unique qui couvre cette commande, avec d'autres commandes "
             "du même client réglées en compte client.")

    # --- Régularisation ------------------------------------------------
    # Odoo interdit de repasser une commande payée à l'état « annulé » :
    # le noyau n'autorise que paid, done et invoiced. On marque donc la
    # commande comme régularisée, ce qui dit la vérité — elle a existé,
    # elle a été extournée — au lieu de réécrire son état.
    laresidence_regularisee = fields.Boolean(
        string="Régularisée", readonly=True, copy=False, index=True,
        help="La commande a été extournée par un avoir. Elle ne peut plus "
             "être facturée.")
    laresidence_avoir_id = fields.Many2one(
        'account.move', string="Avoir d'extourne",
        readonly=True, copy=False, ondelete='set null')
    laresidence_regularisation_motif = fields.Char(
        string="Motif de régularisation", readonly=True, copy=False)
    laresidence_regularisation_date = fields.Datetime(
        string="Régularisée le", readonly=True, copy=False)
    laresidence_regularisation_user_id = fields.Many2one(
        'res.users', string="Régularisée par", readonly=True, copy=False)
