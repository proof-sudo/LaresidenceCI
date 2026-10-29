{
    'name': 'Détection et suppression des produits en doublon',
    'version': '1.0',
    'summary': 'Identifie et supprime les produits dupliqués dans la base de données',
    'category': 'Inventory',
    'depends': ['product'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/product_duplicate_wizard_views.xml',
    ],
    'author': 'La Residence',
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
