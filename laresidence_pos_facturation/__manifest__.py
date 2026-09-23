# -*- coding: utf-8 -*-
{
    'name': "Caisse — facturation guidée",
    'summary': "La caisse enregistre la demande de facture, elle ne la produit pas",
    'description': """
Trois changements, tous au service d'une même règle : le caissier encaisse,
il ne facture pas.

* le bouton « Facture » disparaît de l'écran de paiement ;
* le choix d'un mode de paiement demande une confirmation, puis une seule
  question — le client veut-il une facture FNE ? — à laquelle le caissier
  peut ne pas répondre ;
* la commande porte un statut de facturation à quatre états, dont les deux
  derniers se déduisent de la facture elle-même.

Il rattache aussi la facture issue d'une commande liée à un devis à ce devis,
sans que le client soit compté deux fois.
""",
    'version': '19.0.3',
    'category': 'Sales/Point of Sale',
    'author': "Djakaridja Traore",
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'pos_sale',
        'odoo_fne_connector',
    ],
    'data': [
        'views/pos_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'laresidence_pos_facturation/static/src/app/facturation_patch.js',
            'laresidence_pos_facturation/static/src/app/facturation_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
}
