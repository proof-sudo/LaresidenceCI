{
    'name': 'Direct Network ESC/POS Printer',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Print directly to network ESC/POS printers without IoT Box',
    'author': 'KAALIMBA',
    'license': 'LGPL-3',
    'depends': ['point_of_sale'],
    'data': [
        'views/pos_printer_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_direct_printer/static/src/app/**/*',
        ],
        'web.assets_backend': [
            'pos_direct_printer/static/src/backend/**/*',
        ],
    },
    'installable': True,
}
