# laresidence_hr_control — Contrôle des présences

Auteur : Djakaridja Traore · Odoo 19 · LGPL-3

## Le problème

Odoo enregistre les pointages mais ne les confronte à rien. Un employé qui
prend son poste deux heures avant l'heure, ou qui ne badge jamais sa sortie,
ne déclenche aucune alerte.

Constat sur l'instance au moment de la conception : sur les pointages réels du
mois, **41 % se terminent par une sortie automatique** — une heure de fin
fabriquée par le serveur, que personne ne relit.

## Le choix de conception qui compte : la référence

Deux sources d'horaire coexistent dans Odoo et ne couvrent pas la même population.

| Source | Couverture constatée | Nature |
|---|---|---|
| `planning.slot` | une minorité des employés | créneau daté et nominatif |
| `resource_calendar_id` | la totalité de l'effectif | semaine type |

Le module applique donc : **créneau planning s'il existe, horaire contractuel
sinon**, et aucun écart si ni l'un ni l'autre n'est renseigné. Ne s'appuyer que
sur le planning rendrait le contrôle aveugle pour la majorité des employés — y
compris, dans le cas qui a motivé ce module, celui qui posait problème.

Chaque enregistrement indique la référence effectivement utilisée, pour que la
discussion avec l'employé porte sur une base explicite.

## Écarts détectés

- **Retard à la prise de poste** — entrée après l'heure attendue
- **Prise de poste anticipée** — entrée nettement avant l'heure attendue
- **Départ anticipé** et **dépassement d'horaire**
- **Sortie non badgée** — le pointage a été clôturé par la sortie automatique
- **Absence** — une référence existe, aucun pointage en face
- **Pointage hors référence** — un pointage sans créneau ni horaire correspondant

Les congés validés sont exclus : les intervalles de travail sont calculés avec
les absences, un employé en congé ne génère donc pas d'écart. Les pointages
techniques (lignes de durée nulle produites par la gestion des absences) sont
ignorés.

## Tolérances

Quatre paramètres système, en minutes. Les valeurs par défaut s'appliquent si
le paramètre n'existe pas.

| Paramètre | Défaut |
|---|---|
| `laresidence_hr_control.tolerance_late_in` | 10 |
| `laresidence_hr_control.tolerance_early_in` | 30 |
| `laresidence_hr_control.tolerance_early_out` | 10 |
| `laresidence_hr_control.tolerance_late_out` | 60 |

## Traitement

Chaque écart naît « à examiner ». Un responsable le passe en **justifié** ou
**non justifié**, avec un motif. Le recalcul quotidien ne touche jamais un
écart déjà traité : seules les lignes encore à examiner sont régénérées.

## Alerte

Un récapitulatif quotidien est envoyé par courriel aux membres du groupe
**« Présences : destinataire des alertes d'écart »**. Ajoutez-y le gestionnaire
du planning. Sans membre, aucun envoi.

## Où le consulter

- Présences → Rapports → **Écarts de présence**
- Bouton **Écarts** sur la fiche employé
- Vue croisée employé × type d'écart pour la tendance

## Préalables organisationnels

Deux points relèvent de la direction, pas du module :

1. **Publier le planning.** Les créneaux laissés en brouillon ne sont pas
   communiqués aux employés. On ne peut pas reprocher un écart à une référence
   que personne n'a reçue.
2. **Décider du sort des employés non planifiés** — les étendre au planning, ou
   assumer l'horaire contractuel comme référence pour eux.
