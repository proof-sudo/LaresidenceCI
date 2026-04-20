# -*- coding: utf-8 -*-
{
    'name': 'HR Attendance QR Code',
    'version': '17.0.1.0.1',
    'category': 'Human Resources/Attendances',
    'summary': 'Pointage présence via QR code — fonctionne sur tout appareil',
    'description': """
        Permet aux employés de pointer leur arrivée/départ en scannant
        un QR code personnel imprimé sur leur badge.
        Aucun matériel RFID/NFC requis — tout appareil avec appareil photo suffit.

        Fonctionnalités :
        - Token sécurisé unique par employé (secrets.token_urlsafe)
        - Image QR calculée et intégrée dans le badge PDF
        - Endpoint public : /hr/attendance/qr/scan/<token>
        - Logique bascule : présence ouverte → départ ; sinon → arrivée
        - Badge imprimable (PDF QWeb) avec photo, infos, QR
        - Régénération du token avec confirmation
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': [
        'hr_attendance',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'report/hr_attendance_badge_report.xml',
        'report/hr_attendance_badge_template.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
