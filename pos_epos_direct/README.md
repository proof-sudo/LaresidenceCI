# pos_epos_direct — Impression ePOS Directe pour Odoo 19 POS

Auteur : Djakaridja Traore · Projet LaResidence CI · Licence LGPL-3

---

## Présentation

Ce module améliore l'impression des reçus dans le Point de Vente Odoo 19.
Il ajoute **deux nouveaux types d'imprimantes ePOS directes** qui envoient des
commandes texte natives à l'imprimante, sans IoT Box et sans conversion image.

| Type | Label Odoo | Usage |
| --- | --- | --- |
| `epos_direct` | Epson ePOS Direct — Reçu client | Reçu complet après paiement |
| `epos_direct_kitchen` | Epson ePOS Direct — Ticket Cuisine / Bar | Ticket de préparation par station |

---

## Pourquoi ce module ?

### Problème avec l'approche native

```text
Clic "Imprimer"
    → html2canvas()      ← 300-1500 ms, CPU élevé
    → encode Base64      ← ~200-400 Ko
    → HTTP vers imprimante
    → Imprimante décode le bitmap et imprime
```

Sous forte charge (plusieurs caisses, heure de pointe), les impressions
s'accumulent et les terminaux bas de gamme "freezent".

### Solution apportée

```text
Clic "Imprimer"
    → RPC léger vers serveur Odoo  ← ~5 ms
    → Python génère XML ePOS texte  ← ~3-5 Ko
    → HTTP depuis serveur vers imprimante
    → Imprimante imprime avec polices natives
```

### Comparatif

| Critère | Natif epson_epos | pos_epos_direct |
| --- | --- | --- |
| Temps d'impression | 1,5 – 4 s | 0,2 – 0,5 s |
| Charge CPU client | Élevée (html2canvas) | Négligeable |
| Payload réseau | 200 – 400 Ko | 3 – 5 Ko |
| Qualité polices | Bitmap (flou possible) | Polices natives (net) |
| IoT Box requise | Non | Non |
| Coupe automatique | Oui | Oui |
| Notes de ligne | Non | Oui |
| Numéro de table | Non | Oui (si pos_restaurant) |

---

## Prérequis

### Imprimante

Toute imprimante Epson avec interface **Ethernet ou WiFi** et firmware **ePOS-Print**.

| Modèle | Compatible | Notes |
| --- | --- | --- |
| TM-T20III (Ethernet) | ✅ | Entrée de gamme, recommandé |
| TM-m30II / TM-m30III | ✅ | Compact, WiFi natif |
| TM-T88VII | ✅ | Haut de gamme, rapide |
| TM-T70II (Ethernet) | ✅ | Format horizontal |
| TM-T20 / TM-T20II USB | ❌ | Pas de réseau |
| TM-T20 RS-232 | ❌ | Interface série uniquement |

**Vérification ePOS :** ouvrir `http://[IP_IMPRIMANTE]` dans un navigateur.
Une interface web Epson doit s'afficher → activer `ePOS-Print` dans les paramètres.

### Réseau

- Le **serveur Odoo** (pas le navigateur client) doit accéder à l'IP de l'imprimante
- Port 80 (HTTP) ouvert entre serveur Odoo et imprimante

### Odoo

- Odoo 19 community ou enterprise
- Module `point_of_sale` installé
- `pos_restaurant` optionnel (pour numéro de table)

---

## Installation

```bash
# Copier dans le dossier addons personnalisés puis :
./odoo-bin -u pos_epos_direct -d MA_BASE
```

Ou via l'interface :
`Paramètres > Mode développeur > Applications > Mettre à jour > Installer pos_epos_direct`

---

## Configuration

### 1. Créer l'imprimante de caisse (reçu client)

`Point de Vente > Configuration > Imprimantes > Nouveau`

| Champ | Valeur |
| --- | --- |
| Nom | Caisse Principale |
| Type | **Epson ePOS Direct — Reçu client (Rapide)** |
| Adresse IP | `192.168.1.50` |

### 2. Créer l'imprimante cuisine

