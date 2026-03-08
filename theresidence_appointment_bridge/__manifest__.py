# -*- coding: utf-8 -*-
{
    'name': 'The Residence — Appointment Bridge',
    'version': '19.0.1',
    'category': 'Technical',
    'summary': 'Synchronise les réservations sale.order avec pos_appointment',
    'description': """
        Module bridge entre le système de réservation TR (sale.order)
        et le module pos_appointment d'Odoo.

        - Crée automatiquement un appointment.type par espace (x_tr_is_space)
        - Crée un calendar.event miroir pour chaque réservation
        - Synchronise les statuts sale.order ↔ calendar.event
        - Les réservations apparaissent nativement dans le menu POS Appointments
    """,
    'author': 'Neurones Technologies',
    'license': 'LGPL-3',
    'depends': [
        'theresidence_api',
        'appointment',
        'pos_appointment',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/bridge_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
