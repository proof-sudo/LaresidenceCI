# -*- coding: utf-8 -*-
"""L'étape « Servi », que le parcours natif n'a pas.

Odoo arrête le parcours au passe. Le temps qui intéresse la salle est celui
qui sépare l'envoi en cuisine de l'assiette posée devant le client : il faut
donc une étape de plus, et savoir laquelle c'est sur chaque poste.
"""

from odoo import _, fields, models

NOM_ETAPE_SERVI = "Servi"


class PosPrepDisplay(models.Model):
    _inherit = 'pos.prep.display'

    laresidence_stage_servi_id = fields.Many2one(
        'pos.prep.stage', string="Étape « Servi »", copy=False,
        help="Étape finale ajoutée par le suivi des temps. Elle n'est pas "
             "remplie par la cuisine mais par le serveur, depuis la caisse.")

    # ------------------------------------------------------------------
    def _laresidence_stage_passe(self):
        """Dernière étape de préparation, celle qui précède le service.

        C'est la seule depuis laquelle un plat peut être déclaré servi.
        """
        self.ensure_one()
        etapes = self.stage_ids - self.laresidence_stage_servi_id
        if not etapes:
            return self.env['pos.prep.stage']
        return etapes.sorted(key=lambda s: (s.sequence, s.id))[-1]

    def _laresidence_assurer_etape_servi(self):
        """Fige l'ordre des étapes et pose « Servi » en dernier.

        Les deux opérations sont faites à chaque appel, y compris sur un
        poste qui a déjà son étape « Servi » : c'est ce qui permet à une mise
        à jour du module de rattraper un poste installé auparavant.
        """
        Etape = self.env['pos.prep.stage'].sudo()
        for ecran in self:
            servi = ecran.laresidence_stage_servi_id or ecran.stage_ids.filtered(
                lambda e: (e.name or '').strip().lower() == NOM_ETAPE_SERVI.lower())[:1]

            # Les étapes d'origine sont toutes à la séquence 0 : leur ordre ne
            # tient qu'à leur identifiant. Une étape ajoutée plus tard en
            # cuisine prendrait alors la dernière place et deviendrait, sans
            # que personne ne le voie, celle depuis laquelle on peut servir.
            # On fige donc l'ordre déjà affiché en séquences explicites.
            rang = 0
            for etape in ecran.stage_ids - servi:
                rang += 10
                if etape.sequence != rang:
                    etape.sudo().sequence = rang

            if servi:
                if ecran.laresidence_stage_servi_id != servi:
                    ecran.laresidence_stage_servi_id = servi
                if servi.sequence != rang + 10:
                    servi.sudo().sequence = rang + 10
                continue

            ecran.laresidence_stage_servi_id = Etape.create({
                'name': NOM_ETAPE_SERVI,
                'prep_display_id': ecran.id,
                'sequence': rang + 10,
                'alert_timer': 0,
                'color': '#1D6B4F',
            })
        return True

    def action_laresidence_assurer_etape_servi(self):
        self._laresidence_assurer_etape_servi()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Étape « Servi »"),
                'message': _("L'étape est en place sur les postes sélectionnés."),
                'type': 'success',
            },
        }
