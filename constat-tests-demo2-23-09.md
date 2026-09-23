# Campagne de tests sur demo2 — 23/09/2026

Tous les constats ci-dessous proviennent d'interrogations directes des bases.
Aucune conclusion n'est donnée sans le chiffre qui la porte.

---

## 1. Mise en condition

| Action | Résultat |
|---|---|
| `fne.mode` sur demo2 | `prod` → **`test`** (vérifié après écriture) |
| `fne.mode` en production | reste `prod`, non touché |
| `laresidence_mail_blocage` sur demo2 | installé 19.0.3 |

Avant la bascule, demo2 pointait sur `https://www.services.fne.dgi.gouv.ci/ws`
avec la clé de production. Toute certification lancée depuis demo2 serait
partie à la DGI.

## 2. Blocage des envois de mails

Message de contrôle créé sur demo2, adressé à `controle@example.invalid` :
état `cancel`, motif « Envoi bloque : cette base n'est pas autorisee a emettre
des e-mails. »

demo2 contenait **9 messages en attente**, dont des inscriptions à des
événements adressées à de vraies adresses clients. Ils sont désormais bloqués.

### Contrôle de la production

Module installé le **21/09/2026 à 19h09**. Messages à l'état « envoyé » :

| Date | Destinataire | Nature |
|---|---|---|
| 21/09 19h35 | test5@example.invalid | test de la fenêtre temporaire |
| 09/09 | info@adenka.ci | antérieur à l'installation |
| 04/09 et avant | divers | antérieurs à l'installation |

**Aucun message réel n'est sorti de la production depuis la mise en place du
verrou.** Deux messages restent en attente, tous deux internes.

## 3. Facture groupée compte client — parcours complet

Client retenu : **INPHB YAMOUSSOUKRO**, 3 consommations en compte client sur
3 dates et 3 sessions différentes.

| Commande | Date | Montant |
|---|---|---|
| Desk - 000004 | 17/07/2026 | 376 265 |
| Desk - 000010 | 21/07/2026 | 136 716 |
| Desk - 000028 | 31/07/2026 | 131 335 |
| **Total** | | **644 316** |

### Résultat

**Une seule facture** : `INV/2026/00197`, comptabilisée, 644 316 CFA,
6 lignes, origine « 260-1-000028, 260-1-000010, 260-1-000004 ».

Libellés produits obtenus, exemple :

```
Pause-café matin
Eau, café/thé, jus de fruits, viennoiserie — 31/07/2026, ticket Desk - 000028
[100599594] Eau pétillante Kirene, 75 cl — 31/07/2026, ticket Desk - 000028
```

Le produit réellement commandé, la date de consommation et la référence du
ticket figurent bien sur chaque ligne.

### Contrôle du compte client

| | Montant |
|---|---|
| Solde créance avant | 8 958 063 |
| Solde créance après facturation | 8 958 063 |
| **Écart** | **0** |

Trois écritures d'extourne ont été produites automatiquement :

| Pièce | Montant |
|---|---|
| POSS/2026/09/0030 — extourne POSS/2026/07/0005, Desk - 000004 | −376 265 |
| POSS/2026/09/0029 — extourne POSS/2026/07/0013, Desk - 000010 | −136 716 |
| POSS/2026/09/0028 — extourne POSS/2026/08/0001, Desk - 000028 | −131 335 |

**Le client n'est pas débité deux fois.** La facture remplace exactement les
créances portées par les clôtures de caisse.

## 4. Certification FNE — non rejouable en l'état

Appel réel vers l'environnement de test :

```
FNE POST http://54.247.95.108/ws/external/invoices/sign
401 — {'message': 'Invalid API Key', 'error': 'unauthorized'}
```

L'adresse de test répond, donc elle est joignable. La clé configurée est celle
de production, que l'environnement de test refuse. **Il faut une clé API de
test pour rejouer ce parcours.** La facture est restée non certifiée.

## 5. Paiements sans écriture comptable — à examiner

Constat fait d'abord sur demo2, puis vérifié sur la production.

### Production

| Mesure | Valeur |
|---|---|
| Paiements au total | 358 |
| Paiements sans aucune pièce comptable | 91 |
| dont à l'état « payé » | **69** |
| Montant de ces 69 paiements | **212 756 023 CFA** |
| Factures liées | 68 |
| Factures affichant encore un reste dû | **67** |
| Total du reste dû correspondant | **213 540 205 CFA** |

Période concernée : du **22/03/2026 au 21/09/2026**.

### Cas concrets

| Paiement | Client | Montant | Facture | Reste dû affiché |
|---|---|---|---|---|
| PAY00024 | GROUPE CENTAURES SASU | 9 800 000 | INV/2026/00025 | 9 800 000 |
| PAY00034 | NEEMBA CÔTE D'IVOIRE | 9 800 000 | INV/2026/00101 | 9 800 000 |
| PAY00079 | GABRIEL WEALTH MANAGEMENT | 9 800 000 | INV/2026/00141 | 9 800 000 |

### Ce qui distingue ces paiements des autres

| | Paiement normal | Paiement sans écriture |
|---|---|---|
| Nom | PBNK1/2026/00268 | PAY00102 |
| Compte d'attente | 521003 Outstanding Receipts | **aucun** |
| Pièce comptable | oui | **aucune** |
| Créé par | Acceuil (la caisse) | Direction (saisie manuelle) |

Les paiements produits par la caisse sont corrects. Ceux saisis manuellement
depuis l'écran de facture ne portent aucun compte d'attente et ne génèrent
aucune pièce.

### Principaux montants par client

