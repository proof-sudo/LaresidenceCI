# -*- coding: utf-8 -*-
{
    'name': 'La Résidence — Pointage QR Badge',
    'version': '19.0.1',
    'category': 'Human Resources/Attendances',
    'summary': 'Pointage présence via QR code — fonctionne sur tout appareil',
    'description': """
        Permet aux employés de pointer leur arrivée/départ en scannant
        un QR code personnel imprimé sur leur badge.
        Aucun matériel RFID/NFC requis — tout appareil avec appareil photo suffit.

        Fonctionnalités :
        - Token sécurisé unique par employé (secrets.token_urlsafe)
        - Image QR persistée en base de données (store=True)
        - Endpoint public : /laresidence/attendance/qr/scan/<token>
        - Logique bascule : présence ouverte -> départ ; sinon -> arrivée
        - Badge imprimable (PDF QWeb) avec photo, infos, QR
        - Regeneration du token avec confirmation
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': [
        'hr_attendance',
    ],
    'data': [
        'security/ir.model.access.csv',
        'report/hr_attendance_badge_report.xml',
        'report/hr_attendance_badge_template.xml',
    ],
    'assets': {
        'hr_attendance.assets_public_attendance': [
            'laresidence_attendance_qr/static/src/kiosk_qr_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
