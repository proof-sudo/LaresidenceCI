{
    'name': 'POS ePOS Direct Printing (Fast)',
    'version': '19.0.1',
    'category': 'Point of Sale',
    'summary': 'Impression ePOS directe sans IoT Box — reçu client et ticket cuisine/bar en commandes texte natives',
    'description': """
Ajoute deux types d'imprimantes ePOS directes au Point de Vente Odoo 19 :

- **Epson ePOS Direct — Reçu client** : imprime le reçu complet après paiement
  (avec prix, totaux, paiements) sans passer par html2canvas.

- **Epson ePOS Direct — Ticket Cuisine / Bar** : imprime un ticket de préparation
  filtré par catégories de produits, en grand format, sans prix.

Avantages par rapport à l'implémentation native :
- Pas de conversion image (gain 300-500 ms par reçu)
- Payload 50× plus léger (XML texte vs image base64)
- Polices natives de l'imprimante (rendu net)
- Compatible imprimantes Epson ePOS sur réseau (TM-T20III Ethernet, TM-m30, TM-T88VII...)
- Aucune dépendance IoT Box
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_printer_log_views.xml',
        'views/pos_printer_form.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pos_epos_direct/static/src/app/backend/test_connection_action.js',
        ],
        'point_of_sale._assets_pos': [
            'pos_epos_direct/static/src/app/utils/printer/epos_direct_printer.js',
            'pos_epos_direct/static/src/app/utils/printer/epos_direct_kitchen_printer.js',
            'pos_epos_direct/static/src/app/overrides/pos_store_patch.js',
        ],
    },
    'installable': True,
    'application': False,
}
