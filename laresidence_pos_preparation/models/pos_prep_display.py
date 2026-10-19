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
        """Crée l'étape « Servi » sur les postes qui ne l'ont pas encore."""
        Etape = self.env['pos.prep.stage'].sudo()
        for ecran in self:
            if ecran.laresidence_stage_servi_id:
                continue
            existante = ecran.stage_ids.filtered(
                lambda e: (e.name or '').strip().lower() == NOM_ETAPE_SERVI.lower())
            if existante:
                ecran.laresidence_stage_servi_id = existante[0]
                continue
            sequences = ecran.stage_ids.mapped('sequence') or [0]
            ecran.laresidence_stage_servi_id = Etape.create({
                'name': NOM_ETAPE_SERVI,
                'prep_display_id': ecran.id,
                'sequence': max(sequences) + 10,
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
