# -*- coding: utf-8 -*-
"""L'étape « Servi » est posée à l'installation, sur chaque poste existant."""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    ecrans = env['pos.prep.display'].sudo().search([])
    if not ecrans:
        _logger.info("laresidence_pos_preparation : aucun écran de préparation configuré.")
        return
    ecrans._laresidence_assurer_etape_servi()
    _logger.info(
        "laresidence_pos_preparation : étape « Servi » en place sur %s poste(s) : %s",
        len(ecrans), ", ".join(ecrans.mapped('name')))
