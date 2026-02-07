# -*- coding: utf-8 -*-
{
    'name': 'Webhook System',
    'version': '19.0.1',
    'category': 'Technical',
    'summary': 'Système de webhooks CRUD pour Odoo',
    'description': """
        Système de webhooks pour envoyer des notifications HTTP
        lors des opérations CRUD sur les modèles Odoo.
        
        Fonctionnalités:
        - Configuration des webhooks par modèle
        - Suivi des champs modifiés
        - Support des relations Many2many
        - Authentification API
    """,
    'author': 'Votre Entreprise',
    'website': 'https://www.votresite.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'sale_management',
        'point_of_sale',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/webhook_config_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}