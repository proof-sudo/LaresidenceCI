# Documentation Technique — The Residence CI
**Plateforme Odoo 19 — Business Club Management System**
*Auteur : Neurones Technologies — Dernière mise à jour : 2026-03-22*

---

## Table des matières

1. [Vue d'ensemble du projet](#1-vue-densemble-du-projet)
2. [Architecture générale](#2-architecture-générale)
3. [Module theresidence_api](#3-module-theresidence_api)
   - 3.1 [Authentification API](#31-authentification-api)
   - 3.2 [Modèles](#32-modèles)
   - 3.3 [Contrôleurs HTTP](#33-contrôleurs-http)
   - 3.4 [Composants POS (OWL/JS)](#34-composants-pos-owljs)
4. [Module theresidence_appointment_bridge](#4-module-theresidence_appointment_bridge)
5. [Module theresidence_kitchen_bridge](#5-module-theresidence_kitchen_bridge)
6. [Système de webhooks](#6-système-de-webhooks)
7. [Patterns de conception](#7-patterns-de-conception)
8. [Guide de débogage](#8-guide-de-débogage)
9. [Guide d'ajout de fonctionnalités](#9-guide-dajout-de-fonctionnalités)
10. [Référence des endpoints API](#10-référence-des-endpoints-api)
11. [Schéma des statuts et workflows](#11-schéma-des-statuts-et-workflows)
12. [Modules à mettre à jour](#12-modules-à-mettre-à-jour)

---

## 1. Vue d'ensemble du projet

The Residence CI est une installation Odoo 19 sur mesure pour la gestion d'un business club à Abidjan. Elle expose une **API REST complète** consommée par une **application mobile**, et étend le **Point de Vente (POS)** d'Odoo pour gérer :

| Domaine | Description |
|---|---|
| **Membres** | Inscription, profil, abonnements, QR codes |
| **Espaces** | Réservation de salles/tables avec contrôle de disponibilité |
| **Commandes restaurant** | Commandes mobiles synchronisées avec la caisse POS |
| **Abonnements** | Plans d'adhésion avec cycle de vie complet |
| **Webhooks** | Notifications temps réel vers systèmes externes |
| **POS natif** | Intégration avec `pos_appointment` pour le planning |

### Structure des modules custom

```
LaresidenceCI/
├── theresidence_api_true/
│   └── theresidence_api/          ← Module principal (API + modèles)
├── theresidence_appointment_bridge/ ← Pont réservations ↔ pos_appointment
├── theresidence_kitchen_bridge/     ← Pont commandes mobiles ↔ cuisine POS
└── residence_webhook/               ← Webhooks legacy (obsolète)
```

### Dépendances entre modules

```
theresidence_api
    ↑
theresidence_appointment_bridge (dépend de: theresidence_api, appointment, pos_appointment)
    ↑
theresidence_kitchen_bridge (dépend de: theresidence_api, pos_enterprise)
```

---

## 2. Architecture générale

### Flux de données — Application mobile

```
App Mobile
    │
    ├─[X-API-Key]──► /v1/external/...  (controllers/)
    │                      │
    │               @api_auth decorator
    │               theresidence.api.key
    │                      │
    │              Modèles Odoo (ORM)
    │                      │
    │              theresidence.webhook.trigger_event()
    │                      │
    └──────────────[webhook POST]──► Système externe
```

### Flux de données — POS

```
POS Frontend (OWL/JS)
    │
    ├─[ORM call]──► sale.order.get_pos_reservations()
    ├─[ORM call]──► sale.order.pos_reserve_reservation()
    ├─[ORM call]──► sale.order.pos_load_reservation_to_pos()
    │
    ├─[bus.bus]──► pos_reservation_notify.js (polling 10s)
    │
    └─[sync_from_ui]──► pos.order (caisse normale)
```

### Convention de nommage des champs custom

Tous les champs custom The Residence utilisent le préfixe `x_tr_` :
- `x_tr_uuid` — identifiant unique pour l'API externe
- `x_tr_is_*` — flags booléens (is_member, is_space, is_reservation…)
- `x_tr_*_status` — champs de statut (reservation_status, order_status…)
- `x_tr_*_id` — relations Many2one custom

---

## 3. Module theresidence_api

**Chemin :** `theresidence_api_true/theresidence_api/`
**Dépendances Odoo :** `base`, `sale`, `sale_subscription`, `sale_renting`, `point_of_sale`

### 3.1 Authentification API

**Fichier :** `models/api_key.py`
**Modèle :** `theresidence.api.key`

#### Champs

| Champ | Type | Description |
|---|---|---|
| `name` | Char | Nom descriptif de la clé |
| `key` | Char (readonly) | Valeur générée : `tr_{urlsafe_token_32_chars}` |
| `is_active` | Boolean | Active/inactive |
| `can_read_members` | Boolean | Permission lecture membres |
| `can_write_members` | Boolean | Permission écriture membres |
| `can_read_spaces` | Boolean | Permission lecture espaces |
| `can_read_menu` | Boolean | Permission lecture menu |
| `can_read_reservations` | Boolean | Permission lecture réservations |
| `can_write_reservations` | Boolean | Permission écriture réservations |
| `can_read_orders` | Boolean | Permission lecture commandes |
| `can_write_orders` | Boolean | Permission écriture commandes |
| `can_read_subscriptions` | Boolean | Permission lecture abonnements |
| `can_write_subscriptions` | Boolean | Permission écriture abonnements |
| `can_manage_webhooks` | Boolean | Permission gestion webhooks |

#### Méthodes importantes

```python
# Génération automatique à la création
def _generate_api_key(self) → str

# Regénère une nouvelle clé (bouton UI)
def regenerate_key(self) → None

# Vérifie une permission nommée
def has_permission(self, permission: str) → bool

# Valide une clé API — retourne le record ou lève une erreur
@api.model
def validate_key(self, key: str) → theresidence.api.key
```

#### Decorator d'authentification

Défini dans `controllers/main.py` :

```python
@api_auth('read_reservations')  # permission optionnelle
def ma_route(self, **kwargs):
    api_key = request.api_key  # disponible après auth
```

Le decorator :
1. Lit l'en-tête `X-API-Key`
2. Appelle `validate_key()` → 401 si invalide
3. Vérifie la permission → 403 si insuffisante
4. Stocke le record dans `request.api_key`

---

### 3.2 Modèles

#### 3.2.1 Membres — `res.partner` (héritage)

**Fichier :** `models/res_partner.py`

**Nouveaux champs :**

| Champ | Type | Description |
|---|---|---|
| `x_tr_uuid` | Char (readonly, indexed) | UUID unique pour l'API |
| `x_tr_qr_token` | Char (readonly) | Token QR pour check-in : `mbr_{hex12}` |
| `x_tr_is_member` | Boolean | Marque le partenaire comme membre |
| `x_tr_member_status` | Selection | PENDING / ACTIVE / SUSPENDED / INACTIVE |
| `x_tr_membership_type_id` | Many2one → `theresidence.membership.type` | Type d'adhésion |
| `x_tr_joined_at` | Date | Date de début d'adhésion |

**Hooks :**
- `create()` : génère UUID + QR token pour les membres
- `write()` : génère UUID/QR si absents, journalise les changements de statut

**Méthodes :**

```python
# Conversion en dict API (camelCase)
def to_member_api_dict(self) → dict

# Création/mise à jour depuis l'API mobile
@api.model
def create_member_from_api(self, data: dict) → res.partner
```

**Format dict API :**
```json
{
  "id": "uuid",
  "firstName": "...",
  "lastName": "...",
  "email": "...",
  "phone": "...",
  "companyName": "...",
  "jobTitle": "...",
  "membershipTypeId": "uuid",
  "membershipTypeCode": "PREMIUM",
  "membershipTypeName": "Premium",
  "status": "ACTIVE",
  "joinedAt": "2026-01-15",
  "qrToken": "mbr_abc123def456"
}
```

---

#### 3.2.2 Espaces — `product.template` (héritage)

**Fichier :** `models/product.py`

**Nouveaux champs :**

| Champ | Type | Description |
|---|---|---|
| `x_tr_is_space` | Boolean | Marque le produit comme espace |
| `x_tr_space_uuid` | Char (readonly, indexed) | UUID espace |
| `x_tr_space_capacity` | Integer | Capacité maximale |
| `x_tr_space_type_id` | Many2one → `theresidence.space.type` | Type d'espace |
| `x_tr_space_description` | Text | Description |
| `x_tr_is_occupied` | Boolean | Occupation courante (legacy) |
| `x_tr_space_status` | Selection | `libre` / `réservé` |
| `x_tr_is_subscription_plan` | Boolean | Plan d'abonnement |
| `x_tr_membership_type_id` | Many2one → `theresidence.membership.type` | Type lié |
| `x_tr_duration_months` | Integer | Durée en mois |

**Logique de statut espace :**
- `action_reserve_reservation()` dans `sale.order` → met `x_tr_space_status = 'réservé'`
- `action_release_reservation()` / `action_cancel_reservation()` → met `x_tr_space_status = 'libre'` **uniquement si aucune autre réservation active** sur cet espace

**Méthodes :**

```python
# Vérification de disponibilité pour un créneau
def check_availability(self, start_time, end_time) → dict
# Retourne: { "isAvailable": bool, "conflictingReservations": int, ... }

# Libération manuelle (admin)
def action_free_space(self) → None

# Sérialisation API
def to_space_api_dict(self) → dict
def to_subscription_plan_api_dict(self) → dict
```

---

#### 3.2.3 Réservations — `sale.order` (héritage)

**Fichier :** `models/sale_order.py`

**Champs réservation :**

| Champ | Type | Description |
|---|---|---|
| `x_tr_uuid` | Char | UUID unique |
| `x_tr_is_reservation` | Boolean | Marque la commande comme réservation |
| `x_tr_reservation_status` | Selection | PENDING / RESERVED / ARRIVED / CANCELLED / COMPLETED |
| `x_tr_space_id` | Many2one → `product.template` | Espace réservé |
| `x_tr_start_time` | Datetime | Début du créneau |
| `x_tr_end_time` | Datetime | Fin du créneau |
| `x_tr_guest_count` | Integer | Nombre d'invités |
| `x_tr_notes` | Text | Notes client |
| `x_tr_rejection_reason` | Text | Raison d'un refus |
| `x_tr_qr_token` | Char | Token QR de la réservation |
| `x_tr_invitee_ids` | One2many → `theresidence.reservation.invitee` | Invités |
| `x_tr_option_ids` | One2many → `theresidence.reservation.option` | Options supplémentaires |

**Contrainte d'anti-doublon :**

```python
@api.constrains('x_tr_reservation_status', 'x_tr_space_id', 'x_tr_start_time', 'x_tr_end_time')
def _check_no_double_booking(self):
    # Bloque toute réservation PENDING/RESERVED/ARRIVED
    # qui chevauche un créneau existant sur le même espace
    # Logique : start < other_end AND end > other_start
```

**Workflow réservations :**

```
PENDING ──[Réserver]──► RESERVED ──[Arrivée]──► ARRIVED ──[Libérer]──► COMPLETED
   │                       │                      │
   └──[Annuler]──► CANCELLED ◄──[Annuler]─────────┘
```

**Méthodes workflow :**

```python
def action_reserve_reservation(self)    # PENDING → RESERVED + espace occupé
def action_arrive_reservation(self)     # RESERVED → ARRIVED
def action_release_reservation(self)    # RESERVED/ARRIVED → COMPLETED + espace libéré
def action_cancel_reservation(self)     # Any → CANCELLED + espace libéré

# Appelées depuis le POS (par UUID)
def pos_reserve_reservation(self, uuid: str)
def pos_arrive_reservation(self, uuid: str)
def pos_release_reservation(self, uuid: str)
def pos_cancel_reservation(self, uuid: str)

# Création depuis l'API
@api.model
def create_reservation_from_api(self, data: dict) → sale.order

# Lecture pour le POS
@api.model
def get_pos_reservations(self, date_filter: str = 'today') → list[dict]
```

**Helpers pour le statut espace :**

```python
def _space_has_other_active_reservations(self, space) → bool
def _mark_space_reserved(self, space) → None
def _mark_space_free_if_no_active(self, space) → None
```

---

#### 3.2.4 Commandes mobiles — `pos.order` (héritage)

**Fichier :** `models/pos_order.py`

**Deux types de commandes POS :**

| Type | `x_tr_is_mobile_order` | `x_tr_order_status` |
|---|---|---|
| Commande mobile (API) | `True` | Suit le workflow mobile |
| Commande POS normale | `False` | `NULL` (pas concernée) |

> **Important :** Le champ `x_tr_order_status` n'a PAS de contrainte NOT NULL. Les commandes POS normales (créées via `sync_from_ui`) ont ce champ à NULL, ce qui est correct.

**Champs commandes mobiles :**

| Champ | Type | Description |
|---|---|---|
| `x_tr_uuid` | Char | UUID commande |
| `x_tr_is_mobile_order` | Boolean | Commande depuis l'app |
| `x_tr_order_status` | Selection | PENDING / CONFIRMED / READY / SENT_TO_POS / CANCELLED / PAID / COMPLETED |
| `x_tr_order_mode` | Selection | PICKUP / DELIVERY / DINE_IN |
| `x_tr_delivery_address` | Text | Adresse livraison |
| `x_tr_qr_token` | Char | Token QR commande |
| `x_tr_member_id` | Many2one → `res.partner` | Membre commandant |

**Synchronisation automatique état Odoo → statut TR :**

```python
_STATE_TO_ORDER_STATUS = {
    'paid':   'PAID',
    'done':   'COMPLETED',
    'cancel': 'CANCELLED',
}
# Déclenché dans write() sur mobile orders uniquement
```

**Ligne de commande — `pos.order.line` (héritage) :**

```python
# Champ calculé pour le nom traduit dans la vue POS
translated_product_name = fields.Char(compute='_compute_translated_product_name', store=False)
```

**Méthodes :**

```python
def to_order_api_dict(self) → dict
def action_confirm_order(self)    # PENDING → CONFIRMED
def action_ready_order(self)      # CONFIRMED → READY
def action_complete_order(self)   # READY → COMPLETED
def action_cancel_order(self, reason=None)

@api.model
def create_order_from_api(self, data: dict) → pos.order

@api.model
def get_new_pending_orders(self, since_iso: str) → list[dict]
```

---

#### 3.2.5 Données de référence

**Fichier :** `models/membership_type.py`

| Modèle | Description | Champs principaux |
|---|---|---|
| `theresidence.membership.type` | Types d'adhésion | code, name, sort_order, x_uuid |
| `theresidence.space.type` | Types d'espace | code, name, sort_order |
| `theresidence.reservation.option.def` | Options de réservation | code, name, price, scope |
| `theresidence.menu.kind` | Catégories de menu niveau 1 | code, name, sort_order |

Tous ces modèles ont un UUID auto-généré et une méthode `to_api_dict()`.

---

#### 3.2.6 Webhooks — `theresidence.webhook`

**Fichier :** `models/webhook.py`

**Modèles :**
- `theresidence.webhook` : Configuration d'un endpoint distant
- `theresidence.webhook.event.type` : Types d'événements (RESERVATION_CREATED, etc.)
- `theresidence.webhook.event` : Journal des envois

**Champs webhook :**

| Champ | Type | Description |
|---|---|---|
| `name` | Char | Nom |
| `url` | Char | URL cible |
| `secret` | Char | Secret HMAC-SHA256 |
| `is_active` | Boolean | Activé |
| `event_type_ids` | Many2many | Types d'événements souscrits |
| `event_ids` | One2many | Historique des envois |

**Payload standard :**

```json
{
  "id": "uuid-event",
  "eventType": "RESERVATION_CREATED",
  "entityType": "reservation",
  "entityId": "uuid-entity",
  "data": { ...dict_complet... },
  "previousStatus": null,
  "newStatus": "PENDING",
  "timestamp": "2026-03-22T10:30:45.123456Z"
}
```

**En-tête de signature :**
```
X-Webhook-Signature: sha256={hmac_hex_digest}
```

---

### 3.3 Contrôleurs HTTP

**Base URL :** `/v1/external/`
**Authentification :** En-tête `X-API-Key: tr_...`

#### Fonctions utilitaires (main.py)

```python
json_response(data, status=200) → Response
error_response(message, error_code=None, status=400) → Response
success_response(data, status=200) → Response      # avec headers anti-cache
paginated_response(items, total, page, size) → Response
```

**Format d'erreur standard :**
```json
{ "error": "Message d'erreur lisible", "code": "ERROR_CODE" }
```

**Format paginé standard :**
```json
{
  "data": [...],
  "pagination": { "page": 1, "size": 20, "total": 150, "pages": 8 }
}
```

#### Tableau complet des routes

**Santé / Auth**

| Route | Méthode | Permission | Description |
|---|---|---|---|
| `/v1/external/health` | GET | public | Vérification API |
| `/v1/external/info` | GET | any | Infos clé API |

**Membres**

| Route | Méthode | Permission | Description |
|---|---|---|---|
| `/v1/external/reference/members` | GET | read_members | Liste paginée |
| `/v1/external/reference/members` | POST | write_members | Création |
| `/v1/external/reference/members/<id>` | GET | read_members | Fiche membre |
| `/v1/external/reference/members/<id>` | PUT | write_members | Mise à jour |

**Espaces**

| Route | Méthode | Permission | Description |
|---|---|---|---|
| `/v1/external/reference/spaces` | GET | read_spaces | Liste |
| `/v1/external/reference/spaces/<id>` | GET | read_spaces | Détail |
| `/v1/external/reference/spaces/<id>/availability` | GET | read_spaces | Disponibilité (?startTime=&endTime=) |

**Réservations**

| Route | Méthode | Permission | Description |
|---|---|---|---|
| `/v1/external/reservations` | GET | read_reservations | Liste paginée |
| `/v1/external/reservations` | POST | write_reservations | Création (vérifie disponibilité) |
| `/v1/external/reservations/<id>` | GET | read_reservations | Détail |
| `/v1/external/reservations/<id>` | PUT | write_reservations | Modification (état PENDING seulement) |
| `/v1/external/reservations/<id>` | DELETE | write_reservations | Annulation |
| `/v1/external/reservations/<id>/approve` | POST | write_reservations | PENDING → RESERVED |
| `/v1/external/reservations/<id>/reject` | POST | write_reservations | PENDING → CANCELLED |
| `/v1/external/reservations/<id>/check-in` | POST | write_reservations | RESERVED → ARRIVED |
| `/v1/external/reservations/<id>/cancel` | POST | write_reservations | → CANCELLED |
| `/v1/external/reservations/<id>/options` | PATCH | write_reservations | Ajout option |
| `/v1/external/reservations/<id>/options/<opt_id>` | DELETE | write_reservations | Suppression option |
| `/v1/external/reservations/<id>/invitees` | PATCH | write_reservations | Ajout invité |
| `/v1/external/reservations/<id>/invitees/<inv_id>` | DELETE | write_reservations | Suppression invité |
| `/v1/external/members/<id>/reservations` | GET | read_reservations | Réservations d'un membre |

**Commandes**

| Route | Méthode | Permission | Description |
|---|---|---|---|
| `/v1/external/orders` | GET | read_orders | Liste |
| `/v1/external/orders` | POST | write_orders | Création |
| `/v1/external/orders/<id>` | GET | read_orders | Détail |
| `/v1/external/orders/<id>` | PUT | write_orders | Modification |
| `/v1/external/orders/<id>/confirm` | POST | write_orders | PENDING → CONFIRMED |
| `/v1/external/orders/<id>/ready` | POST | write_orders | CONFIRMED → READY |
| `/v1/external/orders/<id>/complete` | POST | write_orders | READY → COMPLETED |
| `/v1/external/orders/<id>/cancel` | POST | write_orders | → CANCELLED |
| `/v1/external/members/<id>/orders` | GET | read_orders | Commandes d'un membre |

**Abonnements**

| Route | Méthode | Permission | Description |
|---|---|---|---|
| `/v1/external/subscriptions` | GET | read_subscriptions | Liste |
| `/v1/external/subscriptions` | POST | write_subscriptions | Création |
| `/v1/external/subscriptions/<id>` | GET | read_subscriptions | Détail |
| `/v1/external/subscriptions/<id>/pause` | POST | write_subscriptions | ACTIVE → PAUSED |
| `/v1/external/subscriptions/<id>/resume` | POST | write_subscriptions | PAUSED → ACTIVE |
| `/v1/external/subscriptions/<id>/cancel` | POST | write_subscriptions | → CANCELLED |
| `/v1/external/members/<id>/subscriptions` | GET | read_subscriptions | Abonnements d'un membre |

**Menu (lecture publique)**

| Route | Méthode | Description |
|---|---|---|
| `/v1/external/reference/menu-kinds` | GET | Catégories niveau 1 |
| `/v1/external/reference/menu-kinds/<id>/categories` | GET | Sous-catégories |
| `/v1/external/reference/menu-categories` | GET | Toutes les catégories |
| `/v1/external/reference/menu-items` | GET | Tous les produits POS |
| `/v1/external/reference/menu-items/<id>` | GET | Détail produit |

**Webhooks**

| Route | Méthode | Permission | Description |
|---|---|---|---|
| `/v1/external/webhooks` | GET/POST | manage_webhooks | Liste/création |
| `/v1/external/webhooks/<id>` | GET/PUT/DELETE | manage_webhooks | CRUD |
| `/v1/external/webhooks/<id>/events` | GET | manage_webhooks | Historique paginé |
| `/v1/external/webhooks/<id>/test` | POST | manage_webhooks | Test |

---

### 3.4 Composants POS (OWL/JS)

#### ReservationPanel (`static/src/js/ReservationScreen.js`)

Panneau latéral dans le POS pour gérer les réservations.

**État (useState) :**
```javascript
{
  reservations: [],      // Liste courante
  loading: false,        // Indicateur de chargement
  filter: 'ALL',         // Filtre statut
  dateFilter: 'today',   // Filtre date
  actionLoading: null,   // UUID de l'action en cours
}
```

**Appels ORM :**
```javascript
this.orm.call('sale.order', 'get_pos_reservations', [dateFilter])
this.orm.call('sale.order', 'pos_reserve_reservation', [uuid])
this.orm.call('sale.order', 'pos_arrive_reservation', [uuid])
this.orm.call('sale.order', 'pos_release_reservation', [uuid])
this.orm.call('sale.order', 'pos_cancel_reservation', [uuid])
```

#### ReservationButton (`static/src/js/ReservationButton.js`)

Patch sur le composant `Chrome` du POS pour ajouter le bouton d'accès au panneau.

---

## 4. Module theresidence_appointment_bridge

**Chemin :** `theresidence_appointment_bridge/`
**Dépendances :** `theresidence_api`, `appointment`, `pos_appointment`

Ce module fait le pont entre les réservations TR (`sale.order`) et le module natif `pos_appointment` d'Odoo (`calendar.event`). Chaque réservation TR génère automatiquement un `calendar.event` miroir visible dans le planning POS.

### 4.1 Modèle `sale.order` (héritage)

**Fichier :** `models/sale_order.py`

**Champs ajoutés :**

| Champ | Type | Description |
|---|---|---|
| `x_tr_calendar_event_id` | Many2one → `calendar.event` | Événement miroir créé |
| `x_tr_pos_order_id` | Many2one → `pos.order` | Commande POS chargée depuis cette réservation |

**Logique de création :**
```python
# À chaque create() d'une réservation TR :
# 1. Crée le calendar.event miroir (_sync_create_calendar_event)
# 2. Notifie le POS via bus.bus (_notify_pos_new_reservation)
# → Chaque étape est dans un savepoint isolé (erreur non bloquante)
```

**Mapping statut → calendar.event :**

| x_tr_reservation_status | show_as (calendar) | active |
|---|---|---|
| PENDING | free | True |
| RESERVED | busy | True |
| ARRIVED | busy | True |
| COMPLETED | free | False |
| CANCELLED | free | False |

**Logique de chargement en POS (`_do_load_to_pos`) :**

```python
def _do_load_to_pos(self):
    # 1. Auto-confirme le sale.order si brouillon
    # 2. Cherche une session POS ouverte
    # 3. Vérifie si déjà chargé (x_tr_pos_order_id)
    #    → Identique : bloque avec message
    #    → Modifié : supprime les lignes et recrée
    # 4. Crée le pos.order avec toutes les lignes
    # 5. Calcule les taxes correctement
    # 6. Relie le pos.order via x_tr_pos_order_id
```

**Anti-doublon de chargement :**

```python
def _lines_match_pos_order(self, pos_order) → bool:
    # Compare les ensembles de (product_id, qty, price_unit)
    # entre sale.order.line et pos.order.line
```

### 4.2 Modèle `calendar.event` (héritage)

**Fichier :** `models/calendar_event.py`

**Champ calculé :**
```python
x_tr_reservation_status = fields.Char(compute='...')
# Lit le statut depuis la sale.order liée
```

**Sync inverse (calendar → sale.order) :**
Les changements de `appointment_status` dans la vue POS déclenchent des mises à jour sur le `sale.order` correspondant :

| appointment_status | action TR |
|---|---|
| booked | action_reserve_reservation() |
| attended | action_arrive_reservation() |
| no_show / cancelled | action_cancel_reservation() |

**Boutons dans la vue POS :**
- `action_tr_reserve()` — Réserver
- `action_tr_arrive()` — Marquer arrivée
- `action_tr_release()` — Libérer l'espace
- `action_tr_cancel()` — Annuler
- `action_tr_load_to_pos()` — Charger la commande dans le POS (visible si ARRIVED)

### 4.3 Modèle `product.template` (héritage)

**Fichier :** `models/product_template.py`

**Champ ajouté :**
```python
x_tr_appointment_type_id = Many2one('appointment.type')
```

**Méthode `_ensure_appointment_type()` :**
- Cherche ou crée un `appointment.type` lié à l'espace
- Priorité : catégorie 'table' (restaurant POS)
- Fallback : "Réservation de table"
- Ajoute l'admin comme staff et lie à tous les POS actifs

### 4.4 JavaScript — `pos_reservation_notify.js`

**Polling toutes les 10 secondes :**
```javascript
// Appels ORM
orm.call('sale.order', 'get_new_pending_reservations', [since_iso])
orm.call('pos.order', 'get_new_pending_orders', [since_iso])
```

**Notification audio :**
1. Essaie de jouer `/theresidence_appointment_bridge/static/src/sounds/new_reservation.wav`
2. Fallback : génère un bip Web Audio (sine wave 880→1100 Hz, 450ms)

### 4.5 JavaScript — `appointment_list_patch.js`

Enrichit les cartes de la liste de réservations POS (vue kanban/liste) :

**Problème résolu :** Le texte `"Espace — Client"` généré par `_build_event_name()` est tronqué nativement par Odoo.

**Solution :**
1. Charge les `calendar.event` via RPC (une fois au premier rendu)
2. `MutationObserver` détecte les nouvelles cartes dans le DOM
3. Restructure chaque carte avec des libellés stylisés :
   - **ESPACE** : nom complet de l'espace
   - **CLIENT** : nom du client
   - **PRÉVU** : date · heure début – heure fin
4. Supprime la troncature CSS (`text-overflow: ellipsis`)

### 4.6 Modèle `pos.order` (héritage dans le bridge)

**Fichier :** `models/pos_order.py`

**Objectif :** Annuler le `stock.picking` de la `sale.order` quand la commande POS est payée.

**Pourquoi :** Sans cela, il y aurait une **double sortie de stock** :
1. Le POS valide ses propres `stock.move` à la clôture
2. Le bon de livraison de la `sale.order` sortirait les mêmes articles une deuxième fois

**Logique :**
```python
def write(self, vals):
    # Détecte state = 'paid' ou 'done'
    # → Cherche la sale.order liée via x_tr_pos_order_id
    # → Annule ses stock.picking encore ouverts
    # → Journalise l'opération
```

---

## 5. Module theresidence_kitchen_bridge

**Chemin :** `theresidence_kitchen_bridge/`
**Dépendances :** `theresidence_api`, `pos_enterprise`

### Objectif

Synchroniser le statut des commandes mobiles avec la préparation en cuisine (module `pos_prep_order` de POS Enterprise).

### Modèle `pos.order` (héritage)

**Fichier :** `models/pos_order.py`

```python
# Override de sync_from_ui :
# Avant la synchronisation POS, passe les commandes mobiles PENDING → CONFIRMED
# et déclenche le webhook ORDER_STATUS_CHANGED
def sync_from_ui(self, orders):
```

### Modèle `pos.prep.order` (héritage)

**Fichier :** `models/pos_prep_order.py`

```python
# Quand une commande entre en cuisine :
# mobile order PENDING → CONFIRMED + webhook
def process_order(self, order_id, options):
```

---

## 6. Système de webhooks

### Types d'événements disponibles

| Code | Déclencheur |
|---|---|
| `MEMBER_CREATED` | Nouveau membre |
| `MEMBER_UPDATED` | Modification membre |
| `SPACE_CREATED` | Nouvel espace |
| `SPACE_UPDATED` | Modification espace |
| `RESERVATION_CREATED` | Nouvelle réservation |
| `RESERVATION_STATUS_CHANGED` | Changement de statut réservation |
| `RESERVATION_CANCELLED` | Annulation réservation |
| `ORDER_CREATED` | Nouvelle commande mobile |
| `ORDER_STATUS_CHANGED` | Changement statut commande |
| `ORDER_CANCELLED` | Annulation commande |
| `SUBSCRIPTION_CREATED` | Nouvel abonnement |
| `SUBSCRIPTION_STATUS_CHANGED` | Changement statut abonnement |
| `SUBSCRIPTION_CANCELLED` | Annulation abonnement |

### Comment appeler depuis un modèle

```python
self.env['theresidence.webhook'].trigger_event(
    'RESERVATION_STATUS_CHANGED',  # code événement
    'reservation',                  # entity_type
    order.x_tr_uuid,               # entity_id
    order.to_reservation_api_dict(), # data
    old_status,                     # previousStatus
    'RESERVED',                     # newStatus
)
```

### Gestion des erreurs webhook

- Timeout : 30 secondes
- L'événement est journalisé même en cas d'échec (status = FAILED)
- L'échec d'un webhook n'annule pas la transaction Odoo
- Les erreurs sont visibles dans le menu `The Residence API > Webhooks > Événements`

---

## 7. Patterns de conception

### Pattern 1 — UUID externe

Toutes les entités ont un UUID pour l'API externe, indépendant de l'ID Odoo :

```python
x_tr_uuid = fields.Char(copy=False, readonly=True, index=True)

def create(self, vals_list):
    for vals in vals_list:
        if not vals.get('x_tr_uuid'):
            vals['x_tr_uuid'] = str(uuid.uuid4())
    return super().create(vals_list)
```

L'API cherche toujours par UUID :
```python
record = self.env['sale.order'].search([('x_tr_uuid', '=', entity_id)], limit=1)
```

### Pattern 2 — Anti-boucle de synchronisation

Quand deux modèles se synchronisent mutuellement, on utilise un flag de contexte :

```python
# Dans sale_order.write() :
if self.env.context.get('tr_skip_calendar_sync'):
    return res

# Dans calendar_event.write() :
event.with_context(tr_skip_calendar_sync=True).write(update_vals)
```

Flags utilisés :
- `tr_skip_calendar_sync` — empêche la boucle sale.order ↔ calendar.event
- `tr_skip_order_sync` — empêche la boucle pos.order state ↔ x_tr_order_status
- `tr_skip_webhook` — désactive les webhooks pendant des opérations internes

### Pattern 3 — Savepoints isolés

Les opérations secondaires (webhooks, notifications) ne doivent pas faire échouer l'opération principale :

```python
try:
    with rec.env.cr.savepoint():
        rec.sudo()._sync_create_calendar_event()
except Exception:
    _logger.exception("[TR BRIDGE] Échec création calendar.event pour %s", rec.x_tr_uuid)
```

### Pattern 4 — Dict API camelCase

Chaque modèle exporte ses données via `to_*_api_dict()` retournant du camelCase :

```python
def to_reservation_api_dict(self):
    self.ensure_one()
    return {
        'id': self.x_tr_uuid,
        'spaceId': self.x_tr_space_id.x_tr_space_uuid,
        'spaceName': self.x_tr_space_id.name,
        'startTime': self.x_tr_start_time.isoformat(),
        # ...
    }
```

### Pattern 5 — Sudo pour les opérations API

Les contrôleurs utilisent `sudo()` pour bypasser les droits de l'utilisateur API public :

```python
record = self.env['sale.order'].sudo().search([...])
result = record.sudo().action_reserve_reservation()
```

---

## 8. Guide de débogage

### Erreurs courantes et solutions

#### `null value in column "x_tr_order_status" violates not-null constraint`

**Cause :** Une commande POS normale (créée via `sync_from_ui`) envoie `x_tr_order_status: null`.

**Solution :** Déjà corrigée. Le champ n'a plus `required=True`. La méthode `create()` ignore `x_tr_order_status` pour les commandes non mobiles.

**Vérification :**
```python
# Dans pos_order.py, create() :
if vals.get('x_tr_is_mobile_order'):
    vals['x_tr_order_status'] = 'PENDING'
else:
    vals.pop('x_tr_order_status', None)  # ← crucial
```

---

#### `AttributeError: 'sale.order.line' object has no attribute 'product_uom'`

**Cause :** Odoo 19 utilise `product_uom_id` (pas `product_uom`) sur `sale.order.line`.

**Solution :** Toujours utiliser `line.product_uom_id` dans le bridge.

---

#### `KeyError: 'translated_product_name'`

**Cause :** La vue POS backend référençait ce champ mais il n'existait pas en Odoo 19.

**Solution :** Ajouté comme champ calculé sur `pos.order.line` dans `pos_order.py`.

---

#### Le bouton "Charger la commande" n'apparaît pas dans le POS

**Vérification :**
1. Le statut de la réservation est-il bien `ARRIVED` ?
2. La vue héritée est-elle la bonne ? → `pos_appointment.calendar_event_view_form_gantt_booking`
3. Le module est-il à jour ? → `-u theresidence_appointment_bridge`
4. Vider le cache navigateur ou ouvrir en mode privé

---

#### Les enrichissements de cartes POS ne s'affichent pas

**Cause :** Les assets JS ne sont pas régénérés.

**Solutions :**
1. Ajouter `?debug=assets` dans l'URL
2. Relancer le serveur avec `-u theresidence_appointment_bridge`

---

#### `ValidationError: L'espace 'X' n'est pas disponible pour ce créneau`

**Cause normale :** Double réservation bloquée par la contrainte `_check_no_double_booking`.

**Debugging :**
```python
# Vérifier les réservations actives sur l'espace :
self.env['sale.order'].search([
    ('x_tr_space_id', '=', space_id),
    ('x_tr_reservation_status', 'in', ['PENDING', 'RESERVED', 'ARRIVED']),
    ('x_tr_start_time', '<', end_time),
    ('x_tr_end_time', '>', start_time),
])
```

---

#### Webhook non déclenché

**Vérification par étapes :**
1. Le type d'événement existe-t-il ? → Menu `The Residence API > Types d'événements`
2. Le webhook est-il actif et souscrit à ce type ? → Menu `The Residence API > Webhooks`
3. L'historique montre-t-il SUCCESS ou FAILED ? → Onglet "Événements" du webhook
4. L'URL est-elle accessible depuis le serveur ?

---

### Logs à surveiller

```bash
# Erreurs bridge
grep "TR BRIDGE" /var/log/odoo/odoo.log

# Erreurs webhook
grep "theresidence.webhook" /var/log/odoo/odoo.log

# Erreurs API
grep "v1/external" /var/log/odoo/odoo.log
```

**Niveaux de log utilisés :**
- `_logger.info(...)` — opérations normales (création calendar.event, notifications)
- `_logger.warning(...)` — erreurs non bloquantes (webhook échoué)
- `_logger.exception(...)` — erreurs inattendues avec stack trace

---

### Commandes de debug utiles (shell Odoo)

```python
# Accéder au shell
./odoo-bin shell -c odoo.conf

# Vérifier les réservations actives d'un espace
env['sale.order'].search([
    ('x_tr_space_id.name', '=', 'Salle A'),
    ('x_tr_reservation_status', 'in', ['PENDING', 'RESERVED', 'ARRIVED']),
])

# Forcer la création d'un calendar.event manquant
order = env['sale.order'].browse(42)
order.sudo()._sync_create_calendar_event()

# Tester un webhook manuellement
env['theresidence.webhook'].trigger_event(
    'RESERVATION_CREATED', 'reservation', 'test-uuid',
    {'id': 'test-uuid'}, None, 'PENDING'
)

# Vérifier le statut des sessions POS
env['pos.session'].search([('state', '=', 'opened')])
```

---

## 9. Guide d'ajout de fonctionnalités

### Ajouter un nouveau champ à une entité existante

**Exemple : ajouter un champ "note interne" sur les membres**

1. **Modèle** (`models/res_partner.py`) :
```python
x_tr_internal_note = fields.Text(string='Note interne TR')
```

2. **Vue** (`views/res_partner_views.xml`) :
```xml
<record id="view_partner_form_tr_note" model="ir.ui.view">
    <field name="model">res.partner</field>
    <field name="inherit_id" ref="base.view_partner_form"/>
    <field name="arch" type="xml">
        <xpath expr="..." position="after">
            <field name="x_tr_internal_note"/>
        </xpath>
    </field>
</record>
```

3. **API dict** (`to_member_api_dict()`) :
```python
'internalNote': self.x_tr_internal_note or '',
```

4. **Contrôleur** (si besoin d'accepter ce champ en PUT) :
```python
if data.get('internalNote') is not None:
    write_vals['x_tr_internal_note'] = data['internalNote']
```

5. **Mise à jour :** `-u theresidence_api`

---

### Ajouter un nouveau type d'événement webhook

1. Ajouter dans `data/reference_data.xml` :
```xml
<record id="webhook_event_type_space_occupied" model="theresidence.webhook.event.type">
    <field name="name">Espace occupé</field>
    <field name="code">SPACE_OCCUPIED</field>
    <field name="sequence">25</field>
</record>
```

2. Déclencher depuis le modèle :
```python
self.env['theresidence.webhook'].trigger_event(
    'SPACE_OCCUPIED', 'space', space.x_tr_space_uuid,
    space.to_space_api_dict(), 'libre', 'réservé'
)
```

3. **Mise à jour :** `-u theresidence_api`

---

### Ajouter un nouveau statut de réservation

1. Dans `sale_order.py`, étendre la Selection :
```python
x_tr_reservation_status = fields.Selection([
    ('PENDING',   'En attente'),
    ('RESERVED',  'Réservée'),
    ('ARRIVED',   'Arrivée'),
    ('ON_HOLD',   'En pause'),      # ← nouveau
    ('CANCELLED', 'Annulée'),
    ('COMPLETED', 'Terminée'),
])
```

2. Ajouter une méthode d'action :
```python
def action_hold_reservation(self):
    for order in self:
        if order.x_tr_reservation_status != 'ARRIVED':
            raise ValidationError(_("..."))
        old = order.x_tr_reservation_status
        order.write({'x_tr_reservation_status': 'ON_HOLD'})
        self.env['theresidence.webhook'].trigger_event(
            'RESERVATION_STATUS_CHANGED', 'reservation',
            order.x_tr_uuid, order.to_reservation_api_dict(), old, 'ON_HOLD'
        )
```

3. Ajouter le bouton XML et la route API correspondante.

4. **Mise à jour :** `-u theresidence_api`

---

### Ajouter une route API

**Exemple : endpoint pour obtenir les statistiques des espaces**

1. Créer ou étendre un contrôleur (`controllers/stats.py`) :
```python
from odoo import http
from odoo.http import request
from .main import api_auth, success_response, error_response

class StatsController(http.Controller):

    @http.route('/v1/external/stats/spaces', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_spaces')
    def get_space_stats(self, **kwargs):
        spaces = request.env['product.template'].sudo().search([
            ('x_tr_is_space', '=', True)
        ])
        data = [{
            'spaceId': s.x_tr_space_uuid,
            'spaceName': s.name,
            'status': s.x_tr_space_status,
        } for s in spaces]
        return success_response({'spaces': data})
```

2. Enregistrer dans `controllers/__init__.py` :
```python
from . import stats
```

3. **Mise à jour :** `-u theresidence_api`

---

### Ajouter un nouveau module bridge

Si une nouvelle intégration est nécessaire (ex: système de paiement) :

**Structure minimale :**
```
theresidence_payment_bridge/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   └── pos_order.py       # héritage du modèle à étendre
├── views/
│   └── bridge_views.xml   # vues héritées
└── security/
    └── ir.model.access.csv
```

**`__manifest__.py` :**
```python
{
    'name': 'The Residence — Payment Bridge',
    'version': '19.0.1',
    'depends': ['theresidence_api', 'payment'],
    'data': ['security/ir.model.access.csv', 'views/bridge_views.xml'],
}
```

---

## 10. Référence des endpoints API

### En-têtes requis

```http
X-API-Key: tr_votre_clé_api
Content-Type: application/json
```

### Codes de retour

| Code | Signification |
|---|---|
| 200 | Succès |
| 201 | Création réussie |
| 400 | Données invalides |
| 401 | Clé API manquante ou invalide |
| 403 | Permission insuffisante |
| 404 | Ressource introuvable |
| 409 | Conflit (ex: espace non disponible) |
| 500 | Erreur serveur |

### Exemple complet — Créer une réservation

**Requête :**
```http
POST /v1/external/reservations
X-API-Key: tr_abc123...
Content-Type: application/json

{
  "memberId": "uuid-du-membre",
  "spaceId": "uuid-de-lespace",
  "startTime": "2026-04-01T09:00:00",
  "endTime": "2026-04-01T12:00:00",
  "guestCount": 4,
  "notes": "Prévoir un rétroprojecteur",
  "options": [
    { "optionId": "uuid-option", "quantity": 1 }
  ],
  "invitees": [
    { "name": "Jean Dupont", "email": "jean@example.com" }
  ]
}
```

**Réponse 201 :**
```json
{
  "id": "uuid-reservation",
  "status": "PENDING",
  "spaceId": "uuid-espace",
  "spaceName": "Salle de réunion A",
  "memberId": "uuid-membre",
  "memberFirstName": "Alice",
  "memberLastName": "Martin",
  "startTime": "2026-04-01T09:00:00",
  "endTime": "2026-04-01T12:00:00",
  "guestCount": 4,
  "notes": "Prévoir un rétroprojecteur",
  "totalAmount": 75000.0,
  "currency": "XOF",
  "qrToken": "res_abc123def456",
  "options": [...],
  "invitees": [...]
}
```

**Réponse 409 (conflit) :**
```json
{
  "error": "L'espace 'Salle de réunion A' n'est pas disponible pour ce créneau.",
  "code": "SPACE_NOT_AVAILABLE"
}
```

---

## 11. Schéma des statuts et workflows

### Réservations

```
         ┌──────────────────────────────────────────┐
         │                PENDING                   │
         │        (nouvelle réservation)            │
         └──────────┬───────────────┬───────────────┘
                    │               │
               [Réserver]      [Annuler]
                    │               │
         ┌──────────▼──────┐   ┌────▼──────┐
         │    RESERVED     │   │ CANCELLED │
         │ (espace occupé) │   └───────────┘
         └──────────┬──────┘
                    │
              [Marquer arrivé]
                    │
         ┌──────────▼──────┐
         │    ARRIVED      │
         │ (client présent)│
         └──────────┬──────┘
                    │
              [Libérer]
                    │
         ┌──────────▼──────┐
         │   COMPLETED     │
         └─────────────────┘
```

### Commandes mobiles

```
PENDING → CONFIRMED → READY → COMPLETED
   │                             ↑
   │                     (sync: paid/done)
   └──────────────► CANCELLED
```

### Statut de l'espace (`x_tr_space_status`)

```
libre
  │
  ├─[Réserver]──► réservé
  │                   │
  └────────────────[Libérer / Annuler]──► libre (si aucune autre réservation active)
```

### Abonnements

```
ACTIVE ──[Pause]──► PAUSED ──[Reprendre]──► ACTIVE
  │                                           │
  └──────────────[Annuler]──► CANCELLED ──────┘
```

---

## 12. Modules à mettre à jour

Après chaque modification de code, mettre à jour les modules concernés :

```bash
# Commande complète (tous les modules custom)
./odoo-bin -c odoo.conf -u theresidence_api,theresidence_appointment_bridge,theresidence_kitchen_bridge --stop-after-init

# Module principal seulement (modèles, vues, données)
./odoo-bin -c odoo.conf -u theresidence_api --stop-after-init

# Bridge réservations (si modification de bridge_views.xml, models/, JS)
./odoo-bin -c odoo.conf -u theresidence_appointment_bridge --stop-after-init
```

### Quand mettre à jour quel module

| Fichier modifié | Module à mettre à jour |
|---|---|
| `theresidence_api/models/*.py` | `theresidence_api` |
| `theresidence_api/views/*.xml` | `theresidence_api` |
| `theresidence_api/controllers/*.py` | `theresidence_api` (rechargement Odoo suffit parfois) |
| `theresidence_api/static/src/js/*.js` | `theresidence_api` + vider cache (`?debug=assets`) |
| `theresidence_appointment_bridge/models/*.py` | `theresidence_appointment_bridge` |
| `theresidence_appointment_bridge/views/*.xml` | `theresidence_appointment_bridge` |
| `theresidence_appointment_bridge/static/src/js/*.js` | `theresidence_appointment_bridge` + vider cache |
| `theresidence_kitchen_bridge/models/*.py` | `theresidence_kitchen_bridge` |

### Régénérer les assets JS (sans restart)

Ajouter `?debug=assets` dans l'URL du navigateur après une mise à jour JS pour forcer la régénération du bundle.

---

*Documentation générée automatiquement — The Residence CI — Neurones Technologies*
