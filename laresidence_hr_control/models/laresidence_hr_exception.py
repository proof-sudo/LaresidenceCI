# -*- coding: utf-8 -*-
"""Écarts entre les pointages réels et l'horaire de référence.

Le point délicat de ce module n'est pas la détection des écarts, qui est
arithmétique, mais le choix de la **référence** à laquelle comparer. Deux
sources coexistent dans Odoo et ne couvrent pas la même population :

- le module *Planning* (``planning.slot``) donne un créneau daté et nominatif,
  mais il n'est renseigné que pour une partie des employés ;
- l'*horaire contractuel* (``resource_calendar_id``) couvre tout le monde,
  mais décrit une semaine type et non une journée précise.

La règle retenue est : planning s'il existe, horaire contractuel sinon, et
aucun écart si ni l'un ni l'autre n'est renseigné. Chaque enregistrement
indique la référence effectivement utilisée, pour que la discussion avec
l'employé porte sur une base explicite.
"""

import logging
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

PARAM_LATE_IN = 'laresidence_hr_control.tolerance_late_in'
PARAM_EARLY_IN = 'laresidence_hr_control.tolerance_early_in'
PARAM_EARLY_OUT = 'laresidence_hr_control.tolerance_early_out'
PARAM_LATE_OUT = 'laresidence_hr_control.tolerance_late_out'
PARAM_ABSENCE = 'laresidence_hr_control.detect_absence'
PARAM_PLANNING_PUBLIE = 'laresidence_hr_control.planning_published_only'

DEFAULTS = {
    PARAM_LATE_IN: 10,    # retard toléré à la prise de poste
    PARAM_EARLY_IN: 30,   # avance tolérée à la prise de poste
    PARAM_EARLY_OUT: 10,  # départ anticipé toléré
    PARAM_LATE_OUT: 60,   # dépassement toléré avant signalement
}

# Fenêtre de rattachement d'un pointage à un créneau de référence.
MATCH_WINDOW_MINUTES = 240
# Deux intervalles de travail séparés de moins que cela appartiennent au même poste.
SHIFT_GAP_MINUTES = 120


