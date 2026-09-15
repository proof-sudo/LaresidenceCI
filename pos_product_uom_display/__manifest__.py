{
    'name': 'POS - Affichage UoM sur produits',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'summary': "Affiche l'unité de mesure sur chaque carte produit dans le POS",
    'depends': ['point_of_sale', 'uom'],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_product_uom_display/static/src/product_card_uom.xml',
            'pos_product_uom_display/static/src/product_card_uom.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