| Client | Reste dû affiché |
|---|---|
| AFREXIM BANK | 20 268 390 |
| WAVE CÔTE D'IVOIRE SA | 13 321 915 |
| GABRIEL WEALTH MANAGEMENT | 9 800 000 |
| NSIA ASSURANCES CÔTE D'IVOIRE SA | 9 800 000 |
| VISA CEMEA HOLDINGS LIMITED | 9 800 000 |
| GROUPE CENTAURES SASU, Emmanuelle BONI | 9 800 000 |
| KEYSFINANCE PARTNERS CÔTE D'IVOIRE | 9 800 000 |
| UA VIE / SUNU Assurances Vie | 9 800 000 |
| NEEMBA CÔTE D'IVOIRE | 9 800 000 |
| AFRICA INTEGRATED ENERGY SOLUTION | 7 646 716 |
| CONCERTO WEST AFRICA | 7 321 610 |
| SOCIÉTÉ IVOIRIENNE DE BÉTON MANUFACTURÉ | 5 900 000 |

Ce constat est antérieur à toute intervention de cette session : le plus
ancien cas date du 22/03/2026.

## 6. Ce qui reste ouvert

- Cause exacte de l'absence de compte d'attente sur les paiements manuels.
- Correction à définir avec le comptable avant toute écriture de rattrapage.
- Clé API FNE de test à obtenir.
- Essai devis de réservation chargé en caisse, non encore réalisé.

---

# Suite — non-régression et essai devis → caisse

## 7. Non-régression des modules déjà en production

### Actions planifiées

Toutes actives, toutes avec une exécution récente : fermeture automatique de
caisse, contrôle des présences, journal d'audit POS (2 tâches), recalcul du
statut de facturation `theresidence_api`.

### Vues

91 vues des modules maison testées une par une : **85 se chargent sans
erreur**, 4 inactives ou sans modèle, **2 en échec** — toutes deux sur
`webhook.log`.

### Cause de l'échec `webhook.log`

Le droit d'accès existe bien (`webhook_manager.access_webhook_log`, groupe
Utilisateur, lecture/écriture/création/suppression) mais il est **archivé** :

```
id 2010 | webhook.log | Historique des Webhooks | Role / User | active: false
```

Conséquence : le menu d'historique des webhooks est inaccessible à tout le
monde, administrateur compris. La correction tient en une réactivation de cet
enregistrement — je n'ai pas eu l'autorisation de l'appliquer.

Les autres modèles sans droit d'accès sont tous des modèles abstraits
(`laresidence.mail.blocage`, `laresidence.pos.audit.acces`,
`laresidence.pos.audit.orm`, `webhook.mixin`) : c'est normal.

### Champs calculés maison

| Contrôle | Résultat |
|---|---|
| `x_tr_payment_detail` sur les commandes de caisse | fonctionne — « Espèces 470 000 », « Compte client 198 493 », « Cheque 49 623 » |
| `x_tr_billing_status` sur les devis | 268 sans objet, 65 à facturer, 46 facturé en retard, 39 facturé payé |
| Factures certifiées FNE | 87 certifiées, **0 sans référence DGI**, 0 avertissement |

### Volumétrie des modèles

`laresidence.pos.audit` 325 · `hr.attendance` 4 454 · `pos.session` 181 ·
`pos.order` 534 · `account.move` 1 102. Aucun modèle en erreur.

## 8. Essai devis de réservation chargé en caisse

Enregistrements de test créés pour l'occasion sur demo2 :
client **TEST DEVIS CAISSE 23-09**, devis **S01263** (10 × BIERE HEINEKEN
BTLE 33CL, 40 000 CFA), commande de caisse **Desk - 000040** dont la ligne
est rattachée à la ligne du devis.

### Étape par étape

| Étape | `invoice_status` | `qty_invoiced` | `amount_to_invoice` | Factures sur le devis |
|---|---|---|---|---|
| Devis confirmé | à facturer | 0 | 40 000 | 0 |
| Commande de caisse en **brouillon** | à facturer | 0 | **0** | 0 |
| Commande **payée**, non facturée | **facturé** | **10** | 0 | **0** |
| Commande **facturée** (INV/2026/00198) | facturé | 10 | 0 | **0** |

Deux enseignements :

1. Une commande de caisse encore en brouillon suffit à ramener le reste à
   facturer du devis à zéro. Le calcul standard qui ajoute les montants de
   caisse ne filtre pas les brouillons, alors que celui des quantités le fait.
2. Une fois la commande payée, **le devis se déclare facturé alors qu'aucune
   facture n'existe**. Puis la facture est créée, porte bien « S01263 » en
   origine — son nom affiché est même « INV/2026/00198 (S01263) » — mais
   **le devis affiche toujours 0 facture**.

### Le piège, vérifié par l'expérience

En rattachant la ligne de facture à la ligne de devis :

| Mesure | Avant | Après |
|---|---|---|
| Factures sur le devis | 0 | **1** ✅ |
| Quantité facturée | 10 | **20** ❌ |
| Montant facturé HT | 33 898 | **67 796** ❌ |
| Statut de facturation | facturé | **à facturer** ❌ |

Le rattachement donne bien le lien documentaire recherché, mais il fait
repasser le devis en « à facturer ». Quelqu'un rééditerait alors une seconde
facture : **c'est là, et seulement là, que le client serait débité deux fois.**

Le lien a été retiré aussitôt après la mesure ; le devis de test est revenu à
son état précédent.

### Ce que cela impose au futur module

Rattacher la facture ne suffit pas : il faut en même temps neutraliser
l'apport de `pos_sale` au calcul des quantités et montants facturés pour les
commandes de caisse **qui ont déjà une facture**. Sans cette neutralisation, le
lien documentaire crée le double comptage.
