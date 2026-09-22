# -*- coding: utf-8 -*-
{
    'name': "La Résidence — Facture groupée des comptes clients",
    'version': '19.0.4',
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

**Deux niveaux de détail, au choix à chaque facture.**

*Articles regroupés par ticket* — le réglage par défaut. Un intertitre par
ticket, puis les articles réellement consommés. Le client voit ce qu'il a
pris et quand, ce qu'une référence de ticket ne dit pas. Chaque ligne portant
sa propre taxe, la ventilation de TVA est exacte sans traitement particulier,
et les intertitres ne portent aucun montant.

*Une ligne par ticket* — référence et date seulement, pour un compte au
volume important. Une commande qui mélange plusieurs taux donne alors une
ligne par taux : une ligne unique portant le total perdrait la ventilation et
la facture serait fausse fiscalement.

Dans les deux cas le montant repris est le prix de vente utilisé par la
caisse, remise déduite. Les taxes 18 % et 9 % étant incluses dans les prix,
c'est cette valeur que le moteur de taxes attend pour retrouver exactement le
total du ticket.

**Pas de double facturation possible.** Chaque commande couverte garde le lien
vers sa facture groupée et disparaît des commandes éligibles, y compris pour
un autre utilisateur. La facture, de son côté, affiche les commandes qu'elle
couvre.

**Régulariser une commande.** Odoo interdit de repasser une commande payée à
l'état « annulé » : le noyau n'autorise que ``paid``, ``done`` et
``invoiced``. Plutôt que de forcer cet état, le module marque la commande
comme **régularisée** et crée l'avoir correspondant en brouillon, article par
article. La commande dit alors la vérité : elle a existé, elle a été
extournée — et elle sort définitivement de la facturation groupée.

L'assistant se lance depuis la liste des commandes, sur une sélection. La
caisse imputant toutes les méthodes de règlement au compte de tiers, l'avoir
au client est la contrepartie correcte dans tous les cas. Pour un règlement
autre que le compte client, dont la ligne de tiers est déjà lettrée,
l'assistant prévient : il restera un rapprochement manuel avec l'écriture
d'origine, et l'encaissement correspondant à défaire.
    """,
    'author': 'Djakaridja Traore',
    'license': 'LGPL-3',
    'depends': ['point_of_sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/facture_groupee_views.xml',
        'wizard/regularisation_views.xml',
        'views/account_move_views.xml',
        'views/pos_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
