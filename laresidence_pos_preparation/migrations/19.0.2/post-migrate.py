# -*- coding: utf-8 -*-
"""Rattrape les postes installés avant que l'ordre des étapes ne soit figé.

Le crochet d'installation ne rejoue pas à la mise à jour : sans ce script,
un poste déjà pourvu de son étape « Servi » garderait des étapes toutes à la
séquence 0, et le garde-fou du service continuerait de dépendre des
identifiants.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    ecrans = env['pos.prep.display'].search([])
    if not ecrans:
        return
    ecrans._laresidence_assurer_etape_servi()
    _logger.info(
        "laresidence_pos_preparation : ordre des \u00e9tapes fig\u00e9 sur %s poste(s).",
        len(ecrans))
