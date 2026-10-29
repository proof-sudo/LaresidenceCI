{
    'name': 'FNE Connector - Ventes (objet du marché)',
    'version': '19.0.1.0.0',
    'summary': "Objet du marché saisi sur le devis, repris sur la facture et envoyé à la FNE",
    'author': 'Neurones Technologies',
    'license': 'AGPL-3',
    'category': 'Accounting',
    'depends': ['odoo_fne_connector', 'sale'],
    'data': ['views/sale_order_views.xml'],
    'installable': True,
    'application': False,
    'auto_install': True,
}
