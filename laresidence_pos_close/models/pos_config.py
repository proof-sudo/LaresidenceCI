# -*- coding: utf-8 -*-
from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    auto_close_enabled = fields.Boolean(
        string="Fermeture automatique de la caisse", default=False,
        help="Verrouille la session à l'heure indiquée, à condition que plus rien "
             "ne soit en cours. Dans le cas contraire, une alerte est envoyée et "
             "la session reste ouverte.")
    auto_close_time = fields.Float(
        string="Heure de fermeture", default=3.0,
        help="Heure locale à partir de laquelle la fermeture est tentée, "
             "par exemple 3,0 pour 03h00.")
    auto_close_idle_minutes = fields.Integer(
        string="Délai d'inactivité (min)", default=30,
        help="Aucune fermeture tant qu'une commande a été créée dans ce délai. "
             "Protège contre une fermeture pendant qu'une tablette synchronise encore.")
    auto_close_block_on_prep = fields.Boolean(
        string="Les bons de préparation bloquent", default=True,
        help="Si coché, une ligne encore en attente sur un écran cuisine ou bar "
             "empêche la fermeture — y compris à l'étape « À envoyer », un plat "
             "prêt mais pas encore servi.")
    auto_close_full = fields.Boolean(
        string="Tenter la clôture comptable", default=False,
        help="Par défaut la session est seulement verrouillée : plus aucune commande "
             "ne peut y être prise, et le comptage de caisse se fait au matin. "
             "Cochez pour tenter en plus la clôture comptable complète — à réserver "
             "aux points de vente sans espèces, sous peine de valider un comptage "
             "que personne n'a fait.")

    auto_close_last_attempt = fields.Datetime(string="Dernière tentative", readonly=True)
    auto_close_last_result = fields.Char(string="Dernier résultat", readonly=True)
