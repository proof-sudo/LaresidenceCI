# -*- coding: utf-8 -*-
"""Recalcul forcé du constat de présence sur les créneaux de planning.

Corriger la logique d'un champ calculé **stocké** ne corrige pas ce qui est
déjà en base : Odoo ne recalcule que les enregistrements qu'on lui signale.
Après la mise à jour précédente, les 2 171 créneaux antérieurs continuaient
d'afficher « Conforme » alors que la règle qui produisait cette valeur avait
été retirée.

Ce script rattrape l'existant, une fois. Les créneaux créés ou modifiés
ensuite se calculent normalement.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    creneaux = env['planning.slot'].search([])
    if not creneaux:
        return
    creneaux.modified(['laresidence_exception_ids'])
    creneaux.flush_recordset()
    _logger.info("laresidence_hr_control : constat de présence recalculé sur %s créneau(x)",
                 len(creneaux))
