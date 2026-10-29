{
    'name': 'Validation achat par catégorie de produit',
    'version': '19.0.1.0.0',
    'summary': 'Bloque la confirmation des bons de commande selon la catégorie du produit et envoie une approbation au manager',
    'category': 'Purchase',
    'author': 'Neurones Technologies',
    'license': 'AGPL-3',
    'depends': ['purchase', 'approvals'],
    'data': [
        'security/ir.model.access.csv',
        'data/approval_category_data.xml',
        'views/purchase_approval_rule_views.xml',
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
