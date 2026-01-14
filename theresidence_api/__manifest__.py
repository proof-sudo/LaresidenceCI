# -*- coding: utf-8 -*-
{
    'name': 'The Residence API',
    'version': '19.0.1',
    'category': 'Sales/Sales',
    'summary': 'REST API Integration for The Residence Mobile App',
    'description': """
The Residence API - Mobile Integration Module
=============================================

Ce module fournit une intégration complète entre Odoo et l'application mobile The Residence.

Fonctionnalités
---------------
* APIs REST pour synchronisation mobile
* Gestion des membres (extension res.partner)
* Réservations de salles via sale_renting
* Commandes restaurant via POS ou Sale Order
* Webhooks bidirectionnels
* Authentification par clé API

APIs Exposées (GET - Lecture)
-----------------------------
* /api/v1/spaces - Liste des salles disponibles
* /api/v1/spaces/<id> - Détail d'une salle
* /api/v1/spaces/<id>/availability - Disponibilités
* /api/v1/menu-kinds - Types de menu
* /api/v1/menu-categories - Catégories de menu
* /api/v1/menu-items - Articles du menu
* /api/v1/members - Liste des membres
* /api/v1/members/<id> - Détail d'un membre
* /api/v1/reservations - Liste des réservations
* /api/v1/orders - Liste des commandes

APIs Exposées (POST/PUT/DELETE - Écriture)
------------------------------------------
* POST /api/v1/reservations - Créer une réservation
* PUT /api/v1/reservations/<id> - Modifier une réservation
* DELETE /api/v1/reservations/<id> - Annuler une réservation
* POST /api/v1/reservations/<id>/approve - Approuver
* POST /api/v1/reservations/<id>/reject - Rejeter
* POST /api/v1/reservations/<id>/check-in - Check-in
* POST /api/v1/orders - Créer une commande
* POST /api/v1/orders/<id>/confirm - Confirmer
* POST /api/v1/orders/<id>/ready - Marquer prêt
* POST /api/v1/orders/<id>/complete - Terminer
* POST /api/v1/orders/<id>/cancel - Annuler
* POST /api/v1/members - Créer un membre
* PUT /api/v1/members/<id> - Modifier un membre
* POST /api/v1/subscriptions - Créer un abonnement
* POST /api/v1/webhook - Réception webhooks

Auteur: Neurones Technologies
    """,
    'author': 'Neurones Technologies',
    'website': 'https://www.neurones-technologies.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale_management',
        'sale_renting',
        'product',
        'calendar',
        'contacts',
        'point_of_sale',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/sequence_data.xml',
        # 'data/product_category_data.xml',
        'data/membership_data.xml',
        # Views
        'views/residence_config_views.xml',
        'views/res_partner_views.xml',
        'views/product_views.xml',
        'views/sale_order_views.xml',
        'views/residence_order_views.xml',
        'views/residence_membership_views.xml',
        'views/residence_webhook_log_views.xml',
        'views/menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {},
    'images': ['static/description/icon.png'],
    'external_dependencies': {
        'python': [],
    },
}
