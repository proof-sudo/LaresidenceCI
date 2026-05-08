{
    'name': 'La Résidence - Menu Security',
    'version': '19.0.2.0.2',
    'summary': 'Restreint la visibilité des menus aux groupes spécifiques de chaque module',
    'author': 'Djakaridja Traore : djakaridjatraore@outlook.com',
    'depends': [
        'base', 'mail', 'calendar', 'contacts', 'appointment',
        'project_todo', 'knowledge', 'sale_renting',
        'sale', 'sales_team', 'spreadsheet_dashboard',
        'documents', 'planning', 'website', 'social',
        'hr', 'hr_holidays', 'approvals', 'whatsapp',
        'frontdesk',
    ],
    'data': [
        'security/security.xml',
        'security/ir_rules.xml',
        'views/menu_security.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
