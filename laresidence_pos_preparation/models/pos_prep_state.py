# -*- coding: utf-8 -*-
"""Le point d'accroche : chaque changement d'étape ferme un passage et en ouvre un.

Le contrôle de cohérence est posé ici, côté serveur, et pas seulement sur
l'écran de caisse : une tablette qui a perdu le réseau peut envoyer une
validation périmée, et un bouton grisé ne l'en empêcherait pas.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosPrepState(models.Model):
    _inherit = 'pos.prep.state'

    # ------------------------------------------------------------------
    # Historisation
    # ------------------------------------------------------------------
    def _laresidence_passage_ouvert(self):
        """Le passage non clôturé de ce suivi, s'il y en a un."""
        self.ensure_one()
        return self.env['laresidence.prep.passage'].sudo().search([
            ('prep_state_id', '=', self.id),
            ('date_fin', '=', False),
        ], order='date_debut desc, id desc', limit=1)

    def _laresidence_ouvrir_passage(self, horodatage=None):
        Passage = self.env['laresidence.prep.passage'].sudo()
        horodatage = horodatage or fields.Datetime.now()
        force = bool(self.env.context.get('laresidence_force_servi'))
        valeurs = []
        for etat in self:
            if not etat.stage_id:
                continue
            # « Servi » est un état terminal, pas une durée : son passage est
            # clos dès sa création. Sans cela, tout plat servi resterait
            # indéfiniment « étape en cours » dans les filtres et l'analyse.
            terminal = etat.stage_id == etat.stage_id.prep_display_id.laresidence_stage_servi_id
            valeurs.append({
                'prep_state_id': etat.id,
                'stage_id': etat.stage_id.id,
                'date_debut': horodatage,
                'date_fin': horodatage if terminal else False,
                'user_id': self.env.user.id,
                'force': force,
            })
        if valeurs:
            Passage.create(valeurs)
        return True

    def _laresidence_fermer_passage(self, horodatage=None):
        horodatage = horodatage or fields.Datetime.now()
        for etat in self:
            passage = etat._laresidence_passage_ouvert()
            if passage:
                passage.write({'date_fin': horodatage})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        etats = super().create(vals_list)
        etats._laresidence_ouvrir_passage()
        return etats

    def write(self, vals):
        if 'stage_id' not in vals:
            return super().write(vals)

        avant = {etat.id: etat.stage_id.id for etat in self}
        resultat = super().write(vals)
        maintenant = fields.Datetime.now()
        for etat in self:
            if avant.get(etat.id) == etat.stage_id.id:
                continue
            etat._laresidence_fermer_passage(maintenant)
            etat._laresidence_ouvrir_passage(maintenant)
        return resultat

    # ------------------------------------------------------------------
    # Service en salle
    # ------------------------------------------------------------------
    def _laresidence_etat_servi(self):
        self.ensure_one()
        ecran = self.stage_id.prep_display_id
        return ecran.laresidence_stage_servi_id

    def _laresidence_pret_a_servir(self):
        """Vrai si la cuisine a réellement marqué ce plat prêt."""
        self.ensure_one()
        ecran = self.stage_id.prep_display_id
        if not ecran:
            return False
        return self.stage_id == ecran._laresidence_stage_passe()

    @api.model
    def laresidence_statuts(self, line_uuids):
        """État de préparation des lignes désignées, pour l'écran de caisse.

        La caisse ne charge pas les modèles de préparation : elle demande cet
        état au moment où le serveur ouvre l'écran de service. Cela évite
        d'alourdir le démarrage de la caisse, et surtout d'y toucher.
        """
        if not line_uuids:
            return {}
        etats = self.sudo().search([
            ('prep_line_id.pos_order_line_uuid', 'in', list(line_uuids)),
        ])
        maintenant = fields.Datetime.now()
        resultat = {}
        for etat in etats:
            ecran = etat.stage_id.prep_display_id
            etape_servi = ecran.laresidence_stage_servi_id
            passage = etat._laresidence_passage_ouvert()
            depuis = 0.0
            if passage and passage.date_debut:
                depuis = (maintenant - passage.date_debut).total_seconds() / 60.0
            resultat[etat.prep_line_id.pos_order_line_uuid] = {
                'etape': etat.stage_id.name or '',
                'poste': ecran.name or '',
                'pret': etat._laresidence_pret_a_servir(),
                'servi': bool(etape_servi) and etat.stage_id == etape_servi,
                'depuis': round(depuis, 1),
                'seuil': etat.stage_id.alert_timer or 0,
            }
        return resultat

    @api.model
    def laresidence_marquer_servi(self, line_uuids, forcer=False):
        """Déclare servis les plats désignés par leurs lignes de caisse.

        Renvoie ce qui a été fait et ce qui a été refusé, plutôt que de lever
        une erreur sur le lot entier : en plein service, un plat encore en
        cuisson ne doit pas empêcher de valider les trois autres.
        """
        if not line_uuids:
            return {'servis': [], 'refuses': [], 'forces': []}

        etats = self.sudo().search([
            ('prep_line_id.pos_order_line_uuid', 'in', list(line_uuids)),
        ])
        servis, refuses, forces = [], [], []

        for etat in etats:
            uuid = etat.prep_line_id.pos_order_line_uuid
            etape_servi = etat._laresidence_etat_servi()
            if not etape_servi:
                refuses.append({'uuid': uuid, 'motif': _("Poste sans étape « Servi »")})
                continue
            if etat.stage_id == etape_servi:
                continue  # déjà servi, rien à refaire
            if not etat._laresidence_pret_a_servir():
                if not forcer:
                    refuses.append({
                        'uuid': uuid,
                        'motif': _("Plat encore à l'étape « %s »", etat.stage_id.name or ''),
                        'etape': etat.stage_id.name or '',
                    })
                    continue
                forces.append(uuid)

            etat.with_context(
                laresidence_force_servi=uuid in forces,
            ).write({
                'stage_id': etape_servi.id,
                'todo': False,
                'last_stage_change': fields.Datetime.now(),
            })
            servis.append(uuid)

        if forces:
            _logger.info(
                "laresidence_pos_preparation : %s plat(s) déclaré(s) servis sans "
                "passage au passe par %s", len(forces), self.env.user.login)

        return {'servis': servis, 'refuses': refuses, 'forces': forces}

    def action_laresidence_marquer_servi(self):
        """Même opération depuis le back-office, sur un suivi sélectionné."""
        for etat in self:
            if not etat._laresidence_pret_a_servir():
                raise UserError(_(
                    "Ce plat est encore à l'étape « %(etape)s ». Il ne peut être "
                    "déclaré servi que lorsque la cuisine l'a marqué prêt.",
                    etape=etat.stage_id.name or '',
                ))
        uuids = self.mapped('prep_line_id.pos_order_line_uuid')
        return self.laresidence_marquer_servi(uuids)
