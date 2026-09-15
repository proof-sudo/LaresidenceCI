# -*- coding: utf-8 -*-
"""L'écart remonte jusque dans le planning.

Un gestionnaire de planning ne va pas consulter une liste d'écarts : il
travaille dans son planning. Si l'information ne l'y rejoint pas, elle
n'existe pas pour lui.

Chaque créneau porte donc le constat de ce qui s'est réellement passé — rien
de plus qu'un rappel de l'écart déjà enregistré, avec le lien pour l'ouvrir.
Le calcul reste entier du côté du module de contrôle ; le planning se contente
d'afficher.
"""

from odoo import api, fields, models


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    laresidence_exception_ids = fields.One2many(
        'laresidence.hr.exception', 'planning_slot_id',
        string="Écarts constatés", readonly=True)
    laresidence_exception_count = fields.Integer(
        string="Nombre d'écarts", compute='_compute_laresidence_ecart',
        store=True, readonly=True)
    laresidence_ecart = fields.Char(
        string="Constat", compute='_compute_laresidence_ecart',
        store=True, readonly=True,
        help="Ce qui a été relevé sur ce créneau à partir des pointages. "
             "Vide tant que le créneau n'a pas été analysé.")
    laresidence_ecart_state = fields.Selection([
        ('conforme', "Conforme"),
        ('ecart', "Écart constaté"),
        ('non_analyse', "Pas encore analysé"),
    ], string="Présence", compute='_compute_laresidence_ecart',
        store=True, readonly=True,
        help="Permet de filtrer le planning sur les créneaux qui ont posé problème.")

    @api.depends('laresidence_exception_ids',
                 'laresidence_exception_ids.exception_type',
                 'laresidence_exception_ids.delta_minutes',
                 'laresidence_exception_ids.state')
    def _compute_laresidence_ecart(self):
        libelles = dict(self.env['laresidence.hr.exception']._fields['exception_type'].selection)

        # Quelles journées ont réellement été passées en revue ?
        #
        # Premier essai : « la tâche est passée après la fin du créneau ». Faux,
        # et vérifié faux en production — la détection ne traite qu'un jour, la
        # veille. Les 2 171 créneaux antérieurs, jamais analysés, se sont
        # affichés « Conforme » d'un coup. Exactement l'affichage qui rassure à
        # tort que ce champ était censé éviter.
        #
        # On s'appuie donc sur une trace, pas sur une heure : une journée
        # analysée a produit des écarts. Sur cinquante-quatre employés, une
        # journée traitée sans le moindre écart n'existe pas. Et l'erreur, s'il
        # y en a une, penche du bon côté : on affiche « pas encore analysé »
        # plutôt qu'un « Conforme » que personne n'a vérifié.
        jours = {c.start_datetime.date() for c in self if c.start_datetime}
        analyses = set()
        if jours:
            lignes = self.env['laresidence.hr.exception'].sudo().search_read(
                [('date', 'in', list(jours))], ['date'])
            # Normalisé des deux côtés : selon les versions, une date relue
            # revient tantôt en objet, tantôt en chaîne. Comparer sans y penser
            # donnerait un ensemble vide et « pas encore analysé » partout.
            analyses = {fields.Date.to_date(l['date']) for l in lignes if l.get('date')}

        for creneau in self:
            ecarts = creneau.laresidence_exception_ids
            creneau.laresidence_exception_count = len(ecarts)
            if not ecarts:
                jour = creneau.start_datetime and creneau.start_datetime.date()
                if jour in analyses:
                    creneau.laresidence_ecart_state = 'conforme'
                    creneau.laresidence_ecart = "Conforme"
                else:
                    creneau.laresidence_ecart_state = 'non_analyse'
                    creneau.laresidence_ecart = False
                continue

            creneau.laresidence_ecart_state = 'ecart'
            if len(ecarts) == 1:
                ecart = ecarts[0]
                libelle = libelles.get(ecart.exception_type, ecart.exception_type)
                if ecart.delta_minutes:
                    creneau.laresidence_ecart = "%s — %s min" % (libelle, abs(ecart.delta_minutes))
                else:
                    creneau.laresidence_ecart = libelle
            else:
                creneau.laresidence_ecart = "%s écarts : %s" % (
                    len(ecarts),
                    ", ".join(libelles.get(e.exception_type, e.exception_type) for e in ecarts))

    def action_laresidence_voir_ecarts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Écarts — %s" % (self.employee_id.name or self.display_name),
            'res_model': 'laresidence.hr.exception',
            'view_mode': 'list,form',
            'domain': [('planning_slot_id', '=', self.id)],
            'context': {'create': False},
        }
