{
    'name': 'La Résidence - Menu Security',
    'version': '19.0.1.0.0',
'summary': 'Restreint la visibilité des menus aux groupes spécifiques de chaque module',
    'author': 'Djakaridja Traore',
    'depends': [
        'base', 'mail', 'calendar', 'contacts', 'appointment',
        'project_todo', 'knowledge', 'booking_engine',
        'sale', 'sales_team', 'spreadsheet_dashboard',
        'documents', 'planning', 'website', 'social',
        'hr', 'hr_holidays', 'approvals', 'whatsapp',
    ],
    'data': [
        'security/security.xml',
        'views/menu_security.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
