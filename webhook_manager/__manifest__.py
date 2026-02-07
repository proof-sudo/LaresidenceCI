# -*- coding: utf-8 -*-
{
    'name': 'The Residence Webhook Manager',
    'version': '19.0.1.1',
    'category': 'Technical',
    'summary': 'Intégration Webhook pour The Residence API',
    'description': """
        Système de webhooks synchronisant Odoo avec l'API The Residence.
        
        Modèles supportés :
        - Membres (Contacts)
        - Commandes (Ventes)
        - Abonnements (Subscriptions)
        - Réservations (Hôtel/Restaurant)
        - Factures et Stocks
        
        Fonctionnalités :
        - Authentification via X-API-Key
        - Structure de payload conforme (event_id, timestamp, entity_type)
        - Détection intelligente des changements de statuts métiers
    """,
    'author': 'Votre Entreprise',
    'website': 'https://api.laresidence-abidjan.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'sale_management',
        'stock',
        'account',
        'point_of_sale',
        # 'sale_subscription', # Décommentez si le module Subscriptions est installé
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/webhook_config_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}