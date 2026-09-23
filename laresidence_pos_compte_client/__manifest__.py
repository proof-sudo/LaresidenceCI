# -*- coding: utf-8 -*-
{
    'name': "La Résidence — Comptes clients du point de vente",
    'version': '19.0.5',
    'category': 'Point of Sale',
    'summary': "Traçabilité des lignes de facture et régularisation des commandes en compte client",
    'description': """
Deux compléments au standard, pour les commandes de caisse réglées en
compte client. Tout le reste — le regroupement sur une facture unique,
l'extourne de l'écriture de clôture, la validation — est fait par Odoo et
n'est pas redéveloppé ici.

**Date de consommation et référence du ticket sur chaque ligne.**

Odoo sait regrouper plusieurs commandes de caisse sur une facture unique,
mais il empile les articles sans dire de quel jour ni de quel ticket ils
viennent. Sur une facture couvrant un mois, quatre articles identiques se
suivent sans qu'on puisse les rattacher à un repas — le client ne peut pas
rapprocher de ses propres notes, et une contestation devient impossible à
instruire.

Chaque ligne devient donc « Mérou Laqué — 27/07/2026, ticket Desk - 000144 ».

Le repère est porté par le **libellé** et non par un intertitre, pour deux
raisons. Le libellé survit à n'importe quel modèle d'impression, alors
qu'un intertitre dépend du rapport. Et c'est le libellé que le connecteur
DGI transmet comme description de l'article : un intertitre, dépourvu
d'article, n'est pas envoyé du tout.

**Un écran guidé pour facturer.**

Le chemin natif demande plusieurs gestes et deux filtres, dont un que rien
ne rappelle : ne retenir que le compte client. Le menu ``Point de Vente >
Comptes clients`` propose donc deux entrées. « Comptes clients à facturer »
montre, regroupé par client, tout ce qui reste à facturer. « Facturer un
compte client » demande un client et une période, présente les
consommations éligibles déjà cochées, et prévient quand elles sont
réparties sur plusieurs fiches — une option permet alors de tout rattacher
à la société pour n'obtenir qu'une facture.

La facturation elle-même est confiée à l'assistant natif d'Odoo : facture
consolidée, extourne des écritures de clôture des sessions fermées et
validation sont de son ressort, pas du nôtre.

**Régularisation d'une commande payée.**

Odoo interdit de repasser une commande payée à l'état « annulé » : le noyau
n'autorise que paid, done et invoiced. Depuis la liste des commandes, une
sélection et un motif suffisent. Pour chaque commande, l'avoir est créé
article par article, **validé** et **lettré** contre la créance ouverte du
client ; la commande est marquée régularisée, avec le motif, l'auteur, la
date et le lien vers l'avoir.

Un seul geste, et rien ne reste en suspens. C'est délibéré : un avoir
laissé en brouillon laisserait la commande marquée « régularisée » alors
que rien n'aurait été extourné — le client devrait toujours l'argent, et
plus personne ne le facturerait.

Le lettrage n'a lieu que si une seule créance ouverte correspond, au nom du
même tiers, pour le montant exact et dans l'écriture de clôture de la
session concernée. En cas de doute, le module s'abstient et le consigne
dans le journal du serveur plutôt que de solder la mauvaise créance.

Pour un règlement autre que le compte client, dont la ligne de tiers est
déjà lettrée, l'assistant prévient nommément : il restera un rapprochement
manuel avec l'écriture d'origine.
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/facturation_views.xml',
        'wizard/regularisation_views.xml',
        'views/pos_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
