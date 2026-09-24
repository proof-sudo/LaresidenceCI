# -*- coding: utf-8 -*-
"""Recalcule les deux indicateurs sur les commandes déjà en base.

Odoo ne recalcule pas un champ stocké parce qu'on a changé sa méthode : les
lignes existantes gardent la valeur écrite lors de l'installation. Constaté
sur demo2 après la correction des commandes annulées — 110 d'entre elles
affichaient encore « Non réglé ».

Ce script force le recalcul une fois, à la mise à jour du module.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    commandes = env['pos.order'].search([])
    if not commandes:
        return

    for nom in ('laresidence_statut_facture', 'laresidence_reglement'):
        env.add_to_compute(commandes._fields[nom], commandes)
    commandes.flush_recordset()

    _logger.info(
        "laresidence_pos_facturation : statut de facturation et règlement "
        "recalculés sur %s commande(s) de caisse.", len(commandes))
