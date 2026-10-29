{
    'name': 'Sale Renting ↔ POS Restaurant Bridge',
    'version': '19.0.1',
    'category': 'Sales / Point of Sale',
    'summary': 'Lien entre location de salles et réservation POS',
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': [
        'sale_renting',
        'point_of_sale',
        'pos_restaurant',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/reservation_sequence.xml',

        'views/product_template_views.xml',
        'views/restaurant_floor_views.xml',
        'views/pos_room_reservation_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
