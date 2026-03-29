# -*- coding: utf-8 -*-
{
    'name': 'The Residence - API Module',
    'version': '19.0.1',
    'category': 'Technical',
    'summary': 'REST API pour l\'application mobile The Residence',
    'description': """
        Module API REST pour The Residence Business Club.
        
        Fonctionnalités:
        - Authentification par clé API
        - Gestion des membres (res.partner)
        - Réservations d'espaces (sale.order + rental)
        - Commandes restaurant (pos.order)
        - Abonnements (sale.order subscription)
        - Webhooks pour notifications temps réel
        
        Ce module hérite des modules standards Odoo et ajoute
        les champs et endpoints API nécessaires.
    """,
    'author': 'Djakaridja Traore',
    'website': 'mailto:djakaridjatraore@outlook.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale_subscription',
        'sale',
        'sale_renting',
        'point_of_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/reference_data.xml',
        'views/api_views.xml',
        'views/res_partner_views.xml',
        'views/product_views.xml',
        'views/sale_order_views.xml',
        'views/mobile_order_views.xml',
        'views/pos_config_views.xml',
        'views/pos_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'theresidence_api/static/src/xml/ReservationScreen.xml',
            'theresidence_api/static/src/js/ReservationScreen.js',
            'theresidence_api/static/src/js/ReservationButton.js',
            'theresidence_api/static/src/css/reservation.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
