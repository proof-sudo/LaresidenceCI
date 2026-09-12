# -*- coding: utf-8 -*-
{
    'name': "La Résidence — Contrôle des présences",
    'version': '19.0.1',
    'category': 'Human Resources/Attendances',
    'summary': "Écarts entre les pointages et l'horaire de référence (planning ou horaire contractuel)",
    'description': """
Odoo enregistre les pointages mais ne les confronte à rien : un employé qui
prend son poste deux heures avant l'heure, ou qui ne badge jamais sa sortie,
ne déclenche aucune alerte. Sur le mois écoulé, 41 % des pointages se terminent
par une sortie automatique — une heure de fin fabriquée par le serveur, que
personne ne relit.

Ce module confronte chaque pointage à un horaire de référence et matérialise
l'écart dans un enregistrement à valider.

**Référence retenue, dans cet ordre :**

1. le créneau *Planning* de l'employé, s'il en existe un sur la journée ;
2. à défaut, son *horaire contractuel* (``resource_calendar_id``).

Cet ordre n'est pas cosmétique : le planning ne couvre qu'une minorité des
employés, alors que l'horaire contractuel les couvre tous. S'appuyer sur le
seul planning rendrait le contrôle aveugle pour la majorité de l'effectif.

**Écarts détectés :** retard à l'entrée · prise de poste anticipée ·
départ anticipé · dépassement · sortie non badgée (clôture automatique) ·
absence (référence sans aucun pointage) · pointage hors référence.

Les congés validés sont exclus : les intervalles de travail sont calculés
avec les absences, un employé en congé ne génère donc pas d'écart.
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': [
        'hr_attendance',
        'planning',
    ],
    'data': [
        'security/hr_control_groups.xml',
        'security/ir.model.access.csv',
        'views/laresidence_hr_exception_views.xml',
        'views/hr_employee_views.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
