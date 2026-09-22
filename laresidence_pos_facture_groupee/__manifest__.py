# -*- coding: utf-8 -*-
{
    'name': "La Résidence — Facture groupée des comptes clients",
    'version': '19.0.1',
    'category': 'Point of Sale',
    'summary': "Une facture unique pour toutes les commandes d'un client réglées en compte client",
    'description': """
Un client qui consomme cinq fois dans la semaine en compte client reçoit
aujourd'hui cinq pièces. Ce module permet d'en émettre **une seule**.

**Un assistant, au bureau.** Menu Point de Vente > Facture groupée — compte
client : on choisit le client et une période, la liste des commandes
éligibles s'affiche, on décoche ce qu'on ne veut pas, et la facture est
créée en brouillon. Rien ne part tant que personne ne l'a validée.

**Le regroupement se fait par entité commerciale.** Les commandes passées au
nom d'un contact remontent avec celles de sa société — sans quoi un même
client recevrait plusieurs factures, ce que ce module est précisément censé
éviter.

**Une ligne par commande.** Référence du ticket et date. Une commande qui
mélange plusieurs taux donne une ligne par taux, le nom de la taxe en
complément : une ligne unique portant le total perdrait la ventilation et la
facture serait fausse fiscalement.

Le montant repris est le prix de vente utilisé par la caisse, remise déduite.
Les taxes 18 % et 9 % étant incluses dans les prix, c'est cette valeur que le
moteur de taxes attend pour retrouver exactement le total du ticket.

**Pas de double facturation possible.** Chaque commande couverte garde le lien
vers sa facture groupée et disparaît des commandes éligibles, y compris pour
un autre utilisateur. La facture, de son côté, affiche les commandes qu'elle
couvre.
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/facture_groupee_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