`Point de Vente > Configuration > Imprimantes > Nouveau`

| Champ | Valeur |
| --- | --- |
| Nom | Cuisine |
| Type | **Epson ePOS Direct — Ticket Cuisine / Bar** |
| Adresse IP | `192.168.1.51` |
| Catégories de produits | Plats chauds, Grillades... |

### 3. Créer l'imprimante bar (si besoin)

| Champ | Valeur |
| --- | --- |
| Nom | Bar |
| Type | **Epson ePOS Direct — Ticket Cuisine / Bar** |
| Adresse IP | `192.168.1.52` |
| Catégories de produits | Boissons, Cocktails... |

### 4. Assigner au POS

`POS > Configuration > Paramètres > [Votre POS] > Matériel`
→ Sélectionner les imprimantes créées.

---

## Format des reçus générés

### Reçu client (`epos_direct`)

```text
      ╔══════════════════════════╗
      ║      LA RESIDENCE CI     ║  ← double hauteur, gras
      ╚══════════════════════════╝
       Cocody, Abidjan, Côte d'Ivoire
            Tél: +225 07 00 00 00
──────────────────────────────────────────
Reçu:                    POS/2025/00042
Date:               26/03/2025 14:32
Table:                            5
Caissier:               Jean Kouassi
──────────────────────────────────────────
Poulet braisé                    4 500  ← gras
  1 × 4 500
Eau minérale 50cl                  500
  2 × 250
  Remise: 10%
  ↳ Sans glace
──────────────────────────────────────────
Sous-total HT:                   4 364
TVA (10%):                         636
══════════ TOTAL          5 000 XOF ════  ← double hauteur
──────────────────────────────────────────
Espèces                          6 000
Monnaie rendue:                  1 000
──────────────────────────────────────────
         Merci de votre visite !
              Bonne journée
[avance papier + coupe automatique]
```

### Ticket cuisine (`epos_direct_kitchen`)

```text
╔══════════════════════════════════════╗
║           ═══ CUISINE ═══            ║  ← double hauteur
╚══════════════════════════════════════╝

        TABLE: 5                          ← double hauteur
POS/2025/00042                    14:32
Jean Kouassi
──────────────────────────────────────────
[×1]
  Poulet braisé                          ← gras

[×2]
  Tilapia grillé
  !! SANS ARÊTES                         ← note en majuscules, gras

[×3]
  Riz sauté
──────────────────────────────────────────
NOTE:
  Allergie arachides pour table 5
──────────────────────────────────────────
[avance papier + coupe automatique]
```

---

## Cas d'utilisation

### Scénario 1 — Restaurant complet (caisse + cuisine + bar)

```text
3 imprimantes Epson TM-T20III sur réseau local :
  → IP 192.168.1.50  : Caisse       (type: epos_direct)
  → IP 192.168.1.51  : Cuisine      (type: epos_direct_kitchen, catégs: plats)
  → IP 192.168.1.52  : Bar          (type: epos_direct_kitchen, catégs: boissons)
```

**Flux complet :**

1. Serveur prend la commande sur la tablette POS
2. Clic "Envoyer en cuisine" → ticket cuisine imprimé en 0,3 s à 192.168.1.51
3. Boissons commandées → ticket bar imprimé en 0,3 s à 192.168.1.52
4. Après paiement → reçu client imprimé en 0,4 s à 192.168.1.50

**Sans ce module :** chaque impression prend 2-4 s (html2canvas) × 3 imprimantes
= 6-12 s de latence accumulée sur la tablette.

---

### Scénario 2 — Hôtel / Résidence (La Residence CI)

```text
  → Caisse réception    (type: epos_direct)
  → Cuisine restaurant  (type: epos_direct_kitchen, catégs: menu restaurant)
  → Bar piscine         (type: epos_direct_kitchen, catégs: boissons, snacks)
```

Les reçus hôteliers contiennent souvent 10-20+ lignes (nuitées, extras, services).
Avec l'approche image, un tel reçu génère une image de 600 Ko+.
Avec pos_epos_direct, le XML texte reste < 8 Ko quelle que soit la longueur.

