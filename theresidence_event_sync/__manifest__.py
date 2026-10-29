# -*- coding: utf-8 -*-
{
    'name': 'The Residence - Event Sync',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Synchronisation des événements depuis le backend externe vers Odoo',
    'description': """
        Reçoit les événements, inscriptions et invités depuis le backend
        The Residence (Java/Spring Boot) et les enregistre dans le module
        Events natif d'Odoo.

        Endpoints exposés :
        - POST   /v1/external/events
        - PUT    /v1/external/events/<id>
        - DELETE /v1/external/events/<id>
        - POST   /v1/external/events/<id>/registrations
        - PUT    /v1/external/events/<id>/registrations/<reg_id>
        - DELETE /v1/external/events/<id>/registrations/<reg_id>
    """,
    'author': 'Djakaridja Traore',
    'website': 'mailto:djakaridjatraore@outlook.com',
    'license': 'LGPL-3',
    'depends': [
        'event',
        'theresidence_api',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/event_event_views.xml',
        'views/event_registration_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
