{
    'name': 'POS ePOS Direct Printing (Fast)',
    'version': '19.0.2',
    'category': 'Point of Sale',
    'summary': 'Impression ePOS directe sans IoT Box — via relais PC local (compatible iPad/Safari)',
    'description': """
Ajoute deux types d'imprimantes ePOS directes au Point de Vente Odoo 19 :

- **Epson ePOS Direct — Reçu client** : imprime le reçu complet après paiement
  (avec prix, totaux, paiements) sans passer par html2canvas.

- **Epson ePOS Direct — Ticket Cuisine / Bar** : imprime un ticket de préparation
  filtré par catégories de produits, en grand format, sans prix.

Architecture v2 — relais via agent PC local (pos_print_job) :
    Le navigateur ne contacte plus jamais l'imprimante directement (iOS/Safari
    bloque les appels d'un navigateur vers une IP locale via la restriction
    "Local Network Access" — les tickets échouaient silencieusement sur iPad).
    Le navigateur crée un job en file d'attente via un RPC léger vers Odoo ;
    un agent Python tournant sur un PC du réseau local de l'imprimante
    (voir agent/pos_print_relay_agent.py) récupère les jobs en polling sortant
    et les envoie à l'imprimante. Fonctionne sur Odoo.sh, sans port forwarding.

Avantages par rapport à l'implémentation native :
- Pas de conversion image (gain 300-500 ms par reçu)
- Payload 50× plus léger (XML texte vs image base64)
- Polices natives de l'imprimante (rendu net)
- Compatible imprimantes Epson ePOS sur réseau (TM-T20III Ethernet, TM-m30, TM-T88VII...)
- Aucune dépendance IoT Box
- Compatible iPad/Safari (contournement de la restriction Local Network Access)
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
