# -*- coding: utf-8 -*-
{
    'name': 'The Residence - API Module',
    'version': '19.0.1.0.0',
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
    'author': 'Neurones Technologies',
    'website': 'https://www.neurones.ci',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'sale_renting',
        'point_of_sale',
        'sale_subscription',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/reference_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
