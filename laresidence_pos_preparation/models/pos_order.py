# -*- coding: utf-8 -*-
"""La synthèse au niveau de la commande, pour la salle et pour l'analyse."""

from odoo import api, fields, models

STATUTS = [
    ('aucun', "Pas de préparation"),
    ('envoye', "Envoyé en cuisine"),
    ('en_cours', "En préparation"),
    ('a_envoyer', "Prêt à envoyer"),
    ('servi', "Servi"),
]


class PosOrder(models.Model):
    _inherit = 'pos.order'

    laresidence_passage_ids = fields.One2many(
        'laresidence.prep.passage', 'pos_order_id', string="Suivi de préparation")

    laresidence_temps_service = fields.Float(
        string="Temps de service (min)",
        compute='_compute_laresidence_preparation', store=True,
        help="De l'envoi en cuisine du premier plat au service du dernier.")
    laresidence_nb_plats = fields.Integer(
        string="Plats suivis", compute='_compute_laresidence_preparation', store=True)
    laresidence_nb_hors_delai = fields.Integer(
        string="Plats hors délai", compute='_compute_laresidence_preparation', store=True)
    laresidence_prep_statut = fields.Selection(
        STATUTS, string="Préparation", default='aucun',
        compute='_compute_laresidence_preparation', store=True, index=True)

    @api.depends('laresidence_passage_ids',
                 'laresidence_passage_ids.date_debut',
                 'laresidence_passage_ids.date_fin',
                 'laresidence_passage_ids.depassement',
                 'laresidence_passage_ids.stage_id')
    def _compute_laresidence_preparation(self):
        for commande in self:
            passages = commande.laresidence_passage_ids
            if not passages:
                commande.laresidence_temps_service = 0.0
                commande.laresidence_nb_plats = 0
                commande.laresidence_nb_hors_delai = 0
                commande.laresidence_prep_statut = 'aucun'
                continue

            commande.laresidence_nb_plats = len(set(passages.mapped('prep_line_id').ids))
            commande.laresidence_nb_hors_delai = len(
                set(passages.filtered('depassement').mapped('prep_line_id').ids))

            # Temps de service : du tout premier envoi au dernier service.
            # Tant qu'un plat n'est pas servi, le chrono reste ouvert et le
            # champ vaut zéro : une moyenne calculée sur des services
            # incomplets serait trompeuse.
            debuts = passages.mapped('date_debut')
            etapes_servi = passages.mapped('display_id.laresidence_stage_servi_id')
            servis = passages.filtered(lambda p: p.stage_id in etapes_servi)
            lignes = set(passages.mapped('prep_line_id').ids)
            lignes_servies = set(servis.mapped('prep_line_id').ids)

            if lignes and lignes_servies >= lignes and debuts:
                commande.laresidence_temps_service = (
                    max(servis.mapped('date_debut')) - min(debuts)).total_seconds() / 60.0
            else:
                commande.laresidence_temps_service = 0.0

            commande.laresidence_prep_statut = commande._laresidence_statut_depuis(passages)

    def _laresidence_statut_depuis(self, passages):
        """Le statut de la commande est celui du plat le moins avancé."""
        self.ensure_one()
        en_cours = passages.filtered(lambda p: p.en_cours)
        if not en_cours:
            return 'servi'

        rangs = {}
        for passage in en_cours:
            ecran = passage.display_id
            if not ecran:
                continue
            etape_servi = ecran.laresidence_stage_servi_id
            etape_passe = ecran._laresidence_stage_passe()
            if passage.stage_id == etape_servi:
                rangs[passage.id] = 4
            elif passage.stage_id == etape_passe:
                rangs[passage.id] = 3
            else:
                premieres = (ecran.stage_ids - etape_servi).sorted(
                    key=lambda e: (e.sequence, e.id))
                rangs[passage.id] = 1 if (premieres and passage.stage_id == premieres[0]) else 2

        if not rangs:
            return 'aucun'
        return {1: 'envoye', 2: 'en_cours', 3: 'a_envoyer', 4: 'servi'}[min(rangs.values())]

    def action_laresidence_voir_passages(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Suivi de préparation",
            'res_model': 'laresidence.prep.passage',
            'view_mode': 'list,pivot,graph',
            'domain': [('pos_order_id', '=', self.id)],
            'context': {'search_default_group_product': 1},
        }
