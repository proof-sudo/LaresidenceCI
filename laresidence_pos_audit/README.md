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

## Intégrité — le journal se surveille lui-même

Bloquer `write()` et `unlink()` ne vaut que dans l'application. Un accès direct
à la base contourne l'ORM et n'y laisse rien.

Chaque ligne porte donc un **numéro d'ordre continu** et l'**empreinte** de son
propre contenu combinée à celle de la ligne précédente. Retirer une ligne,
en insérer une, ou en retoucher une seule valeur rompt la chaîne à partir de ce
point. C'est le principe retenu par Odoo pour l'inaltérabilité des factures.

**Éprouvé en conditions réelles**, par deux instructions SQL passées
directement en base, hors d'Odoo :

```sql
UPDATE laresidence_pos_audit SET note = 'x' WHERE sequence_no = 400;
DELETE FROM laresidence_pos_audit WHERE sequence_no = 402;
```
> Anomalie détectée — 744 ligne(s) contrôlées.
> Numérotation interrompue : entre 401 et 403.
> Première anomalie au n° 400 (contenu modifié).

### Le scellé est posé après coup, jamais pendant un encaissement

Un chaînage se calcule en série. Le calculer dans la transaction d'une vente
obligerait chaque tablette à attendre son tour — exactement le ralentissement
qu'un journal d'audit ne doit pas provoquer.

L'écriture d'une ligne est donc un simple `INSERT`, sans verrou ni relecture.
Une tâche planifiée numérote et scelle les lignes en attente **chaque minute**,
en dehors de tout encaissement.

| | Dans la transaction de vente | Hors transaction |
|---|---|---|
| Écriture d'une ligne | 1 `INSERT` | |
| Numérotation, chaînage, empreinte | | tâche chaque minute |

Conséquence assumée : les lignes de la dernière minute ne sont pas encore
protégées. Le contrôle d'intégrité l'annonce explicitement — « n lignes
récentes pas encore scellées » — plutôt que de le passer sous silence, et le
filtre **Pas encore scellées** les isole.

L'action **« Vérifier l'intégrité du journal »**, disponible depuis la liste,
recalcule toute la chaîne et désigne la première anomalie : trou dans la
numérotation, chaînage rompu, ou contenu modifié.

Un enquêteur ne demande pas si les données sont vraies — il demande comment on
le prouve. C'est cette question-là que la chaîne répond.

## Ce qui est surveillé hors caisse

Un détournement se prépare rarement dans la commande elle-même. Quinze modèles
sont donc suivis en écriture, dont :

| Modèle | Ce que ça révèle |
|---|---|
| `product.template` / `product.product` | **prix modifié en plein service** — l'incident du 11 septembre |
| `res.users`, `res.groups` | quelqu'un qui s'attribue des droits |
| `hr.employee` | code PIN ou badge réattribué |
| `pos.config` | contrôle de caisse désactivé, droits POS élargis |
| `pos.payment.method`, `account.journal` | mode de paiement redirigé vers un autre journal |
| `ir.config_parameter` | **le paramètre de purge de ce journal** |
| `ir.cron` | une tâche planifiée activée ou coupée |
| `resource.calendar` | horaires de référence retouchés |
| `res.device.log` | **chaque nouvelle session** : plateforme, navigateur, IP, pays, ville |

### Les clés d'accès permanentes : un cas à part

Une clé d'API donne un accès complet au compte, sans mot de passe et sans
double authentification, tant que personne ne la révoque. C'est le moyen le
plus discret de garder la main sur la base après coup, et il fallait donc le
couvrir.

Il ne pouvait pas l'être de la même façon que les autres. Odoo crée et
supprime ces clés en SQL direct, sans passer par l'ORM — `res.users.apikeys`
est déclaré `_auto = False` et `_generate` fait son `INSERT` lui-même. Une
surveillance posée sur `create` ne se serait jamais déclenchée : elle aurait
donné l'apparence d'une couverture, ce qui est pire que pas de couverture du
tout.

Le relevé se fait donc autrement : une fois par minute, le contenu réel de la
table est comparé à ce que le journal a déjà constaté. Toute clé apparue
produit une ligne `api_key_create` — datée de sa **création réelle**, pas du
relevé — et toute clé disparue une ligne `api_key_remove`. Les appareils de
confiance de la double authentification sont traités de la même manière.

Deux limites, dites franchement :

- la détection a jusqu'à une minute de retard sur le fait ;
- une clé créée **puis supprimée** à l'intérieur de cette même minute ne
  laisse aucune ligne : l'enregistrement a disparu de la table avant d'être
  relu. Odoo trace cependant sa création dans le journal technique du serveur,
  qui n'est pas modifiable depuis l'application.

Les valeurs secrètes — mots de passe, codes PIN, jetons — ne sont **jamais**
recopiées : on enregistre qu'elles ont changé, pas ce qu'elles valent. Un
journal de sécurité qui recopie un code PIN devient lui-même le problème.

## Connexions

Chaque session ouverte laisse une ligne : utilisateur, plateforme, navigateur,
adresse IP, pays et ville. Elle vient du modèle `res.device.log`, qu'Odoo 19
alimente lui-même et que ce module suit — aucune intervention dans le chemin
d'authentification.

