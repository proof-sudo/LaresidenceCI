# -*- coding: utf-8 -*-
{
    'name': "La Résidence — Blocage total des envois d'e-mails",
    'version': '19.0.1',
    'category': 'Productivity/Discuss',
    'summary': "Aucun e-mail ne peut sortir de la base, quelle qu'en soit l'origine",
    'description': """
Cette base ne doit émettre aucun e-mail : ni facture, ni devis, ni relance,
ni rappel d'abonnement, ni confirmation d'inscription, ni campagne.

Désactiver les tâches planifiées émettrices ne suffit pas : une grande partie
des envois est immédiate et ne passe par aucune tâche — le bouton « Envoyer »
d'une facture ou d'un devis, le reçu de caisse, la confirmation d'inscription
à un événement, l'invitation d'un utilisateur. Le seul contrôle fiable est
donc placé au point de passage unique par lequel tout sort.

Deux verrous, indépendants l'un de l'autre :

1. **File des messages.** ``mail.mail.send()`` ne remet plus rien au serveur :
   chaque message est marqué « annulé », avec le motif inscrit dans la fiche.
   Aucune erreur n'est levée, donc aucun processus métier n'est interrompu.

2. **Remise SMTP.** ``ir.mail_server.connect()`` et ``send_email()`` refusent
   la connexion. Ce second verrou couvre les rares envois qui ne passent pas
   par la file — accusés de rejet, bouton de test de connexion.

Chaque blocage est écrit dans le journal du serveur, donc traçable.

**Pour rétablir les envois**, il suffit de désinstaller ce module. Rien
d'autre n'est modifié dans la base.
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': ['mail'],
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
