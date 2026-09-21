# -*- coding: utf-8 -*-
{
    'name': "La Résidence — Fermeture automatique de caisse",
    'version': '19.0.1',
    'category': 'Point of Sale',
    'summary': "Verrouille la caisse à une heure définie, si plus rien n'est en cours — alerte sinon",
    'description': """
Une session de caisse laissée ouverte ne génère aucune écriture comptable et
fait perdre le seul point de contrôle quotidien disponible. Au moment de la
conception, une session de ce point de vente était ouverte depuis deux jours,
avec dix-huit commandes et aucune écriture.

Le module ferme la caisse à une heure définie par point de vente, mais
seulement si plus rien n'est en cours. Trois conditions, toutes vérifiées
côté serveur :

1. aucune commande à l'état brouillon — donc aucune table ouverte ;
2. aucune ligne en attente sur les écrans de préparation (cuisine, bar) ;
3. aucune commande créée depuis un délai d'inactivité réglable.

La troisième condition n'est pas décorative : sans elle, on risque de fermer
sous les pieds d'une tablette qui n'a pas fini de synchroniser.

**Si une condition bloque**, rien n'est fermé et une alerte part vers les
destinataires désignés, en nommant précisément ce qui reste en cours.

**Comptage de caisse.** Fermeture automatique et contrôle de caisse tirent en
sens inverse : une session avec comptage exige un montant déclaré que personne
n'a compté à 3 h du matin. Par défaut le module se contente donc de
**verrouiller** la session (état « contrôle de fermeture ») : plus aucune
commande ne peut y être prise, et le comptage se fait au matin. La clôture
comptable complète reste disponible en option, point de vente par point de vente.
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'pos_restaurant_preparation_display',
    ],
    'data': [
        'security/pos_close_groups.xml',
        'views/pos_config_views.xml',
        'views/pos_session_views.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