class LaresidenceHrException(models.Model):
    _name = 'laresidence.hr.exception'
    _description = "Écart de présence"
    _order = 'date desc, employee_id, expected_start'
    _inherit = ['mail.thread']

    EXCEPTION_TYPES = [
        ('late_in', "Retard à la prise de poste"),
        ('early_in', "Prise de poste anticipée"),
        ('early_out', "Départ anticipé"),
        ('late_out', "Dépassement d'horaire"),
        ('no_checkout', "Sortie non badgée"),
        ('absence', "Absence — aucun pointage"),
        ('unplanned', "Pointage hors référence"),
    ]

    employee_id = fields.Many2one('hr.employee', string="Employé", required=True,
                                  index=True, ondelete='cascade', tracking=True)
    department_id = fields.Many2one(related='employee_id.department_id', store=True, string="Département")
    date = fields.Date(string="Date", required=True, index=True)
    exception_type = fields.Selection(EXCEPTION_TYPES, string="Écart", required=True, index=True, tracking=True)

    reference_type = fields.Selection([
        ('planning', "Créneau planning"),
        ('calendar', "Horaire contractuel"),
        ('none', "Aucune référence"),
    ], string="Référence utilisée", required=True, default='none',
        help="Sur quelle base l'écart a été calculé. Le planning prime lorsqu'il "
             "est renseigné ; à défaut l'horaire contractuel de l'employé s'applique.")
    planning_slot_id = fields.Many2one('planning.slot', string="Créneau", ondelete='set null')
    attendance_id = fields.Many2one('hr.attendance', string="Pointage", ondelete='cascade')

    expected_start = fields.Datetime(string="Début attendu")
    expected_end = fields.Datetime(string="Fin attendue")
    actual_start = fields.Datetime(string="Entrée réelle")
    actual_end = fields.Datetime(string="Sortie réelle")
    delta_minutes = fields.Integer(string="Écart (min)", tracking=True,
                                   help="Positif = après l'heure attendue, négatif = avant.")
    delta_display = fields.Char(string="Écart", compute='_compute_delta_display')

    in_mode = fields.Selection(related='attendance_id.in_mode', string="Mode d'entrée", store=True)
    out_mode = fields.Selection(related='attendance_id.out_mode', string="Mode de sortie", store=True)

    state = fields.Selection([
        ('to_review', "À examiner"),
        ('justified', "Justifié"),
        ('unjustified', "Non justifié"),
    ], string="Statut", default='to_review', required=True, index=True, tracking=True)
    reason = fields.Text(string="Motif")
    validated_uid = fields.Many2one('res.users', string="Traité par", readonly=True)
    validated_on = fields.Datetime(string="Traité le", readonly=True)

    company_id = fields.Many2one('res.company', string="Société",
                                 default=lambda self: self.env.company, index=True)

    # Odoo 19 ne reconnaît plus _sql_constraints : sans cette réécriture, la
    # contrainte n'existait pas en base et rien n'empêchait un même écart
    # d'être enregistré deux fois.
    #
    # « nulls not distinct » n'est pas un détail : sans cette mention,
    # PostgreSQL tient deux valeurs nulles pour différentes, et la contrainte
    # ne protège rien dès qu'un pointage manque — c'est-à-dire précisément sur
    # les absences, de loin le cas le plus fréquent. (PostgreSQL 15 et plus.)
    _unique_exception = models.Constraint(
        'unique nulls not distinct '
        '(employee_id, date, exception_type, expected_start, attendance_id)',
        "Cet écart a déjà été enregistré.",
    )

    # ------------------------------------------------------------------
    # Affichage
    # ------------------------------------------------------------------
    @api.depends('delta_minutes')
    def _compute_delta_display(self):
        for rec in self:
            minutes = abs(rec.delta_minutes or 0)
            sign = '+' if (rec.delta_minutes or 0) > 0 else ('-' if rec.delta_minutes else '')
            rec.delta_display = '%s%dh%02d' % (sign, minutes // 60, minutes % 60) if minutes >= 60 \
                else ('%s%d min' % (sign, minutes) if minutes else '—')

    @api.depends('employee_id', 'exception_type', 'date')
    def _compute_display_name(self):
        labels = dict(self.EXCEPTION_TYPES)
        for rec in self:
            rec.display_name = "%s — %s (%s)" % (
                rec.employee_id.name or '',
                labels.get(rec.exception_type, ''),
                rec.date or '')

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_justify(self):
        return self._set_state('justified')

    def action_unjustify(self):
        return self._set_state('unjustified')

    def action_reset(self):
        self.write({'state': 'to_review', 'validated_uid': False, 'validated_on': False})

    def _set_state(self, state):
        self.write({
            'state': state,
            'validated_uid': self.env.user.id,
            'validated_on': fields.Datetime.now(),
        })
        return True

    # ------------------------------------------------------------------
    # Paramètres
    # ------------------------------------------------------------------
    @api.model
    def _tolerances(self):
        icp = self.env['ir.config_parameter'].sudo()
        out = {}
        for key, default in DEFAULTS.items():
            try:
                out[key] = int(icp.get_param(key, default))
            except (TypeError, ValueError):
                out[key] = default
        brut = icp.get_param(PARAM_ABSENCE, '1')
        out[PARAM_ABSENCE] = str(brut).strip().lower() not in ('0', 'false', 'no', 'non')
        brut = icp.get_param(PARAM_PLANNING_PUBLIE, '1')
        out[PARAM_PLANNING_PUBLIE] = str(brut).strip().lower() not in ('0', 'false', 'no', 'non')
        return out

    # ------------------------------------------------------------------
    # Référence horaire
    # ------------------------------------------------------------------
    @api.model
    def _merge_intervals(self, intervals):
        """Recolle les tranches d'un même poste (pause déjeuner, coupure courte)."""
        if not intervals:
            return []
        intervals = sorted(intervals, key=lambda i: i[0])
        merged = [list(intervals[0])]
        for start, end in intervals[1:]:
            if (start - merged[-1][1]) <= timedelta(minutes=SHIFT_GAP_MINUTES):
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        return [tuple(m) for m in merged]

    @api.model
    def _reference_intervals(self, employee, day_start, day_end, planning_publie=True):
        """Retourne [(debut, fin, creneau_ou_False, type_de_reference)] en UTC naïf.

        Un poste appartient à la journée où il **commence**, pas à chacune de
        celles qu'il traverse. Sans cette règle, les horaires de nuit de la
        maison — « Fermeture 17h-01h45 », « Fermeture 18h-02h45 » — seraient
        comptés deux fois : une fois le soir, une fois le lendemain matin pour
        le morceau situé après minuit, ce second morceau n'ayant jamais de
        pointage en face et produisant une absence imaginaire.

        Les intervalles sont donc calculés sur une fenêtre élargie de douze
        heures de part et d'autre, recollés, puis filtrés sur leur heure de
        début.
        """
        # Planning : le créneau compte pour le jour où il débute.
        #
        # Et seulement s'il a été publié. Un créneau en brouillon n'a jamais
        # été communiqué à l'employé : lui reprocher un retard sur cette base
        # ne tiendrait pas devant lui, encore moins devant un tiers. À défaut
        # de planning publié, on retombe sur l'horaire contractuel, qui est
        # opposable parce qu'il a été signé. Le jour où les plannings sont
        # publiés, la référence redevient le planning sans rien changer au code.
        domaine = [
            ('employee_id', '=', employee.id),
            ('start_datetime', '>=', day_start),
            ('start_datetime', '<=', day_end),
        ]
        if planning_publie:
            domaine.append(('state', '=', 'published'))
        slots = self.env['planning.slot'].search(domaine, order='start_datetime')
        if slots:
            return [(s.start_datetime, s.end_datetime, s, 'planning') for s in slots]

        calendar = employee.resource_calendar_id
        if not calendar:
            return []

        fenetre_debut = pytz.utc.localize(day_start - timedelta(hours=12))
        fenetre_fin = pytz.utc.localize(day_end + timedelta(hours=12))
        try:
            batch = calendar._work_intervals_batch(
                fenetre_debut, fenetre_fin, resources=employee.resource_id)
        except Exception:
            _logger.exception("laresidence_hr_control : calcul d'intervalles impossible pour %s", employee.display_name)
            return []

        raw = batch.get(employee.resource_id.id) or batch.get(False) or []
        naive = []
        for item in raw:
            begin, finish = item[0], item[1]
            naive.append((begin.astimezone(pytz.utc).replace(tzinfo=None),
                          finish.astimezone(pytz.utc).replace(tzinfo=None)))

        return [(a, b, False, 'calendar')
                for a, b in self._merge_intervals(naive)
                if day_start <= a <= day_end]

    # ------------------------------------------------------------------
    # Génération
    # ------------------------------------------------------------------
    @api.model
    def generate(self, date_from, date_to, employees=None):
        """Recalcule les écarts sur une période. Idempotent : les écarts déjà
        traités par un responsable sont conservés tels quels, seuls ceux encore
        « à examiner » sont régénérés."""
        if isinstance(date_from, str):
            date_from = fields.Date.to_date(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.to_date(date_to)

        # Appelé aussi bien depuis la tâche planifiée, qui passe un
        # enregistrement, que depuis l'extérieur — action serveur, appel
        # distant — où l'on ne dispose que d'identifiants.
        if not employees:
            employees = self.env['hr.employee'].search([])
        elif isinstance(employees, (list, tuple, int)):
            employees = self.env['hr.employee'].browse(employees).exists()
        tol = self._tolerances()
        created = 0

        day = date_from
        while day <= date_to:
            day_start = datetime.combine(day, time.min)
            day_end = datetime.combine(day, time.max)

            # On repart d'une ardoise propre pour les écarts non encore traités.
            self.search([
                ('date', '=', day),
                ('state', '=', 'to_review'),
                ('employee_id', 'in', employees.ids),
            ]).unlink()
            already = self.search([('date', '=', day), ('employee_id', 'in', employees.ids)])
            deja_traite = {(e.employee_id.id, e.exception_type, e.expected_start, e.attendance_id.id)
                           for e in already}

            attendances = self.env['hr.attendance'].search([
                ('employee_id', 'in', employees.ids),
                ('check_in', '>=', day_start),
                ('check_in', '<=', day_end),
                ('in_mode', '!=', 'technical'),
            ])
            par_employe = {}
            for att in attendances:
                par_employe.setdefault(att.employee_id.id, []).append(att)

            concernes = employees.filtered(
                lambda e: e.id in par_employe) | employees.filtered(lambda e: e.resource_calendar_id)

            rows = []
            for employee in concernes:
                rows += self._compute_for_day(employee, day, day_start, day_end,
                                              par_employe.get(employee.id, []), tol)

            rows = [r for r in rows
                    if (r['employee_id'], r['exception_type'], r.get('expected_start'),
                        r.get('attendance_id') or False) not in deja_traite]
            if rows:
                created += len(self.create(rows))

            # Les créneaux de la journée portent le constat de présence. Ceux
            # qui reçoivent un écart sont recalculés d'eux-mêmes ; ceux qui
            # n'en reçoivent aucun, non — ils resteraient muets alors qu'ils
            # viennent justement d'être déclarés conformes. On les marque donc
            # explicitement comme à recalculer.
            creneaux = self.env['planning.slot'].sudo().search([
                ('employee_id', 'in', employees.ids),
                ('start_datetime', '>=', day_start),
                ('start_datetime', '<=', day_end),
            ])
            if creneaux:
                creneaux.modified(['laresidence_exception_ids'])

            day += timedelta(days=1)

        _logger.info("laresidence_hr_control : %s écart(s) généré(s) du %s au %s", created, date_from, date_to)
        return created

    @api.model
    def _compute_for_day(self, employee, day, day_start, day_end, attendances, tol):
        references = self._reference_intervals(
            employee, day_start, day_end, tol[PARAM_PLANNING_PUBLIE])
        rows = []
        restants = list(attendances)

        for expected_start, expected_end, slot, ref_type in references:
            # Pointage le plus proche du début attendu, dans une fenêtre raisonnable.
            candidat, ecart_min = None, None
            for att in restants:
                delta = abs((att.check_in - expected_start).total_seconds()) / 60.0
                if delta <= MATCH_WINDOW_MINUTES and (ecart_min is None or delta < ecart_min):
                    candidat, ecart_min = att, delta

            base = {
                'employee_id': employee.id,
                'date': day,
                'reference_type': ref_type,
                'planning_slot_id': slot.id if slot else False,
                'expected_start': expected_start,
                'expected_end': expected_end,
                'company_id': employee.company_id.id or self.env.company.id,
            }

            if not candidat:
                # Un effectif qui ne badge pas systématiquement produirait une
                # avalanche d'absences, et un relevé que plus personne ne lit.
                # Le paramètre permet de couper cette détection sans toucher
                # aux autres.
                if tol.get(PARAM_ABSENCE, True):
                    rows.append(dict(base, exception_type='absence', delta_minutes=0))
                continue

            restants.remove(candidat)
            base.update({
                'attendance_id': candidat.id,
                'actual_start': candidat.check_in,
                'actual_end': candidat.check_out or False,
            })

            delta_in = int(round((candidat.check_in - expected_start).total_seconds() / 60.0))
            if delta_in > tol[PARAM_LATE_IN]:
                rows.append(dict(base, exception_type='late_in', delta_minutes=delta_in))
            elif delta_in < -tol[PARAM_EARLY_IN]:
                rows.append(dict(base, exception_type='early_in', delta_minutes=delta_in))

            if candidat.out_mode == 'auto_check_out':
                rows.append(dict(base, exception_type='no_checkout', delta_minutes=0))
            elif candidat.check_out:
                delta_out = int(round((candidat.check_out - expected_end).total_seconds() / 60.0))
                if delta_out < -tol[PARAM_EARLY_OUT]:
                    rows.append(dict(base, exception_type='early_out', delta_minutes=delta_out))
                elif delta_out > tol[PARAM_LATE_OUT]:
                    rows.append(dict(base, exception_type='late_out', delta_minutes=delta_out))

        for att in restants:
            rows.append({
                'employee_id': employee.id,
                'date': day,
                'exception_type': 'unplanned',
                'reference_type': 'none',
                'attendance_id': att.id,
                'actual_start': att.check_in,
                'actual_end': att.check_out or False,
                'delta_minutes': 0,
                'company_id': employee.company_id.id or self.env.company.id,
            })

        return rows

    # ------------------------------------------------------------------
    # Tâche planifiée
    # ------------------------------------------------------------------
    @api.model
    def _cron_generate(self):
        hier = fields.Date.context_today(self) - timedelta(days=1)
        nb = self.generate(hier, hier)
        if nb:
            self._send_digest(hier)
        return nb

    @api.model
    def _send_digest(self, day):
        """Un seul courriel récapitulatif par jour, aux membres du groupe
        « destinataires des alertes de présence ». Composé directement plutôt
        que via un modèle de courriel : un écran de moins à maintenir."""
        groupe = self.env.ref('laresidence_hr_control.group_hr_exception_notified',
                              raise_if_not_found=False)
        if not groupe:
            return False
        emails = [u.email for u in groupe.user_ids if u.email]
        if not emails:
            return False

        ecarts = self.search([('date', '=', day), ('state', '=', 'to_review')],
                             order='employee_id, expected_start')
        if not ecarts:
            return False

        labels = dict(self.EXCEPTION_TYPES)
        lignes = []
        for e in ecarts:
            lignes.append(
                "<tr>"
                "<td style='padding:6px 10px;border-bottom:1px solid #e5e7eb'>%s</td>"
                "<td style='padding:6px 10px;border-bottom:1px solid #e5e7eb'>%s</td>"
                "<td style='padding:6px 10px;border-bottom:1px solid #e5e7eb'>%s</td>"
                "<td style='padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:right'>%s</td>"
                "</tr>" % (
                    e.employee_id.name or '',
                    labels.get(e.exception_type, e.exception_type),
                    dict(self._fields['reference_type'].selection).get(e.reference_type, ''),
                    e.delta_display or '',
                ))

        corps = (
            "<div style=\"font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#1a1c20\">"
            "<p>Écarts de présence relevés le <b>%s</b> : <b>%s</b> à examiner.</p>"
            "<table style='border-collapse:collapse;font-size:14px'>"
            "<tr>"
            "<th style='text-align:left;padding:6px 10px;border-bottom:2px solid #7a1f3d'>Employé</th>"
            "<th style='text-align:left;padding:6px 10px;border-bottom:2px solid #7a1f3d'>Écart</th>"
            "<th style='text-align:left;padding:6px 10px;border-bottom:2px solid #7a1f3d'>Référence</th>"
            "<th style='text-align:right;padding:6px 10px;border-bottom:2px solid #7a1f3d'>Durée</th>"
            "</tr>%s</table>"
            "<p style='color:#5d646f;font-size:13px'>Ce relevé ne préjuge de rien : "
            "chaque ligne reste à valider ou à justifier dans Odoo.</p>"
            "</div>" % (day, len(ecarts), ''.join(lignes))
        )

        self.env['mail.mail'].sudo().create({
            'subject': "Écarts de présence du %s — %s à examiner" % (day, len(ecarts)),
            'body_html': corps,
            'email_to': ','.join(emails),
            'auto_delete': False,
        })
        return True