---

### Scénario 3 — Forte affluence (marché, food court)

```text
4 caisses simultanées, pic à 3 impressions/minute/caisse = 12 impressions/min
```

Sans ce module : html2canvas s'exécute 12 fois par minute sur chaque terminal.
Sur tablettes d'entrée de gamme, la latence s'accumule, les caisses ralentissent.

Avec pos_epos_direct : le traitement est côté serveur, les terminaux ne font
qu'un appel RPC léger. Le serveur Odoo gère les 12 requêtes en parallèle sans effort.

---

### Scénario 4 — WiFi instable (terrasse, cuisine éloignée)

L'imprimante cuisine est en WiFi et le signal est parfois faible.
Avec l'image Base64 (300 Ko), un timeout réseau cause une impression échouée.
Avec pos_epos_direct, le serveur (câblé) contacte l'imprimante directement.
La connexion WiFi entre terminal et serveur ne transporte que 3 Ko de RPC.

---

## Dépannage

| Symptôme | Cause | Solution |
| --- | --- | --- |
| "Impossible de joindre l'imprimante" | IP incorrecte / imprimante éteinte | `ping [IP]` depuis le serveur Odoo |
| "Délai dépassé" | Réseau lent ou imprimante occupée | Vérifier le réseau, timeout = 8 s |
| "Commande non synchronisée" | Impression trop rapide avant sync | Attendre confirmation paiement |
| Option absente dans le formulaire | Module non installé | Vérifier installation + redémarrage Odoo |
| Ticket cuisine vide | Aucun article dans les catégories configurées | Vérifier `product_categories_ids` |
| Caractères mal encodés | Firmware imprimante ancien | S'assurer que UTF-8 est supporté |

---

## Architecture technique

```text
┌─────────────────────────────────────────────────────────┐
│                  NAVIGATEUR CLIENT                      │
│                                                         │
│  PosStore.createPrinter(config)                         │
│    ├── 'epos_direct'         → EposDirectPrinter        │
│    ├── 'epos_direct_kitchen' → EposDirectKitchenPrinter │
│    └── autres types          → super() (natif Odoo)     │
│                                                         │
│  EposDirectPrinter.printReceipt()                       │
│    └── orm.call('pos.printer', '_send_epos_receipt',    │
│                 [printer_id, order_id])                 │
│                                                         │
│  EposDirectKitchenPrinter.printReceipt()                │
│    └── orm.call('pos.printer',                          │
│                 '_send_epos_kitchen_ticket',            │
│                 [printer_id, order_id])                 │
└──────────────────────────┬──────────────────────────────┘
                           │ RPC (~3-5 Ko)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  SERVEUR ODOO (Python)                  │
│                                                         │
│  pos.printer._send_epos_receipt(printer_id, order_id)   │
│    └── _build_receipt_xml(order)                        │
│          └── Génère XML ePOS complet                    │
│              → HTTP POST → imprimante caisse            │
│                                                         │
│  pos.printer._send_epos_kitchen_ticket(printer_id, ...) │
│    └── _build_kitchen_xml(order)                        │
│          └── Filtre lignes par product_categories_ids   │
│              → Génère XML ePOS ticket préparation       │
│              → HTTP POST → imprimante cuisine/bar       │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP ePOS XML (~3-5 Ko)
                           ▼
            ┌──────────────────────────┐
            │   IMPRIMANTE EPSON ePOS  │
            │  (TM-T20III, TM-m30...)  │
            └──────────────────────────┘
```

---

## Structure des fichiers

```text
pos_epos_direct/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   └── pos_printer.py              ← Modèle étendu + générateurs XML
├── static/src/app/
│   ├── utils/printer/
│   │   ├── epos_direct_printer.js          ← Classe reçu client
│   │   └── epos_direct_kitchen_printer.js  ← Classe ticket cuisine/bar
│   └── overrides/
│       └── pos_store_patch.js      ← Patch createPrinter
└── views/
    └── pos_printer_form.xml        ← Affiche champ IP pour les 2 types
```
