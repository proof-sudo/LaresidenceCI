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

## Ce que fait le module

Un enregistrement immuable par action du front POS, horodaté **par le serveur**.

Événements couverts : ouverture de commande · ajout, retrait et modification de
ligne · remise · changement de caissier · **reconnexion silencieuse du caissier
sans code PIN** · affectation de table · transfert · impression de l'addition ·
impression du reçu · validation · suppression de commande.

Chaque ligne porte : horodatage serveur, horodatage tablette et écart entre les
deux, numéro d'appareil, identifiant de poste, caissier, utilisateur technique,
adresse IP, référence et n° d'appel de la commande, table, article et son
libellé figé, quantité, montant, ancienne et nouvelle valeur.

## Garanties

- `write()` et `unlink()` lèvent une erreur pour **tous** les profils,
  administrateur compris.
- L'horodatage serveur, l'utilisateur et l'adresse IP sont posés côté serveur ;
  la tablette ne peut pas les influencer.
- Le libellé de l'article est figé à l'instant de l'événement : renommer une
  fiche article plus tard ne réécrit pas l'historique.
- La file d'attente est recopiée dans le stockage local du navigateur à chaque
  événement : un redémarrage de tablette ne perd rien.
- Un échec d'audit n'interrompt jamais le service — les erreurs sont avalées et
  le lot repart au cycle suivant.

## Rétention

Aucune purge par défaut. Pour en activer une, renseigner le paramètre système
`laresidence_pos_audit.retention_days` avec un nombre de jours strictement
positif, puis activer l'action planifiée « Journal d'audit POS : purge de
rétention ». Chaque purge inscrit elle-même une ligne dans le journal.

## Où le consulter

- Point de vente → Rapports → **Journal d'audit** (responsables POS)
- Bouton **Journal d'audit** sur une commande POS
- Bouton **Journal d'audit** sur une session POS

## Points d'accroche

Relevés sur l'instance, pas supposés — trois ne sont pas là où on les
attendrait :

| Action | Classe | Module |
|---|---|---|
| ouverture, ligne, caissier, table, transfert, suppression, reçu | `PosStore` | `services/pos_store` |
| retrait de ligne | `PosOrder` | `models/pos_order` |
| impression de l'addition | `ControlButtons` | `screens/product_screen/control_buttons` |
| validation | `PaymentScreen` | `screens/payment_screen` |

La classe `OrderPaymentValidation`, qui porte `finalizeValidation`, existe mais
n'est pas exportée par son module : elle est inatteignable depuis un module
tiers. La validation est donc observée une couche au-dessus, sur
`PaymentScreen.validateOrder` — ce qui a l'avantage de déposer l'événement
*avant* que la commande ne parte au serveur.

Un patch dont la méthode cible a disparu est ignoré avec un avertissement en
console : une évolution d'Odoo dégrade l'audit, elle n'empêche jamais la
caisse de démarrer.

## Limites connues

- Les événements sont produits par le navigateur : une tablette qui n'a jamais
  retrouvé le réseau avant d'être réinitialisée perd sa file locale.
- Les modifications faites directement en base de données, hors interface
  caisse, ne sont pas couvertes — elles relèvent du suivi du chatter Odoo.
