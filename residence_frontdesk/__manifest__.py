{
    'name': 'Frontdesk — Lien Contact (res.partner)',
    'version': '1.0',
    'summary': 'Lie les visiteurs frontdesk à un contact res.partner existant ou à créer',
    'description': """
        Ajoute un champ "Contact" (res.partner) sur les visiteurs frontdesk.
        Lorsqu'un contact est sélectionné, le nom, le téléphone, l'email et
        la société sont automatiquement remplis depuis le contact.
        Compatible avec le kiosk (saisie manuelle du nom toujours possible).
    """,
    'category': 'Front Desk',
    'depends': ['frontdesk'],
    'data': [
        'views/frontdesk_visitor_views.xml',
    ],
    'author': 'La Residence',
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