**Les tentatives de connexion refusées ne sont pas captées en base.** Elles
n'existent que dans le journal du serveur.

Ce n'est pas un oubli. Les capturer suppose de s'intercaler dans `_login`, ce
qui a été tenté et retiré : deux échecs de construction consécutifs, dont un
qui rendait toute connexion impossible. Une faute à cet endroit met tout le
monde dehors, personnel comme administrateur, et aucune vérification statique
ne la révèle — l'installation se passe bien, c'est la connexion qui échoue.

La fonction reste souhaitable et sera reprise à part, avec un mécanisme qui ne
touche pas au chemin d'authentification : lecture différée du journal serveur
par une tâche planifiée, ou exploitation des compteurs internes d'Odoo. Les
types d'événement `auth_success` et `auth_failure` restent déclarés pour
l'accueillir.

En attendant, les échecs de connexion se lisent dans `~/logs/odoo.log` de
l'instance, à la ligne « Login failed ».

## Qui consulte le journal

La lecture du journal y est notée, une fois par utilisateur et par quart
d'heure. Savoir qui a consulté les traces fait partie des traces.

## Adresses : trois niveaux

| | |
|---|---|
| **Adresse publique** | vue par le serveur — identique pour toutes les tablettes du restaurant |
| **Chaîne d'adresses** | relais traversés compris : un intermédiaire ne peut pas masquer l'origine |
| **Adresse locale** | relevée par le navigateur de l'appareil — c'est elle qui distingue deux tablettes derrière le même routeur |

Les navigateurs récents remplacent souvent l'adresse locale par un nom en
`.local`. Il ne donne pas l'adresse, mais il est propre à l'appareil et stable :
il suffit à les différencier.

S'y ajoute l'**empreinte de session**, qui relie toutes les actions d'une même
connexion. L'identifiant de session lui-même n'est jamais stocké : il serait
réutilisable par quiconque lirait le journal.

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
- L'envoi est asynchrone et groupé. Au moment de la validation d'une commande,
  où l'on veut que la trace parte avant que le serveur ne réécrive l'employé et
  l'heure, l'attente est **bornée à une seconde et demie** : au-delà on rend la
  main. La file étant conservée dans le navigateur, rien n'est perdu pour
  autant.
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

## Qui peut voir le journal

Deux droits, et rien par défaut :

- **Journal d'audit : consultation** — sans lui, le menu n'apparaît pas et les
  enregistrements sont hors de portée, y compris pour un responsable de caisse.
- **Journal d'audit : administration** — permet en plus de définir le code et
  de désigner qui consulte.

La liste se règle dans *Point de vente → Configuration → Accès au journal
d'audit*. Toute modification de cette liste est elle-même inscrite dans le
journal.

## Le code d'accès

Appartenir au groupe ne suffit pas. Le code est demandé à l'ouverture du
journal, puis l'accès reste ouvert quinze minutes (durée réglable). Il protège
aussi la **désinstallation du module**.

- Le code n'est jamais conservé en clair : seule son empreinte salée l'est.
- Trois échecs en quinze minutes bloquent les tentatives suivantes.
- Chaque saisie, réussie ou non, est inscrite dans le journal — comme les
  tentatives de désinstallation refusées.

Tant qu'aucun code n'est défini, l'accès reste ouvert aux membres du groupe :
le module doit rester utilisable au moment de son installation.

Les méthodes qui ouvrent l'accès, définissent le code ou déposent une ligne
dans le journal ne sont **pas appelables à distance** : elles sont privées au
sens d'Odoo. Sans cette précaution, il suffirait d'un appel direct pour
s'ouvrir l'accès sans code, ou pour injecter de fausses lignes dans le
journal. Seuls le point d'entrée du menu et les assistants sont exposés, et
chacun vérifie le droit et le code avant d'agir.

### Ce que cette protection vaut, et ce qu'elle ne vaut pas

Contre un employé, un caissier ou un responsable de salle, l'occultation est
complète.

Contre un administrateur Odoo, **aucune protection applicative ne tient** : il
peut s'ajouter au groupe, réécrire les droits d'accès, ou désinstaller le
module en ligne de commande. Ce n'est pas une faiblesse de ce module, c'est la
nature du rôle d'administrateur.

L'objectif retenu est donc différent, et atteignable : rendre chacun de ces
gestes **délibéré et inscrit**. S'ajouter au groupe modifie `res.groups` —
journalisé. Réécrire un droit modifie `ir.model.access` — journalisé. Saisir ou
changer le code — journalisé. Tenter la désinstallation — journalisé et
refusé. Et comme la chaîne d'empreintes rend toute suppression détectable,
effacer ces traces ne les fait pas disparaître : cela laisse un trou visible.

On ne prétend pas rendre le contournement impossible. On le rend voyant.

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
- Les clés d'accès permanentes sont relevées par comparaison et non
  interceptées : jusqu'à une minute de retard, et une clé créée puis supprimée
  dans cet intervalle passe inaperçue (voir plus haut).
- La création d'une clé d'API est tracée par Odoo dans le journal technique du
  serveur. Ce journal n'est pas couvert par le scellé de ce module : il relève
  de l'hébergement.
