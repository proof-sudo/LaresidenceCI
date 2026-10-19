# -*- coding: utf-8 -*-
{
    'name': 'The Residence — Kitchen Bridge',
    'version': '19.0.1',
    'category': 'Technical',
    'summary': 'Synchronise le statut des commandes mobiles TR avec l\'avancement en cuisine',
    'description': """
        Module bridge entre le système de commandes mobiles TR (pos.order)
        et le module de préparation cuisine d'Odoo (pos_enterprise).

        - Quand une commande mobile est envoyée en cuisine : statut → CONFIRMED + webhook
        - Quand tous les articles sont marqués prêts en cuisine : statut → READY + webhook
    """,
    'author': 'Djakaridja Traore',
    'website': 'mailto:djakaridjatraore@outlook.com',
    'license': 'LGPL-3',
    'depends': [
        'theresidence_api',
        'pos_enterprise',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
