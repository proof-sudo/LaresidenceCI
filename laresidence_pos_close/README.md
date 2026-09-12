# laresidence_pos_close — Fermeture automatique de caisse

Auteur : Djakaridja Traore · Odoo 19 · LGPL-3

## Le problème

Une session de caisse laissée ouverte ne génère aucune écriture comptable et
fait perdre le seul point de contrôle quotidien disponible. Au moment de la
conception, une session de ce point de vente était ouverte **depuis deux
jours**, avec dix-huit commandes et aucune écriture — alors qu'à cet instant
précis plus aucune commande n'était en cours et plus rien n'attendait en
cuisine.

## Les trois conditions

La fermeture n'a lieu que si les trois sont remplies, toutes vérifiées côté
serveur :

1. **Aucune commande à l'état brouillon** — donc aucune table ouverte.
2. **Aucune ligne en attente sur les écrans de préparation** (cuisine, bar),
   étape « À envoyer » comprise : un plat prêt mais pas encore servi compte
   comme un service en cours. Désactivable point de vente par point de vente.
3. **Aucune commande créée depuis le délai d'inactivité** (30 minutes par
   défaut). Cette condition n'est pas décorative : sans elle, on risque de
   fermer sous les pieds d'une tablette qui n'a pas fini de synchroniser.

Si une condition bloque, **rien n'est fermé** et une alerte part en nommant
précisément ce qui reste en cours — nombre de commandes ouvertes et numéros de
table, nombre de préparations en attente et étape où elles se trouvent.

## Verrouiller plutôt que clôturer

Fermeture automatique et contrôle de caisse tirent en sens inverse : une
session avec comptage exige un montant déclaré que personne n'a compté à 3 h
du matin.

Par défaut, le module **verrouille** la session — état « contrôle de
fermeture » : plus aucune commande ne peut y être prise, la coupure est nette,
et le comptage se fait au matin. La clôture comptable complète reste
disponible en option (`Tenter la clôture comptable`), à réserver aux points de
vente sans espèces.

## Réglages

Sur la fiche du point de vente : activation, heure de fermeture, délai
d'inactivité, blocage par les bons de préparation, clôture comptable. La
dernière tentative et son résultat y sont affichés.

La tâche planifiée tourne toutes les 30 minutes. Elle n'agit que dans une
fenêtre de 4 heures après l'heure cible : sans cette fenêtre, une heure fixée
à 03h00 serait considérée comme dépassée dès 23h00 le soir même. Une session
ouverte *après* l'heure cible appartient au service suivant et n'est pas touchée.

## Alertes

Aux membres du groupe **« Caisse : destinataire des alertes de fermeture »**.
Sans membre, aucun envoi. Chaque tentative laisse aussi une trace dans le
journal de la session.

## Vérification manuelle

Action **« Vérifier si la caisse peut être fermée »** disponible depuis la
liste ou la fiche d'une session : elle affiche ce qui bloque, sans rien fermer.
