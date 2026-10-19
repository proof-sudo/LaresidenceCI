# -*- coding: utf-8 -*-
{
    'name': "La R\u00e9sidence \u2014 Suivi des \u00e9tapes de pr\u00e9paration",
    'version': '19.0.1',
    'category': 'Point of Sale',
    'summary': "Historise chaque passage d'\u00e9tape en cuisine et au bar, avec sa dur\u00e9e",
    'description': """
Odoo sait dans quelle \u00e9tape se trouve un plat, et \u00e0 quelle heure il y est
entr\u00e9 pour la derni\u00e8re fois. Il ne garde rien de ce qui pr\u00e9c\u00e8de : impossible
de dire combien de temps un plat est rest\u00e9 en cuisson, ni de comparer deux
services.

Ce module enregistre **chaque passage d'\u00e9tape** comme un fait dat\u00e9 :
plat, poste, \u00e9tape, heure d'entr\u00e9e, heure de sortie, dur\u00e9e, seuil d'alerte
configur\u00e9 et auteur du changement. Rien n'est recalcul\u00e9 apr\u00e8s coup.

Il ajoute aussi l'\u00e9tape **Servi**, que le parcours natif n'a pas : le
parcours s'arr\u00eate au passe, alors que le temps qui int\u00e9resse la salle est
celui qui s\u00e9pare l'envoi en cuisine de l'assiette pos\u00e9e devant le client.

**Garde-fou.** Un plat ne peut \u00eatre d\u00e9clar\u00e9 servi que s'il a r\u00e9ellement \u00e9t\u00e9
marqu\u00e9 pr\u00eat par la cuisine. Le contr\u00f4le est refait c\u00f4t\u00e9 serveur Odoo et pas
seulement \u00e0 l'\u00e9cran : une tablette qui a perdu le r\u00e9seau peut envoyer une
validation p\u00e9rim\u00e9e. Un for\u00e7age reste possible lorsque la cuisine a oubli\u00e9 de
marquer le plat pr\u00eat \u2014 il est alors enregistr\u00e9 comme tel et ressort dans
l'analyse, pour que l'oubli devienne un chiffre plut\u00f4t qu'un angle mort.
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'pos_restaurant',
        'pos_restaurant_preparation_display',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/prep_passage_views.xml',
        'views/pos_order_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
