# -*- coding: utf-8 -*-
"""Mise en place à l'installation.

Deux choses : l'étape « Servi » sur chaque poste, et le rattrapage des plats
déjà en cours au moment où le module arrive. Sans ce rattrapage, un plat
envoyé en cuisine avant l'installation n'aurait aucun passage d'ouverture :
son historique commencerait au milieu, et le temps écoulé depuis l'envoi
serait perdu.
"""

import logging

from odoo import fields

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

    _rattraper_suivis_en_cours(env)


def _rattraper_suivis_en_cours(env):
    """Ouvre un passage pour les plats déjà en cuisine à l'installation.

    L'heure retenue est celle qu'Odoo a lui-même enregistrée au dernier
    changement d'étape : rien n'est inventé. Les étapes antérieures, elles,
    sont définitivement perdues — elles n'ont jamais été consignées.
    """
    Passage = env['laresidence.prep.passage'].sudo()
    etats = env['pos.prep.state'].sudo().search([('stage_id', '!=', False)])
    if not etats:
        return

    deja = set(Passage.search([]).mapped('prep_state_id').ids)
    valeurs = []
    for etat in etats:
        if etat.id in deja:
            continue
        ecran = etat.stage_id.prep_display_id
        terminal = ecran and etat.stage_id == ecran.laresidence_stage_servi_id
        debut = etat.last_stage_change or etat.create_date or fields.Datetime.now()
        valeurs.append({
            'prep_state_id': etat.id,
            'stage_id': etat.stage_id.id,
            'date_debut': debut,
            'date_fin': debut if terminal else False,
        })

    if not valeurs:
        return
    Passage.create(valeurs)
    _logger.info(
        "laresidence_pos_preparation : %s plat(s) déjà en préparation rattaché(s) "
        "au suivi, à partir de leur dernier changement d'étape.", len(valeurs))
