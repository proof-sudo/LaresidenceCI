# -*- coding: utf-8 -*-
"""Détache le groupe du privilège « Point de Vente ».

Le groupe a été créé rattaché à ce privilège. Dans Odoo 19 un privilège
s'affiche en liste déroulante à choix unique : le groupe devenait donc
exclusif de « Utilisateur » et « Administrateur » du Point de Vente. Il
n'apparaissait pas en case à cocher, et le choisir aurait retiré à la
personne ses droits caisse au lieu de lui ajouter un accès.

L'enregistrement est en noupdate : seule une migration peut le corriger.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    groupe = env.ref('laresidence_pos_close.group_pos_close_notified',
                     raise_if_not_found=False)
    if not groupe:
        return
    valeurs = {'name': "Caisse : alertes et déblocage de fermeture"}
    if groupe.privilege_id:
        valeurs['privilege_id'] = False
    groupe.sudo().write(valeurs)
    _logger.info(
        "laresidence_pos_close : groupe détaché du privilège Point de Vente ; "
        "il s'affiche désormais en case à cocher. %s membre(s).",
        len(groupe.user_ids))
