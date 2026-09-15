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

        # Jusqu'où l'analyse est-elle allée ? La détection tourne une fois par
        # jour sur la veille : un créneau n'est déclaré conforme que si la
        # journée qui le contient a effectivement été passée en revue. Sans
        # cela, tout créneau terminé depuis une minute s'afficherait
        # « Conforme » alors que rien n'a encore été regardé — le pire des
        # affichages, parce qu'il rassure à tort. Une seule requête, quel que
        # soit le nombre de créneaux.
        tache = self.env.ref('laresidence_hr_control.ir_cron_laresidence_hr_exception',
                             raise_if_not_found=False)
        analyse_jusqua = tache and tache.sudo().lastcall

        for creneau in self:
            ecarts = creneau.laresidence_exception_ids
            creneau.laresidence_exception_count = len(ecarts)
            if not ecarts:
                analysee = bool(
                    analyse_jusqua and creneau.end_datetime
                    and creneau.end_datetime < analyse_jusqua)
                if analysee:
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
