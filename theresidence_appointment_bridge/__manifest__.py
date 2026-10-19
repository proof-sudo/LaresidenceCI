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
    'author': 'Djakaridja Traore',
    'website': 'mailto:djakaridjatraore@outlook.com',
    'license': 'LGPL-3',
    'depends': [
        'theresidence_api',
        'appointment',
        'pos_appointment',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/bridge_views.xml',
        'views/assets.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'theresidence_appointment_bridge/static/src/js/pos_reservation_notify.js',
            'theresidence_appointment_bridge/static/src/js/gantt_popover_patch.js',
            'theresidence_appointment_bridge/static/src/js/appointment_list_patch.js',
            'theresidence_appointment_bridge/static/src/css/appointment_list.css',
            'theresidence_appointment_bridge/static/src/sounds/new_reservation.wav'
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
