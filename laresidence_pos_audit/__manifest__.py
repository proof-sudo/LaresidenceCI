# -*- coding: utf-8 -*-
{
    'name': 'La Résidence — Journal d\'audit du Point de Vente',
    'version': '19.0.2',
    'category': 'Point of Sale',
    'summary': "Journal d'événements immuable du POS : qui a ouvert une commande, quand, sur quel appareil",
    'description': """
Odoo ne conserve aucune trace de ce qui précède la validation d'une commande POS :

- ``employee_id`` est réécrit à chaque action (ouverture, ajout de ligne, validation),
  si bien que le dernier caissier connecté écrase tous les précédents ;
- ``date_order`` est réécrit au moment de la validation, l'heure d'ouverture disparaît ;
- ``payment_date`` provient de l'horloge de la tablette, non de celle du serveur ;
- aucun modèle d'audit n'existe (``ir.logging`` ne couvre pas le POS).

Ce module enregistre chaque action du front POS dans un journal **immuable**,
horodaté par le **serveur**, avec l'identifiant de l'appareil et le caissier
en place au moment précis de l'action.

Événements couverts :
    ouverture de commande, ajout / retrait / modification de ligne, remise,
    changement de caissier (y compris la reconnexion silencieuse depuis
    sessionStorage, sans code PIN), changement de table, transfert de commande,
    impression de l'addition, impression du reçu, validation, suppression.

Garanties :
    - écriture et suppression bloquées au niveau du modèle, pour tous les profils ;
    - horodatage serveur faisant foi, l'heure annoncée par la tablette est
      conservée à part et l'écart entre les deux est calculé et exposé ;
    - nom de produit figé au moment de l'événement (un renommage ultérieur de
      l'article ne réécrit pas l'historique) ;
    - file d'attente persistante côté navigateur : un redémarrage de tablette
      ne fait pas perdre les événements en attente d'envoi.
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'pos_hr',
        'pos_restaurant',
    ],
    'data': [
        'security/pos_audit_groups.xml',
        'security/ir.model.access.csv',
        'wizard/audit_unlock_views.xml',
        'views/laresidence_pos_audit_views.xml',
        'views/pos_order_views.xml',
        'views/pos_session_views.xml',
        'data/ir_cron.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'laresidence_pos_audit/static/src/app/audit_service.js',
            'laresidence_pos_audit/static/src/app/pos_audit_patch.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
