{
    'name': 'MRP Auto BoM Cost Cascade',
    'version': '1.0',
    'summary': 'Recalcul automatique en cascade des coûts de nomenclatures',
    'description': """
        Lorsque le prix standard (standard_price) d'un composant est modifié,
        ce module recalcule automatiquement le coût de toutes les nomenclatures
        (BoM) qui utilisent ce composant, en cascadant récursivement à travers
        les nomenclatures imbriquées.
    """,
    'category': 'Manufacturing',
    'depends': ['mrp_account'],
    'data': [
        'views/mrp_bom_views.xml',
    ],
    'author': 'La Residence',
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
