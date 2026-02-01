# -*- coding: utf-8 -*-
{
    'name': 'The Residence - Webhook Sender',
    'version': '19.0.1.0.0',
    'category': 'Integration',
    'summary': 'Envoie des webhooks vers l\'API externe de The Residence',
    'description': """
The Residence Webhook Sender
=============================

Ce module gère l'envoi de webhooks sortants vers l'API externe de The Residence.

Fonctionnalités:
----------------
* Configuration centralisée de l'API externe
* Queue des événements à envoyer
* Retry automatique avec backoff exponentiel
* Monitoring et logs des envois
* Support de l'idempotence
* Traitement asynchrone

Types d'événements supportés:
----------------------------
* Commandes: confirmed, ready, completed, cancelled
* Réservations: approved, rejected, cancelled, checked_in
* Abonnements: activated, paused, resumed, cancelled, expired, renewed
* Membres: updated

Auteur: Développeur The Residence
License: LGPL-3
    """,
    'author': 'The Residence',
    'website': 'https://laresidence-abidjan.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale',
        'point_of_sale',
        'sale_subscription'
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/webhook_config_data.xml',
        'data/cron.xml',
        'views/webhook_config_views.xml',
        'views/webhook_queue_views.xml',
        'views/webhook_log_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
