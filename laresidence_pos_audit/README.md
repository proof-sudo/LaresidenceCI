# laresidence_pos_audit — Journal d'audit du Point de Vente

Auteur : Djakaridja Traore · Odoo 19 · LGPL-3

## Le problème

Odoo ne conserve rien de ce qui précède la validation d'une commande POS.

| Donnée | Comportement d'Odoo | Conséquence |
|---|---|---|
| `employee_id` | réécrit à l'ouverture, à chaque ajout de ligne et à la validation | le dernier caissier connecté écrase tous les précédents |
| `date_order` | réécrit au moment de la validation | l'heure d'ouverture réelle disparaît |
| `payment_date` | provient de l'horloge de la tablette | dérive silencieuse, jusqu'à plusieurs semaines |
| Caissier de session | champ unique pour tout le point de vente | inexploitable dès qu'il y a plusieurs tablettes |
| Journal d'audit | inexistant — `ir.logging` ne couvre pas le POS | aucune reconstitution possible |

Résultat concret : sur un ticket contesté, il est impossible d'établir qui a
ouvert la commande, à quelle heure, et sur quel poste.

## Deux couches complémentaires

**1. Le front de caisse** — ce que le serveur ne peut pas voir : impressions,
relèves de caissier, envois en cuisine, actions annulées avant validation.

**2. Les écritures en base** — `create`, `write`, `unlink` interceptés sur
`pos.order`, `pos.order.line`, `pos.payment` et `pos.session`. Aucun
enregistrement Odoo ne peut être modifié sans passer par ces trois méthodes :
cette couche voit donc **tout**, y compris ce qui ne vient pas de la caisse —
back-office, appel externe, import, tâche planifiée.

## Événements couverts

**Session et caissier** — ouverture de session · prise de poste · relève ·
**reconnexion silencieuse sans code PIN** · retour à l'écran de connexion

**Commande** — ouverture · affectation de table · transfert · client rattaché ·
couverts · liste de prix · position fiscale · notes · facturation demandée ·
division de l'addition · suppression

**Lignes** — ajout · retrait · quantité · prix · remise · note *(interceptées
sur le modèle de ligne : quel que soit le bouton, le pavé numérique ou le
raccourci utilisé, elles passent toutes par là)*

**Paiements** — ajout · retrait avant validation · modification de montant ·
mode employé · validation

**Impressions** — addition · reçu · réimpression d'un ticket déjà émis

**Cuisine** — envoi des lignes en préparation

**Base** — création, modification champ par champ, suppression

## Ce que porte chaque ligne

| | |
|---|---|
| **Quand** | horodatage **serveur** faisant foi, horodatage annoncé par la tablette, et l'écart calculé entre les deux |
| **Qui** | caissier en place à cet instant précis, et utilisateur Odoo relevé côté serveur |
| **Où** | adresse IP, chemin technique d'appel, origine (caisse / back-office / traitement automatique) |
| **Sur quoi** | point de vente, session, commande, n° d'appel, table, article et son libellé figé, quantité, montant |
| **Avec quel appareil** | numéro d'appareil Odoo, identifiant de poste stable, navigateur relevé côté serveur, et un relevé matériel complet — plateforme, écran, fenêtre, densité, langue, fuseau, décalage horaire déclaré, tactile, cœurs, mémoire, état du réseau |
| **Quoi exactement** | ancienne et nouvelle valeur, et pour les écritures en base le détail champ par champ |

## Garanties

- `write()` et `unlink()` lèvent une erreur pour **tous** les profils,
  administrateur compris. Vérifié en exécution.
- Horodatage serveur, utilisateur, adresse IP, navigateur et origine sont
  posés côté serveur : la tablette ne peut pas les influencer.
- Le libellé de l'article est figé à l'instant de l'événement — renommer une
  fiche article plus tard ne réécrit pas l'historique.
- La file d'attente est recopiée dans le stockage local du navigateur à chaque
  événement, et repart au chargement de la caisse : un redémarrage de tablette
  ne perd rien.
- Un échec d'audit n'interrompt jamais le service — les erreurs sont avalées,
  le lot repart au cycle suivant, et la couche base est elle-même protégée.

## Points d'accroche

Relevés sur l'instance, pas supposés — plusieurs ne sont pas où on les attendrait :

| Action | Classe |
|---|---|
| ouverture, caissier, table, transfert, suppression, reçu, cuisine, réimpression | `PosStore` |
| retrait de ligne, client, couverts, tarif, notes | `PosOrder` |
| quantité, prix, remise, note de ligne | `PosOrderline` |
| addition, remboursement, position fiscale, division | `ControlButtons` |
| paiements et validation | `PaymentScreen` |

La classe `OrderPaymentValidation`, qui porte `finalizeValidation`, existe mais
n'est pas exportée par son module : elle est inatteignable depuis un module
tiers. La validation est donc observée une couche au-dessus, sur
`PaymentScreen.validateOrder` — ce qui a l'avantage de déposer l'événement
*avant* que la commande ne parte au serveur.

Un patch dont la classe ou la méthode cible a disparu est ignoré avec un
avertissement en console : une évolution d'Odoo dégrade l'audit, elle
n'empêche jamais la caisse de démarrer.

## Rétention

Aucune purge par défaut. Pour en activer une, renseigner le paramètre système
`laresidence_pos_audit.retention_days` avec un nombre de jours strictement
positif, puis activer l'action planifiée « Journal d'audit POS : purge de
rétention ». Chaque purge inscrit elle-même une ligne dans le journal.

## Où le consulter

- Point de vente → Rapports → **Journal d'audit** (responsables POS)
- Bouton **Journal d'audit** sur une commande et sur une session
- Filtres prêts à l'emploi : reconnexions sans code, impressions, paiements,
  modifications de prix ou remise, retraits et suppressions, horloge d'appareil
  décalée, **actions hors interface caisse**, écritures en base
- Regroupements : événement, caissier, appareil, origine, modèle, commande,
  session, date

## Limites connues

- Les événements du front sont produits par le navigateur : une tablette qui
  n'a jamais retrouvé le réseau avant d'être réinitialisée perd sa file locale.
  La couche base, elle, ne dépend d'aucun navigateur.
- Une modification faite directement en SQL, hors ORM, échappe aux deux
  couches. Aucun mécanisme applicatif ne peut la voir.
