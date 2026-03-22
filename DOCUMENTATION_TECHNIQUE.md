# Documentation Technique — The Residence CI
**Odoo 19 — Business Club Management System**
*Neurones Technologies — Mise à jour : 2026-03-22*

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Arborescence complète des fichiers](#2-arborescence-complète-des-fichiers)
3. [Module theresidence_api](#3-module-theresidence_api)
   - [__manifest__.py](#31-__manifest__py)
   - [models/api_key.py](#32-modelsapi_keypy)
   - [models/webhook.py](#33-modelswebhookpy)
   - [models/membership_type.py](#34-modelsmembership_typepy)
   - [models/res_partner.py](#35-modelsres_partnerpy)
   - [models/product.py](#36-modelsproductpy)
   - [models/pos_category.py](#37-modelspos_categorypy)
   - [models/sale_order.py](#38-modelssale_orderpy)
   - [models/pos_order.py](#39-modelspos_orderpy)
   - [models/pos_session.py](#310-modelspos_sessionpy)
   - [models/mobileOrder.py](#311-modelsmobileorderpy)
   - [models/wizard_reject_order.py](#312-modelswizard_reject_orderpy)
   - [controllers/main.py](#313-controllersmainpy)
   - [controllers/reference.py](#314-controllersreferencepy)
   - [controllers/reservations.py](#315-controllersreservationspy)
   - [controllers/orders.py](#316-controllersorderspy)
   - [controllers/subscriptions.py](#317-controllerssubscriptionspy)
   - [controllers/webhooks.py](#318-controllerswebhookspy)
   - [static/src/js/ReservationScreen.js](#319-staticsrcjsreservationscreenjs)
   - [static/src/js/ReservationButton.js](#320-staticsrcjsreservationbuttonjs)
   - [security/ir.model.access.csv](#321-securityirmodelacccesscsv)
4. [Module theresidence_appointment_bridge](#4-module-theresidence_appointment_bridge)
   - [__manifest__.py](#41-__manifest__py)
   - [models/sale_order.py](#42-modelssale_orderpy)
   - [models/calendar_event.py](#43-modelscalendar_eventpy)
   - [models/product_template.py](#44-modelsproduct_templatepy)
   - [models/reservation_invitee.py](#45-modelsreservation_inviteepy)
   - [models/reservation_option.py](#46-modelsreservation_optionpy)
   - [models/pos_order.py](#47-modelspos_orderpy)
   - [static/src/js/pos_reservation_notify.js](#48-staticsrcjspos_reservation_notifyjs)
   - [static/src/js/gantt_popover_patch.js](#49-staticsrcjsgantt_popover_patchjs)
   - [static/src/js/appointment_list_patch.js](#410-staticsrcjsappointment_list_patchjs)
   - [static/src/css/appointment_list.css](#411-staticsrccssappointment_listcss)
   - [security/ir.model.access.csv](#412-securityirmodelacccesscsv)
5. [Module theresidence_kitchen_bridge](#5-module-theresidence_kitchen_bridge)
   - [models/pos_order.py](#51-modelspos_orderpy)
   - [models/pos_prep_order.py](#52-modelspos_prep_orderpy)
   - [models/pos_prep_state.py](#53-modelspos_prep_statepy)
6. [Tableaux de référence rapide](#6-tableaux-de-référence-rapide)
7. [Guide de débogage](#7-guide-de-débogage)
8. [Guide d'ajout de fonctionnalités](#8-guide-dajout-de-fonctionnalités)

---

## 1. Vue d'ensemble

The Residence CI est une installation **Odoo 19** sur mesure exposant une **API REST** pour une application mobile, et étendant le **Point de Vente** natif pour la gestion d'un business club à Abidjan.

### Modules custom et leurs rôles

| Module | Rôle | Dépendances Odoo |
|---|---|---|
| `theresidence_api` | Module principal : modèles, API REST, POS | `base`, `sale`, `sale_subscription`, `sale_renting`, `point_of_sale` |
| `theresidence_appointment_bridge` | Pont réservations ↔ planning POS natif | `theresidence_api`, `appointment`, `pos_appointment` |
| `theresidence_kitchen_bridge` | Pont commandes mobiles ↔ écran cuisine | `theresidence_api`, `pos_enterprise` |

### Convention de nommage universelle

- **Préfixe champs custom :** `x_tr_` (ex : `x_tr_uuid`, `x_tr_is_member`)
- **UUID externe :** `x_tr_uuid` — identifiant exposé à l'API, distinct de l'`id` Odoo
- **Flags booléens :** `x_tr_is_*` (ex : `x_tr_is_reservation`, `x_tr_is_space`)
- **Statuts :** `x_tr_*_status` — Selection fields avec valeurs en MAJUSCULES
- **Préfixe logs :** `[TR BRIDGE]`, `[TR KITCHEN]`, `[TR API]`

---

## 2. Arborescence complète des fichiers

```
LaresidenceCI/
│
├── DOCUMENTATION_TECHNIQUE.md               ← ce fichier
│
├── theresidence_api_true/
│   └── theresidence_api/
│       ├── __manifest__.py                  ← déclaration module
│       ├── __init__.py
│       ├── controllers/
│       │   ├── __init__.py                  ← importe main, reference, reservations, orders, subscriptions, webhooks
│       │   ├── main.py                      ← helpers JSON, decorator api_auth, routes /health /info
│       │   ├── reference.py                 ← routes membres, espaces, menu, plans
│       │   ├── reservations.py              ← routes CRUD réservations + options + invités
│       │   ├── orders.py                    ← routes CRUD commandes mobiles
│       │   ├── subscriptions.py             ← routes CRUD abonnements
│       │   └── webhooks.py                  ← routes CRUD webhooks + events + test
│       ├── models/
│       │   ├── __init__.py                  ← importe tous les modèles
│       │   ├── api_key.py                   ← theresidence.api.key
│       │   ├── webhook.py                   ← theresidence.webhook + event.type + event
│       │   ├── membership_type.py           ← 4 modèles de données de référence
│       │   ├── res_partner.py               ← héritage res.partner (membres)
│       │   ├── product.py                   ← héritage product.template + product.product
│       │   ├── pos_category.py              ← héritage pos.category (catégories menu)
│       │   ├── sale_order.py                ← héritage sale.order + sale.order.line (réservations + abonnements)
│       │   ├── pos_order.py                 ← héritage pos.order + pos.order.line (commandes mobiles)
│       │   ├── pos_session.py               ← héritage pos.config (champs calculés session)
│       │   ├── mobileOrder.py               ← mobile.order + mobile.order.line (staging)
│       │   └── wizard_reject_order.py       ← mobile.order.reject.wizard (wizard rejet)
│       ├── views/
│       │   ├── api_views.xml                ← vues clés API, webhooks, données référence, menus
│       │   ├── res_partner_views.xml        ← champs membre dans fiche partenaire
│       │   ├── product_views.xml            ← champs espace/plan dans fiche produit
│       │   ├── sale_order_views.xml         ← vues réservations et abonnements
│       │   ├── mobile_order_views.xml       ← vues commandes mobiles staging
│       │   ├── pos_config_views.xml         ← configuration POS
│       │   └── pos_views.xml                ← vues POS (commandes mobiles dans POS)
│       ├── static/src/
│       │   ├── js/
│       │   │   ├── ReservationScreen.js     ← composant OWL panneau réservations POS
│       │   │   └── ReservationButton.js     ← patch Chrome POS (bouton + panneau)
│       │   ├── xml/
│       │   │   └── ReservationScreen.xml    ← template OWL du panneau
│       │   └── css/
│       │       └── reservation.css          ← styles du panneau réservations
│       ├── data/
│       │   └── reference_data.xml           ← données initiales types d'événements webhook
│       ├── scripts/
│       │   └── seed_test_reservations.py    ← script peuplement données de test
│       └── security/
│           └── ir.model.access.csv          ← droits d'accès tous modèles custom
│
├── theresidence_appointment_bridge/
│   ├── __manifest__.py
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py                      ← importe sale_order, pos_order, calendar_event, product_template, reservation_invitee, reservation_option
│   │   ├── sale_order.py                    ← héritage sale.order (sync calendar.event, chargement POS)
│   │   ├── pos_order.py                     ← héritage pos.order (annulation picking stock)
│   │   ├── calendar_event.py                ← héritage calendar.event (sync inverse + boutons TR)
│   │   ├── product_template.py              ← héritage product.template (appointment.type partagé)
│   │   ├── reservation_invitee.py           ← héritage theresidence.reservation.invitee (refresh calendar)
│   │   └── reservation_option.py            ← héritage theresidence.reservation.option (refresh calendar)
│   ├── views/
│   │   ├── bridge_views.xml                 ← vues héritées : product, sale.order, calendar.event
│   │   └── assets.xml                       ← assets POS supplémentaires
│   ├── static/src/
│   │   ├── js/
│   │   │   ├── pos_reservation_notify.js    ← polling 10s + notifications toast + son
│   │   │   ├── gantt_popover_patch.js       ← patch popover Gantt POS (statut réservation)
│   │   │   └── appointment_list_patch.js    ← MutationObserver enrichissement cartes liste POS
│   │   ├── css/
│   │   │   └── appointment_list.css         ← styles cartes enrichies (.tr-row, .tr-lbl, .tr-val)
│   │   └── sounds/
│   │       └── new_reservation.wav          ← son notification nouvelle réservation
│   └── security/
│       └── ir.model.access.csv
│
└── theresidence_kitchen_bridge/
    ├── __manifest__.py
    ├── __init__.py
    └── models/
        ├── __init__.py
        ├── pos_order.py                     ← héritage pos.order (sync_from_ui : PENDING→CONFIRMED)
        ├── pos_prep_order.py                ← héritage pos.prep.order (cuisine → CONFIRMED)
        └── pos_prep_state.py                ← héritage pos.prep.state (cuisine terminée → READY)
```

---

## 3. Module theresidence_api

### 3.1 `__manifest__.py`

```
Nom     : The Residence - API Module
Version : 19.0.1
Auteur  : Neurones Technologies
Licence : LGPL-3
```

**Dépendances :** `base`, `sale_subscription`, `sale`, `sale_renting`, `point_of_sale`

**Fichiers data chargés (dans l'ordre) :**
1. `security/ir.model.access.csv`
2. `data/reference_data.xml`
3. `views/api_views.xml`
4. `views/res_partner_views.xml`
5. `views/product_views.xml`
6. `views/sale_order_views.xml`
7. `views/mobile_order_views.xml`
8. `views/pos_config_views.xml`
9. `views/pos_views.xml`

**Assets POS (`point_of_sale._assets_pos`) :**
- `static/src/xml/ReservationScreen.xml`
- `static/src/js/ReservationScreen.js`
- `static/src/js/ReservationButton.js`
- `static/src/css/reservation.css`

---

### 3.2 `models/api_key.py`

**Modèle :** `theresidence.api.key`
**Tri par défaut :** `name`

#### Champs

| Nom | Type | Attributs | Description |
|---|---|---|---|
| `name` | Char | required | Nom descriptif |
| `key` | Char | readonly, copy=False | Valeur : `tr_{urlsafe_token_32}` |
| `description` | Text | — | Description |
| `is_active` | Boolean | default=True | Clé active |
| `can_read_members` | Boolean | default=True | Permission lecture membres |
| `can_write_members` | Boolean | default=False | Permission écriture membres |
| `can_read_spaces` | Boolean | default=True | Permission lecture espaces |
| `can_read_menu` | Boolean | default=True | Permission lecture menu |
| `can_read_reservations` | Boolean | default=True | Permission lecture réservations |
| `can_write_reservations` | Boolean | default=False | Permission écriture réservations |
| `can_read_orders` | Boolean | default=True | Permission lecture commandes |
| `can_write_orders` | Boolean | default=False | Permission écriture commandes |
| `can_read_subscriptions` | Boolean | default=True | Permission lecture abonnements |
| `can_write_subscriptions` | Boolean | default=False | Permission écriture abonnements |
| `can_manage_webhooks` | Boolean | default=False | Permission gestion webhooks |

#### Méthodes

| Méthode | Décorateur | Signature | Description |
|---|---|---|---|
| `create` | `@api.model_create_multi` | `(vals_list)` | Génère la clé si absente |
| `_generate_api_key` | `@staticmethod` | `() → str` | Retourne `"tr_{secrets.token_urlsafe(32)}"` |
| `regenerate_key` | — | `(self)` | Écrase `key` avec une nouvelle valeur |
| `has_permission` | — | `(self, permission: str) → bool` | Cherche dans `perm_map` dict |
| `validate_key` | `@api.model` | `(key: str) → record\|False` | Cherche par `key` + `is_active=True` |

**`perm_map` dans `has_permission` :**
```python
{
    'read_members':      self.can_read_members,
    'write_members':     self.can_write_members,
    'read_spaces':       self.can_read_spaces,
    'read_menu':         self.can_read_menu,
    'read_reservations': self.can_read_reservations,
    'write_reservations':self.can_write_reservations,
    'read_orders':       self.can_read_orders,
    'write_orders':      self.can_write_orders,
    'read_subscriptions':self.can_read_subscriptions,
    'write_subscriptions':self.can_write_subscriptions,
    'manage_webhooks':   self.can_manage_webhooks,
}
```

---

### 3.3 `models/webhook.py`

#### Modèle 1 : `theresidence.webhook`

**Tri par défaut :** `name`

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `name` | Char | required | Nom du webhook |
| `url` | Char | required | URL de destination |
| `secret` | Char | — | Secret pour signature HMAC-SHA256 |
| `is_active` | Boolean | default=True | Webhook actif |
| `event_type_ids` | Many2many → `theresidence.webhook.event.type` | — | Types d'événements souscrits |
| `event_ids` | One2many → `theresidence.webhook.event` | inverse: webhook_id | Historique des envois |

| Méthode | Décorateur | Signature | Description |
|---|---|---|---|
| `_compute_signature` | — | `(payload: str) → str\|None` | HMAC-SHA256 hex si `secret` défini |
| `send_event` | — | `(event_type, entity_type, entity_id, data, previous_status=None, new_status=None)` | Crée record event + POST HTTP (timeout 30s) |
| `trigger_event` | `@api.model` | `(event_type, entity_type, entity_id, data, previous_status=None, new_status=None)` | Cherche event.type par code → envoie à tous les webhooks actifs |

**Format payload `send_event` :**
```json
{
  "id": "uuid4",
  "eventType": "RESERVATION_CREATED",
  "entityType": "reservation",
  "entityId": "uuid-entité",
  "data": { ...to_*_api_dict()... },
  "previousStatus": null,
  "newStatus": "PENDING",
  "timestamp": "2026-03-22T10:30:45.123456Z"
}
```

**En-tête signature :** `X-Webhook-Signature: sha256={hmac_hexdigest}`

#### Modèle 2 : `theresidence.webhook.event.type`

**Tri :** `sequence, name` | **Contrainte SQL :** `code` unique

| Champ | Type | Attributs |
|---|---|---|
| `name` | Char | required, translate |
| `code` | Char | required, index |
| `description` | Text | translate |
| `sequence` | Integer | default=10 |

#### Modèle 3 : `theresidence.webhook.event`

**Tri :** `create_date desc`

| Champ | Type | Description |
|---|---|---|
| `webhook_id` | Many2one → `theresidence.webhook` | ondelete='cascade' |
| `event_type` | Char | Code de l'événement |
| `payload` | Text | JSON envoyé |
| `status` | Selection | PENDING / SUCCESS / FAILED |
| `response_code` | Integer | Code HTTP réponse |
| `response_body` | Text | Corps réponse (max 2000 chars) |
| `sent_at` | Datetime | Horodatage envoi |

---

### 3.4 `models/membership_type.py`

#### Modèle 1 : `theresidence.membership.type`

**Tri :** `sort_order, name` | **Contrainte SQL :** `code` unique

| Champ | Type | Attributs |
|---|---|---|
| `name` | Char | required, translate |
| `code` | Char | required, index |
| `description` | Text | translate |
| `sort_order` | Integer | default=10 |
| `active` | Boolean | default=True |
| `x_uuid` | Char | readonly, copy=False, default=uuid4 |

**Méthode `to_api_dict()` → dict :**
```python
{'id': x_uuid, 'code': code, 'name': name, 'description': description, 'sortOrder': sort_order}
```

#### Modèle 2 : `theresidence.space.type`

**Tri :** `sequence, name` | **Contrainte SQL :** `code` unique

| Champ | Type |
|---|---|
| `name` | Char (required, translate) |
| `code` | Char (required, index) |
| `description` | Text (translate) |
| `sequence` | Integer (default=10) |
| `active` | Boolean |

#### Modèle 3 : `theresidence.reservation.option.def`

**Tri :** `sequence, name` | **Contrainte SQL :** `code` unique

| Champ | Type | Attributs |
|---|---|---|
| `name` | Char | required, translate |
| `code` | Char | required, index |
| `description` | Text | translate |
| `scope` | Selection | SPACE / EVENT / GLOBAL, default='SPACE' |
| `price` | Float | digits='Product Price' |
| `currency_id` | Many2one → `res.currency` | default=company currency |
| `sequence` | Integer | default=10 |
| `active` | Boolean | |
| `x_uuid` | Char | readonly, copy=False, default=uuid4 |

**Méthode `to_api_dict()` → dict :**
```python
{'id': x_uuid, 'code': code, 'scope': scope, 'label': name, 'description': description, 'price': price, 'currency': ...}
```

#### Modèle 4 : `theresidence.menu.kind`

**Tri :** `sequence, name`

| Champ | Type |
|---|---|
| `name` | Char (required, translate) |
| `code` | Char (index) |
| `description` | Text |
| `sequence` | Integer (default=10) |
| `active` | Boolean |
| `x_uuid` | Char (readonly, copy=False, default=uuid4) |

**Méthode `to_api_dict()` → dict :**
```python
{'id': x_uuid, 'code': code, 'name': name, 'sortOrder': sequence}
```

---

### 3.5 `models/res_partner.py`

**Modèle :** `res.partner` (héritage `_inherit`)

#### Champs ajoutés

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `x_tr_uuid` | Char | copy=False, readonly, index | UUID unique API |
| `x_tr_qr_token` | Char | copy=False, readonly | Format : `member-{token_urlsafe(16)}` |
| `x_tr_is_member` | Boolean | default=False | Marque le partenaire comme membre TR |
| `x_tr_member_status` | Selection | default='PENDING' | PENDING / ACTIVE / SUSPENDED / INACTIVE |
| `x_tr_membership_type_id` | Many2one → `theresidence.membership.type` | — | Type d'adhésion |
| `x_tr_joined_at` | Date | — | Date d'adhésion |

#### Méthodes

| Méthode | Décorateur | Description |
|---|---|---|
| `create` | `@api.model_create_multi` | Génère UUID + QR token pour membres |
| `write` | — | Génère UUID/QR si `x_tr_is_member` activé. Capture les anciennes valeurs (prêt pour webhooks commentés). |
| `unlink` | — | Capture les données avant suppression (prêt pour webhooks commentés). |
| `to_member_api_dict` | — | Sérialise en dict camelCase pour l'API |
| `action_generate_ceo_subscriptions` | — | Crée un abonnement "Abonnement CEO" pour tous les membres (produit récurrent `recurring_invoice=True`). Vérifie l'existant, log les erreurs, retourne notification UI. |
| `create_member_from_api` | `@api.model` | Crée ou met à jour un membre depuis les données API. Si email existant → `write()`. Cherche le type d'adhésion par `membershipTypeCode`. |

**Format `to_member_api_dict()` :**
```json
{
  "id": "x_tr_uuid",
  "firstName": "...",  "lastName": "...",
  "email": "...",  "phone": "...",
  "companyName": "...",  "jobTitle": "...",
  "membershipTypeId": "uuid",  "membershipTypeCode": "...",  "membershipTypeName": "...",
  "status": "ACTIVE",
  "joinedAt": "2026-01-15",
  "qrToken": "member-abc123"
}
```

---

### 3.6 `models/product.py`

#### Modèle 1 : `product.template` (héritage)

**Champs ajoutés :**

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `x_tr_is_space` | Boolean | — | Marque le produit comme espace |
| `x_tr_space_uuid` | Char | copy=False, readonly, index | UUID espace (auto-généré) |
| `x_tr_space_capacity` | Integer | — | Capacité max |
| `x_tr_space_type_id` | Many2one → `theresidence.space.type` | — | Type d'espace |
| `x_tr_space_description` | Text | — | Description |
| `x_tr_is_occupied` | Boolean | default=False | Occupation courante (legacy) |
| `x_tr_space_status` | Selection | default='libre' | `libre` / `réservé` |
| `x_tr_is_subscription_plan` | Boolean | — | Marque comme plan d'abonnement |
| `x_tr_membership_type_id` | Many2one → `theresidence.membership.type` | — | Type d'adhésion lié |
| `x_tr_duration_months` | Integer | default=1 | Durée du plan en mois |

| Méthode | Décorateur | Description |
|---|---|---|
| `create` | `@api.model_create_multi` | Génère UUID, active `rent_ok=True` pour les espaces |
| `write` | — | Génère UUID si `x_tr_is_space` activé, active `rent_ok` |
| `unlink` | — | Capture données avant suppression |
| `action_free_space` | — | Libère manuellement : `x_tr_is_occupied=False`, `x_tr_space_status='libre'` |
| `check_availability` | — | `(start_time, end_time) → dict` Compte les réservations PENDING/RESERVED/ARRIVED qui chevauchent |
| `to_space_api_dict` | — | Sérialise l'espace pour l'API |
| `to_subscription_plan_api_dict` | — | Sérialise le plan d'abonnement |

**Format `check_availability()` retour :**
```json
{
  "spaceId": "uuid",
  "spaceName": "Salle A",
  "startTime": "2026-04-01T09:00:00",
  "endTime": "2026-04-01T12:00:00",
  "isAvailable": true,
  "conflictingReservations": 0
}
```

**Algorithme overlap :** `start < other_end AND end > other_start`

#### Modèle 2 : `product.product` (héritage)

| Méthode | Description |
|---|---|
| `to_menu_item_api_dict` | Sérialise un produit POS (catégorie, kind, prix, image) |

---

### 3.7 `models/pos_category.py`

**Modèle :** `pos.category` (héritage)

| Champ | Type | Attributs |
|---|---|---|
| `x_tr_uuid` | Char | readonly, copy=False, default=uuid4 |
| `x_tr_menu_kind_id` | Many2one → `theresidence.menu.kind` | — |

| Méthode | Décorateur | Description |
|---|---|---|
| `_get_webhook_service` | — | Retourne `theresidence.webhook.service` en mode SAFE (None si indisponible, vérifie `is_event_enabled` + `trigger_event`) |
| `_register_hook` | — | Sync initiale au démarrage Odoo — envoie `POS_CATEGORY_CREATED` pour toutes les catégories existantes |
| `create` | `@api.model_create_multi` | Génère UUID + déclenche `POS_CATEGORY_CREATED` (si webhook actif, ignore si `skip_webhook` en contexte) |
| `write` | — | Détecte champs modifiés (name, parent, sequence, image) + déclenche `POS_CATEGORY_UPDATED` |
| `unlink` | — | Capture données avant suppression + déclenche `POS_CATEGORY_DELETED` |
| `to_category_api_dict` | — | Sérialise : id, parentId, kindId, kindName, name, imageUrl, sortOrder. Remonte l'arbre jusqu'à la racine pour `kindId`. |

> **Note :** Ce modèle utilise `theresidence.webhook.service` (service externe) et non `theresidence.webhook`. Si ce service n'est pas chargé, tout est ignoré silencieusement.

---

### 3.8 `models/sale_order.py`

**Hérite :** `sale.order` + `sale.order.line`

#### SaleOrderLine (héritage `sale.order.line`)

| Méthode | Description |
|---|---|
| `_planning_slot_generation` | Skip la génération de créneaux planning pour les réservations TR (`x_tr_is_reservation=True`) |

#### SaleOrder (héritage `sale.order`)

**Champs Réservation :**

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `x_tr_uuid` | Char | copy=False, readonly, index | UUID réservation |
| `x_tr_is_reservation` | Boolean | default=False | Marque comme réservation TR |
| `x_tr_reservation_status` | Selection | default='PENDING' | PENDING / RESERVED / ARRIVED / CANCELLED / COMPLETED |
| `x_tr_space_id` | Many2one → `product.template` | domain: is_space=True | Espace réservé |
| `x_tr_start_time` | Datetime | — | Début créneau |
| `x_tr_end_time` | Datetime | — | Fin créneau |
| `x_tr_guest_count` | Integer | — | Nombre d'invités |
| `x_tr_notes` | Text | — | Notes du client |
| `x_tr_rejection_reason` | Text | — | Raison de rejet |
| `x_tr_qr_token` | Char | copy=False | Format : `res-{hex12}` |
| `x_tr_invitee_ids` | One2many → `theresidence.reservation.invitee` | inverse: reservation_id | Invités |
| `x_tr_option_ids` | One2many → `theresidence.reservation.option` | inverse: reservation_id | Options |

**Champs Abonnement :**

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `x_tr_is_subscription` | Boolean | default=False | Marque comme abonnement TR |
| `x_tr_subscription_status` | Selection | default='ACTIVE' | ACTIVE / PAUSED / CANCELLED / EXPIRED |
| `x_tr_plan_id` | Many2one → `product.template` | domain: is_subscription_plan=True | Plan |
| `x_tr_billing_period` | Selection | default='MONTHLY' | MONTHLY / QUARTERLY / YEARLY |
| `x_tr_auto_renew` | Boolean | default=True | Renouvellement automatique |
| `x_tr_sub_start_date` | Date | — | Début de l'abonnement |
| `x_tr_sub_end_date` | Date | — | Fin de l'abonnement |

**Méthodes complètes :**

| Méthode | Décorateur | Description |
|---|---|---|
| `create` | `@api.model_create_multi` | Génère UUID + `x_tr_qr_token` pour réservations et abonnements |
| `to_reservation_api_dict` | — | Sérialise la réservation complète (avec options et invités imbriqués) |
| `get_pos_reservations` | `@api.model` | `(date_filter='today')` — Filtre today : PENDING/RESERVED du jour + ARRIVED quel que soit le jour. Retourne `[dict]` |
| `create_reservation_from_api` | `@api.model` | Crée réservation avec vérif disponibilité, ligne commande, invités, options. Déclenche `RESERVATION_CREATED`. |
| `_check_no_double_booking` | `@api.constrains(...)` | Contrainte DB : bloque tout chevauchement sur le même espace en statut PENDING/RESERVED/ARRIVED |
| `_space_has_other_active_reservations` | — | `(space) → bool` Compte les réservations actives sur l'espace, hors `self` |
| `_mark_space_reserved` | — | `(space)` → `x_tr_is_occupied=True`, `x_tr_space_status='réservé'` |
| `_mark_space_free_if_no_active` | — | `(space)` → libère seulement si aucune autre réservation active |
| `action_reserve_reservation` | — | PENDING → RESERVED. Auto-confirme sale.order si draft. Marque espace occupé. Webhook RESERVATION_STATUS_CHANGED. |
| `action_arrive_reservation` | — | RESERVED → ARRIVED. Webhook RESERVATION_STATUS_CHANGED. |
| `action_release_reservation` | — | RESERVED/ARRIVED → COMPLETED. Libère espace si plus de réservation active. Webhook RESERVATION_STATUS_CHANGED. |
| `action_cancel_reservation` | — | Any → CANCELLED (sauf COMPLETED/CANCELLED). Libère espace si RESERVED/ARRIVED. Webhook RESERVATION_CANCELLED. |
| `action_approve_reservation` | — | Alias de `action_reserve_reservation()` |
| `action_reject_reservation` | — | `(reason='')` PENDING → CANCELLED avec raison. Webhook RESERVATION_STATUS_CHANGED. |
| `action_checkin_reservation` | — | Alias de `action_arrive_reservation()` |
| `pos_reserve_reservation` | `@api.model` | `(uuid)` Cherche par UUID → appelle `action_reserve_reservation()` |
| `pos_arrive_reservation` | `@api.model` | `(uuid)` Cherche par UUID → appelle `action_arrive_reservation()` |
| `pos_release_reservation` | `@api.model` | `(uuid)` Cherche par UUID → appelle `action_release_reservation()` |
| `pos_cancel_reservation` | `@api.model` | `(uuid)` Cherche par UUID → appelle `action_cancel_reservation()` |
| `to_subscription_api_dict` | — | Sérialise l'abonnement pour l'API |
| `create_subscription_from_api` | `@api.model` | Crée un abonnement depuis l'API. Déclenche `SUBSCRIPTION_CREATED`. |
| `action_pause_subscription` | — | ACTIVE → PAUSED. Déclenche `SUBSCRIPTION_STATUS_CHANGED`. |
| `action_resume_subscription` | — | PAUSED → ACTIVE. Déclenche `SUBSCRIPTION_STATUS_CHANGED`. |
| `action_cancel_subscription` | — | Any → CANCELLED. Déclenche `SUBSCRIPTION_CANCELLED`. |

**Format `to_reservation_api_dict()` :**
```json
{
  "id": "uuid",
  "memberId": "uuid",  "memberFirstName": "...",  "memberLastName": "...",  "memberEmail": "...",
  "spaceId": "uuid",  "spaceName": "...",
  "startTime": "ISO",  "endTime": "ISO",
  "guestCount": 4,
  "status": "PENDING",
  "totalAmount": 75000.0,  "currency": "XOF",
  "notes": "...",  "saleOrder": "S00001",  "qrToken": "res_abc123",
  "options": [...],  "invitees": [...],
  "createdAt": "ISO",  "updatedAt": "ISO"
}
```

---

### 3.9 `models/pos_order.py`

**Hérite :** `pos.order` + `pos.order.line`

#### PosOrderLine (héritage `pos.order.line`)

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `translated_product_name` | Char | compute, store=False | Nom du produit dans la langue courante |

| Méthode | Description |
|---|---|
| `_compute_translated_product_name` | `line.product_id.with_context(lang=env.lang).name` |

#### PosOrder (héritage `pos.order`)

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `x_tr_uuid` | Char | copy=False, readonly, index | UUID commande |
| `x_tr_is_mobile_order` | Boolean | default=False | Commande depuis app mobile |
| `x_tr_order_status` | Selection | index, tracking | PENDING / CONFIRMED / READY / SENT_TO_POS / CANCELLED / PAID / COMPLETED — **pas de required ni NOT NULL** |
| `x_tr_order_mode` | Selection | default='PICKUP' | PICKUP / DELIVERY / DINE_IN |
| `x_tr_delivery_address` | Text | — | Adresse de livraison |
| `x_tr_qr_token` | Char | copy=False | Token QR commande |
| `x_tr_member_id` | Many2one → `res.partner` | domain: is_member=True | Membre qui commande |

**Constante de mapping Odoo state → statut TR :**
```python
_STATE_TO_ORDER_STATUS = {
    'paid':   'PAID',
    'done':   'COMPLETED',
    'cancel': 'CANCELLED',
}
```

| Méthode | Décorateur | Description |
|---|---|---|
| `write` | — | Si `state` change et commande mobile et non en contexte `tr_skip_order_sync` → applique `_STATE_TO_ORDER_STATUS` → écrit avec `tr_skip_order_sync=True` → déclenche `ORDER_STATUS_CHANGED` |
| `create` | `@api.model_create_multi` | Si `x_tr_is_mobile_order=True` → génère UUID + QR token + force `x_tr_order_status='PENDING'`. Sinon → `pop('x_tr_order_status')` |
| `to_order_api_dict` | — | Sérialise la commande avec ses lignes |
| `create_order_from_api` | `@api.model` | `(data)` Cherche membre, session POS ouverte, crée `pos.order` + lignes avec calcul taxes. Déclenche `ORDER_CREATED`. |
| `get_new_pending_orders` | `@api.model` | `(since_iso: str) → list[dict]` Retourne les commandes PENDING créées après la date ISO |
| `action_confirm_order` | — | PENDING → CONFIRMED. Déclenche `ORDER_STATUS_CHANGED`. |
| `action_ready_order` | — | CONFIRMED → READY. Déclenche `ORDER_STATUS_CHANGED`. |
| `action_complete_order` | — | READY → COMPLETED. Déclenche `ORDER_STATUS_CHANGED`. |
| `action_cancel_order` | — | `(reason=None)` Any → CANCELLED. Déclenche `ORDER_CANCELLED`. |

**Format `to_order_api_dict()` :**
```json
{
  "id": "uuid",
  "memberId": "uuid",  "memberFirstName": "...",  "memberLastName": "...",  "memberEmail": "...",
  "mode": "PICKUP",
  "status": "PENDING",
  "totalAmount": 15000.0,  "currency": "XOF",
  "qrToken": "order-abc123",
  "deliveryAddress": "",
  "items": [{"id": "...", "menuItemId": "...", "menuItemName": "...", "quantity": 2, "unitPrice": 5000.0, "amount": 10000.0}],
  "internal_note": "",
  "createdAt": "ISO",  "updatedAt": "ISO"
}
```

---

### 3.10 `models/pos_session.py`

**Modèle :** `pos.config` (héritage)

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `last_session_closing_date` | Date | compute, store=True, depends: session_ids.stop_at | Date de clôture de la dernière session |
| `last_session_closing_cash` | Date | compute, store=True, depends: session_ids.stop_at | Idem (champ séparé pour un usage différent) |

| Méthode | Description |
|---|---|
| `_safe_dt` | `(dt) → datetime UTC` Normalise en UTC aware. Retourne `MIN_DATETIME = datetime(1970,1,1,UTC)` si vide. |
| `_compute_last_session` | Trie les sessions par `stop_at` desc, retourne la date de la première |
| `_compute_last_session_cash` | Idem |

---

### 3.11 `models/mobileOrder.py`

#### Modèle 1 : `mobile.order`

**Hérite :** `mail.thread`, `mail.activity.mixin`
**Tri :** `date_order desc` | **Rec name :** `name`

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `name` | Char | required, readonly, copy=False | Référence auto via séquence `mobile.order` |
| `x_tr_uuid` | Char | index, readonly, copy=False | UUID staging |
| `x_tr_qr_token` | Char | readonly, copy=False | Format : `mob-{hex12}` |
| `partner_id` | Many2one → `res.partner` | — | Client |
| `x_tr_member_id` | Many2one → `res.partner` | domain: is_member=True | Membre |
| `date_order` | Datetime | required, default=now | Date commande |
| `x_tr_order_mode` | Selection | required, default='PICKUP' | PICKUP / DELIVERY / DINE_IN |
| `x_tr_delivery_address` | Text | — | Adresse livraison |
| `note` | Text | — | Notes |
| `lines` | One2many → `mobile.order.line` | inverse: mobile_order_id | Lignes |
| `x_tr_order_status` | Selection | required, default='PENDING', tracking | PENDING / CONFIRMED / SENT_TO_POS / REJECTED / PAID / COMPLETED |
| `x_tr_is_mobile_order` | Boolean | default=True | Toujours True sur ce modèle |
| `rejection_reason` | Text | — | Raison de rejet |
| `pos_order_id` | Many2one → `pos.order` | readonly, copy=False, ondelete='set null' | Commande POS créée |
| `pos_order_status` | Selection | related: pos_order_id.x_tr_order_status, store | Statut POS en temps réel |
| `amount_total` | Float | compute, store, depends: lines.price_subtotal_incl | Total TTC |
| `amount_tax` | Float | compute, store | Montant taxes |

| Méthode | Décorateur | Description |
|---|---|---|
| `_compute_amounts` | `@api.depends(...)` | `amount_total = sum(lines.price_subtotal_incl)`, `amount_tax = total - sum(ht)` |
| `create` | `@api.model_create_multi` | Génère nom via séquence, UUID et QR token |
| `action_validate` | — | PENDING → CONFIRMED |
| `action_send_to_pos` | — | CONFIRMED → SENT_TO_POS. Appelle `_prepare_pos_order_valeur()` puis `pos.order.create_order_from_api()`. Copie UUID/QR token. |
| `_prepare_pos_order_valeur` | — | Formate le dict pour `create_order_from_api()`. Vérifie session POS ouverte. |
| `action_reject` | — | Ouvre le wizard `mobile.order.reject.wizard` dans une fenêtre modale. |
| `create_order_from_api` | `@api.model` | `(data)` Crée staging depuis API. Résout membre, crée lignes avec taxes. |
| `to_staging_api_dict` | — | Sérialise pour l'API. Si `pos_order_id` → ajoute `posOrderId` et `posStatus`. |

#### Modèle 2 : `mobile.order.line`

| Champ | Type | Attributs |
|---|---|---|
| `mobile_order_id` | Many2one → `mobile.order` | required, ondelete='cascade', index |
| `product_id` | Many2one → `product.product` | required |
| `qty` | Float | default=1.0 |
| `price_unit` | Float | — |
| `discount` | Float | default=0.0 |
| `tax_ids` | Many2many → `account.tax` | — |
| `price_subtotal` | Float | compute, store | HT |
| `price_subtotal_incl` | Float | compute, store | TTC |

| Méthode | Décorateur | Description |
|---|---|---|
| `_compute_price` | `@api.depends(qty, price_unit, discount, tax_ids, ...)` | Calcule HT/TTC via `tax_ids.compute_all()` avec remise |
| `_onchange_product_id` | `@api.onchange('product_id')` | Pré-remplit `price_unit` et `tax_ids` depuis le produit |

---

### 3.12 `models/wizard_reject_order.py`

**Modèle :** `mobile.order.reject.wizard` (TransientModel)

| Champ | Type | Attributs |
|---|---|---|
| `order_id` | Many2one → `mobile.order` | required |
| `rejection_reason` | Text | required |

| Méthode | Description |
|---|---|
| `action_confirm_reject` | Vérifie statut ≠ SENT_TO_POS → écrit `x_tr_order_status='REJECTED'` + `rejection_reason` |

---

### 3.13 `controllers/main.py`

**Variable globale :** `API_PREFIX = '/v1/external'`

#### Fonctions utilitaires (utilisées dans tous les controllers)

| Fonction | Signature | Description |
|---|---|---|
| `json_response` | `(data, status=200) → Response` | Response JSON brute, charset utf-8 |
| `error_response` | `(message, error_code, status=400) → Response` | `{success: False, message, errorCode, timestamp}` |
| `success_response` | `(data, status=200, headers=None) → Response` | `{success: True, data, timestamp}` + headers anti-cache `Cache-Control: no-store` |
| `paginated_response` | `(items, total, page, size) → Response` | `{success, content, totalCount, pagingInfo: {size, pageCount, currentPage, hasPrevious, hasNext}, timestamp}` |
| `api_auth` | `(permission=None) → decorator` | Lit `X-API-Key`, valide avec `validate_key()`, vérifie permission. Stocke `request.api_key`. |

#### Classe `MainController(http.Controller)`

| Route | Méthode | Auth | Fonction | Description |
|---|---|---|---|---|
| `/v1/external/health` | GET | public | `health_check` | Retourne `{status:'healthy', version:'19.0.1.0.0'}` |
| `/v1/external/info` | GET | public + @api_auth() | `api_info` | Retourne le nom et toutes les permissions de la clé API |

---

### 3.14 `controllers/reference.py`

**Classe :** `ReferenceController(http.Controller)`

| Route | Méthode | Permission | Fonction | Description |
|---|---|---|---|---|
| `/api/v1/spaces/<space_id>/image` | GET | public | `get_space_image` | Image de l'espace en binaire (base64 decode) |
| `/v1/external/membership-types` | GET | read_members | `list_membership_types` | Liste tous les types d'adhésion actifs |
| `/v1/external/membership-types/<type_id>` | GET | read_members | `get_membership_type` | Cherche par `x_uuid` |
| `/v1/external/reference/spaces` | GET | read_spaces | `list_spaces` | Filtre optionnel `?type=CODE`. Appelle `_fresh_env()`. |
| `/v1/external/reference/spaces/<space_id>` | GET | read_spaces | `get_space` | Cherche par `x_tr_space_uuid` |
| `/v1/external/reference/spaces/<space_id>/availability` | GET | read_spaces | `check_space_availability` | Params `startTime`, `endTime`. Appelle `space.check_availability()`. |
| `/v1/external/reservation-options` | GET | read_reservations | `list_reservation_options` | Filtre optionnel `?scope=SPACE` |
| `/v1/external/reservation-options/<option_id>` | GET | read_reservations | `get_reservation_option` | Cherche par `x_uuid` |
| `/v1/external/reference/menu-kinds` | GET | read_menu | `list_menu_kinds` | Liste tous les menu kinds actifs |
| `/v1/external/reference/menu-kinds/<kind_id>` | GET | read_menu | `get_menu_kind` | Cherche par `x_uuid` |
| `/v1/external/reference/menu-kinds/<kind_id>/categories` | GET | read_menu | `get_kind_categories` | Catégories enfants d'un kind |
| `/v1/external/reference/menu-categories` | GET | read_menu | `list_menu_categories` | Toutes les catégories POS avec UUID |
| `/v1/external/reference/menu-items` | GET | read_menu | `list_menu_items` | Produits disponibles dans POS (`available_in_pos=True`) |
| `/v1/external/reference/menu-items/<item_id>` | GET | read_menu | `get_menu_item` | Cherche par ID entier |
| `/v1/external/reference/members` | GET | read_members | `list_members` | Paginé, filtre `?search=` sur nom/email/téléphone |
| `/v1/external/reference/members` | POST | write_members | `create_member` | Appelle `create_member_from_api(data)` |
| `/v1/external/reference/members/<member_id>` | GET | read_members | `get_member` | Cherche par `x_tr_uuid` ou ID entier |
| `/v1/external/reference/members/<member_id>` | PUT | write_members | `update_member` | Met à jour les champs modifiables |
| `/v1/external/subscription-plans` | GET | read_subscriptions | `list_subscription_plans` | Produits `x_tr_is_subscription_plan=True` |
| `/v1/external/subscription-plans/<plan_id>` | GET | read_subscriptions | `get_subscription_plan` | Cherche par `x_tr_space_uuid` |

**Méthode interne `_fresh_env()` :** Force `cr.execute('SELECT 1')` (sync DB) + retourne `env` avec `lang='fr_FR'`.

---

### 3.15 `controllers/reservations.py`

**Classe :** `ReservationsController(http.Controller)`

| Route | Méthode | Permission | Fonction | Description |
|---|---|---|---|---|
| `/v1/external/reservations` | GET | read_reservations | `list_reservations` | Paginé, filtres: `memberId`, `spaceId`, `status` |
| `/v1/external/reservations/<id>` | GET | read_reservations | `get_reservation` | Cherche par UUID ou ID entier |
| `/v1/external/reservations` | POST | write_reservations | `create_reservation` | Vérifie disponibilité (→ 409 si conflit) puis `create_reservation_from_api()` |
| `/v1/external/reservations/<id>` | PUT | write_reservations | `update_reservation` | Modifiable seulement si PENDING. Champs: startTime, endTime, guestCount, notes |
| `/v1/external/reservations/<id>` | DELETE | write_reservations | `delete_reservation` | Alias de `cancel_reservation` |
| `/v1/external/reservations/<id>/cancel` | POST | write_reservations | `cancel_reservation` | Appelle `action_cancel_reservation()` |
| `/v1/external/reservations/<id>/approve` | POST | write_reservations | `approve_reservation` | Appelle `action_approve_reservation()` |
| `/v1/external/reservations/<id>/reject` | POST | write_reservations | `reject_reservation` | `reason` depuis kwargs, appelle `action_reject_reservation(reason)` |
| `/v1/external/reservations/<id>/check-in` | POST | write_reservations | `checkin_reservation` | Appelle `action_checkin_reservation()` |
| `/v1/external/reservations/<id>/options` | PATCH | write_reservations | `add_reservation_option` | Cherche par `x_uuid` ou `code`. Si existant → update qty. Sinon crée. |
| `/v1/external/reservations/<id>/options/<opt_id>` | DELETE | write_reservations | `remove_reservation_option` | Cherche par `x_uuid`, `code` ou `id` entier |
| `/v1/external/reservations/<id>/invitees` | PATCH | write_reservations | `add_reservation_invitee` | Crée invité (`fullName` ou `name`, email, phone) |
| `/v1/external/reservations/<id>/invitees/<inv_id>` | DELETE | write_reservations | `remove_reservation_invitee` | Cherche par `x_uuid` ou id entier |
| `/v1/external/members/<id>/reservations` | GET | read_reservations | `get_member_reservations` | Redirige vers `list_reservations` avec `memberId` |

---

### 3.16 `controllers/orders.py`

**Classe :** `OrdersController(http.Controller)`

**Méthode interne :**
```python
def _get_pos_order(self, order_id) → pos.order | None:
    # Cherche dans x_tr_uuid OU id (si numérique)
    # domain: x_tr_is_mobile_order=True
```

| Route | Méthode | Permission | Fonction | Description |
|---|---|---|---|---|
| `/v1/external/orders` | GET | read_orders | `list_orders` | Paginé, filtres: `memberId`, `mode` |
| `/v1/external/orders/<id>` | GET | read_orders | `get_order` | Via `_get_pos_order()` |
| `/v1/external/orders` | POST | write_orders | `create_order` | `pos.order.create_order_from_api(data)` |
| `/v1/external/orders/<id>` | PUT | write_orders | `update_order` | Seulement si `state='draft'`. Champs: deliveryAddress, notes, mode, items (recrée les lignes). |
| `/v1/external/orders/<id>/confirm` | POST | write_orders | `confirm_order` | `action_confirm_order()` |
| `/v1/external/orders/<id>/ready` | POST | write_orders | `ready_order` | `action_ready_order()` |
| `/v1/external/orders/<id>/complete` | POST | write_orders | `complete_order` | `action_complete_order()` |
| `/v1/external/orders/<id>/cancel` | POST | write_orders | `cancel_order` | `action_cancel_order(reason)` |
| `/v1/external/members/<id>/orders` | GET | read_orders | `get_member_orders` | Filtres: `memberId`, `mode` |

---

### 3.17 `controllers/subscriptions.py`

**Classe :** `SubscriptionsController(http.Controller)`

**Mapping status externe → Odoo `subscription_state` :**

| API externe | Odoo interne |
|---|---|
| `draft` | `1_draft` |
| `renewal` | `2_renewal` |
| `active` / `progress` | `3_progress` |
| `paused` | `4_paused` |
| `expired` | `5_expired` |
| `cancelled` | `6_closed` |
| `upsell` | `7_upsell` |

| Route | Méthode | Permission | Fonction | Description |
|---|---|---|---|---|
| `/v1/external/subscriptions` | GET | read_subscriptions | `list_subscriptions` | Paginé, filtres: `memberId`, `status`, `planId` |
| `/v1/external/subscriptions/<id>` | GET | read_subscriptions | `get_subscription` | Cherche par UUID ou id |
| `/v1/external/subscriptions` | POST | write_subscriptions | `create_subscription` | Requiert `memberId` |
| `/v1/external/subscriptions/<id>/pause` | POST | write_subscriptions | `pause_subscription` | `action_pause_subscription()` ou write direct |
| `/v1/external/subscriptions/<id>/resume` | POST | write_subscriptions | `resume_subscription` | `action_resume_subscription()` ou write direct |
| `/v1/external/subscriptions/<id>/cancel` | POST | write_subscriptions | `cancel_subscription` | `action_cancel_subscription()` ou `set_close()` ou write direct |
| `/v1/external/members/<id>/subscriptions` | GET | read_subscriptions | `get_member_subscriptions` | Redirige vers `list_subscriptions` avec `memberId` |

---

### 3.18 `controllers/webhooks.py`

**Classe :** `WebhooksController(http.Controller)`

| Route | Méthode | Permission | Fonction | Description |
|---|---|---|---|---|
| `/v1/external/webhooks` | GET | manage_webhooks | `list_webhooks` | Retourne id, name, url, isActive, eventTypes (codes) |
| `/v1/external/webhooks/<id>` | GET | manage_webhooks | `get_webhook` | Cherche par ID entier |
| `/v1/external/webhooks` | POST | manage_webhooks | `create_webhook` | Crée avec event_type_ids résolu par codes |
| `/v1/external/webhooks/<id>` | PUT | manage_webhooks | `update_webhook` | Met à jour les champs présents dans le body |
| `/v1/external/webhooks/<id>` | DELETE | manage_webhooks | `delete_webhook` | `webhook.unlink()` |
| `/v1/external/webhooks/<id>/events` | GET | manage_webhooks | `list_webhook_events` | Paginé, trié par `create_date desc` |
| `/v1/external/webhooks/<id>/test` | POST | manage_webhooks | `test_webhook` | Envoie `TEST_EVENT` avec `{'message': 'This is a test webhook event'}` |

---

### 3.19 `static/src/js/ReservationScreen.js`

**Composant OWL :** `ReservationPanel`
**Template :** `theresidence_api.ReservationPanel`
**Props :** `{ onClose: Function }`

**État (`useState`) :**

| Propriété | Type | Valeur initiale | Description |
|---|---|---|---|
| `reservations` | Array | `[]` | Liste des réservations chargées |
| `loading` | Boolean | `true` | Affiche le spinner |
| `filter` | String | `"ALL"` | Filtre actif sur le statut |
| `dateFilter` | String | `"today"` | Filtre date: `today` ou `all` |
| `actionLoading` | String\|null | `null` | UUID de l'action en cours |

**Méthodes :**

| Méthode | Async | Description |
|---|---|---|
| `setup` | — | Injecte `orm`, `notification`. Monte avec `onMounted → loadReservations()` |
| `setDateFilter(df)` | oui | Modifie `dateFilter` → recharge |
| `loadReservations` | oui | ORM call `sale.order.get_pos_reservations([dateFilter])`. Gère erreur via `notification.add` |
| `filteredReservations` (getter) | — | Retourne `state.reservations` filtrés par `state.filter` |
| `setFilter(filter)` | — | Modifie `state.filter` |
| `statusLabel(status)` | — | Dict `{PENDING:'En attente', RESERVED:'Réservée', ARRIVED:'Arrivée', CANCELLED:'Annulée', COMPLETED:'Libéré'}` |
| `formatTime(isoString)` | — | `toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'})` |
| `formatDate(isoString)` | — | `toLocaleDateString('fr-FR', {day:'2-digit', month:'short'}) + ' · '` |
| `reserveReservation(uuid)` | oui | ORM `sale.order.pos_reserve_reservation` → notif success → reload |
| `arriveReservation(uuid)` | oui | ORM `sale.order.pos_arrive_reservation` → notif success → reload |
| `releaseReservation(uuid)` | oui | ORM `sale.order.pos_release_reservation` → notif success → reload |
| `cancelReservation(uuid)` | oui | ORM `sale.order.pos_cancel_reservation` → notif warning → reload |

---

### 3.20 `static/src/js/ReservationButton.js`

**Patch sur :** `Chrome` (composant racine POS, `@point_of_sale/app/pos_app`)

**État ajouté :** `trState = useState({ showReservations: false })`

**Méthodes ajoutées au prototype :**

| Méthode | Description |
|---|---|
| `openReservationScreen()` | `trState.showReservations = true` |
| `closeReservationScreen()` | `trState.showReservations = false` |

**Composant ajouté :** `ReservationPanel` dans `Chrome.components`

---

### 3.21 `security/ir.model.access.csv`

| Identifiant accès | Modèle | Groupe | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_theresidence_api_key` | `theresidence.api.key` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_theresidence_webhook` | `theresidence.webhook` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_theresidence_webhook_event_type` | `theresidence.webhook.event.type` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_theresidence_webhook_event` | `theresidence.webhook.event` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_theresidence_membership_type` | `theresidence.membership.type` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_theresidence_membership_type_admin` | `theresidence.membership.type` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_theresidence_space_type` | `theresidence.space.type` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_theresidence_space_type_admin` | `theresidence.space.type` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_theresidence_reservation_option_def` | `theresidence.reservation.option.def` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_theresidence_reservation_option_def_admin` | `theresidence.reservation.option.def` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_theresidence_menu_kind` | `theresidence.menu.kind` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_theresidence_menu_kind_admin` | `theresidence.menu.kind` | `base.group_system` | 1 | 1 | 1 | 1 |
| `access_theresidence_reservation_invitee` | `theresidence.reservation.invitee` | `base.group_user` | 1 | 1 | 1 | 1 |
| `access_theresidence_reservation_option` | `theresidence.reservation.option` | `base.group_user` | 1 | 1 | 1 | 1 |
| `access_mobile_order` | `mobile.order` | `point_of_sale.group_pos_manager` | 1 | 1 | 1 | 1 |
| `access_mobile_order_line` | `mobile.order.line` | `point_of_sale.group_pos_manager` | 1 | 1 | 1 | 1 |
| `access_wizard_reject` | `mobile.order.reject.wizard` | `point_of_sale.group_pos_manager` | 1 | 1 | 1 | 0 |

---

## 4. Module theresidence_appointment_bridge

### 4.1 `__manifest__.py`

```
Nom     : The Residence — Appointment Bridge
Version : 19.0.1
Dépend  : theresidence_api, appointment, pos_appointment
Hook    : post_init_hook
```

**Assets POS (`point_of_sale._assets_pos`) :**
- `static/src/js/pos_reservation_notify.js`
- `static/src/js/gantt_popover_patch.js`
- `static/src/js/appointment_list_patch.js`
- `static/src/css/appointment_list.css`
- `static/src/sounds/new_reservation.wav`

---

### 4.2 `models/sale_order.py` (bridge)

**Héritage :** `sale.order`

**Champs ajoutés :**

| Champ | Type | Attributs | Description |
|---|---|---|---|
| `x_tr_calendar_event_id` | Many2one → `calendar.event` | copy=False, readonly | Événement miroir POS |
| `x_tr_pos_order_id` | Many2one → `pos.order` | copy=False, readonly | Commande POS chargée |

**Constantes de mapping :**
```python
STATUS_TO_SHOW = {'PENDING':'free', 'RESERVED':'busy', 'ARRIVED':'busy', 'COMPLETED':'free', 'CANCELLED':'free'}
STATUS_TO_ACTIVE = {'PENDING':True, 'RESERVED':True, 'ARRIVED':True, 'COMPLETED':False, 'CANCELLED':False}
```

| Méthode | Décorateur | Description |
|---|---|---|
| `create` | `@api.model_create_multi` | Pour chaque réservation TR avec start/end → crée `calendar.event` (savepoint) + notifie POS (savepoint) |
| `write` | — | Si champs `{x_tr_reservation_status, x_tr_start_time, x_tr_end_time, x_tr_notes, x_tr_guest_count}` modifiés → sync calendar. Ignore si `tr_skip_calendar_sync` en contexte. |
| `get_pos_reservations` | `@api.model` | Override : appelle `super()` puis trie par `createdAt` décroissant |
| `get_new_pending_reservations` | `@api.model` | `(since_iso) → list[dict]` Retourne les PENDING créées après la date, avec uuid, member, space, start |
| `_notify_pos_new_reservation` | — | Envoie sur `bus.bus` canal `'tr_reservation_notifications'` type `'tr_new_reservation'` |
| `_sync_create_calendar_event` | — | Cherche/crée `appointment.type` partagé → crée `calendar.event` avec show_as, active, partner, description |
| `_sync_update_calendar_event` | — | Met à jour l'événement existant avec `tr_skip_calendar_sync=True` |
| `_lines_match_pos_order` | — | `(pos_order) → bool` Compare les sets `(product_id, qty, price_unit)` |
| `_do_load_to_pos` | — | Auto-confirme → cherche session → vérifie doublon → crée/met à jour `pos.order` avec toutes les lignes et taxes |
| `pos_load_reservation_to_pos` | `@api.model` | `(calendar_event_id)` Cherche sale.order par event → appelle `_do_load_to_pos()` |
| `action_load_to_pos` | — | Bouton form sale.order → `_do_load_to_pos()` + notification UI |
| `pos_action_from_calendar_event` | `@api.model` | `(calendar_event_id, action)` Router pour actions `reserve`, `arrive`, `release`, `cancel` depuis le popover Gantt |
| `_build_event_name` | — | Retourne `"NomEspace — NomMembre"` |
| `_build_event_description` | — | Construit la description avec invités, options, notes |

---

### 4.3 `models/calendar_event.py` (bridge)

**Héritage :** `calendar.event`

**Constante :**
```python
APT_STATUS_TO_TR = {'booked':'RESERVED', 'attended':'ARRIVED', 'no_show':'CANCELLED', 'cancelled':'CANCELLED'}
```

| Champ | Type | Attributs |
|---|---|---|
| `x_tr_reservation_status` | Char | compute, store=False |

| Méthode | Description |
|---|---|
| `_compute_tr_reservation_status` | Cherche la `sale.order` liée par `x_tr_calendar_event_id` → lit `x_tr_reservation_status` |
| `write` | Détecte `appointment_status` ou `active=False`. Cherche `sale.order` liée. Mappe via `APT_STATUS_TO_TR`. Écrit avec `tr_skip_calendar_sync=True`. Ignore si `tr_skip_calendar_sync` en contexte. |
| `_get_tr_order` | `() → sale.order` Cherche par `x_tr_calendar_event_id = self.id` |
| `action_tr_reserve` | `_get_tr_order()` → `action_reserve_reservation()` |
| `action_tr_arrive` | `_get_tr_order()` → `action_arrive_reservation()` |
| `action_tr_release` | `_get_tr_order()` → `action_release_reservation()` |
| `action_tr_cancel` | `_get_tr_order()` → `action_cancel_reservation()` |
| `action_tr_load_to_pos` | `_get_tr_order()` → `action_load_to_pos()` |

---

### 4.4 `models/product_template.py` (bridge)

**Héritage :** `product.template`

| Champ | Type | Attributs |
|---|---|---|
| `x_tr_appointment_type_id` | Many2one → `appointment.type` | copy=False |

| Méthode | Décorateur | Description |
|---|---|---|
| `create` | `@api.model_create_multi` | Si `x_tr_is_space=True` → `_ensure_appointment_type()` |
| `write` | — | Si `x_tr_is_space` modifié → `_ensure_appointment_type()` si pas déjà défini |
| `_ensure_appointment_type` | — | 1. Cherche type catégorie `'table'` → 2. Cherche par nom `"Réservation de table"` → 3. Crée si absent. Ajoute admin comme staff. Appelle `_link_apt_type_to_pos()`. |
| `_link_apt_type_to_pos` | — | Cherche le champ de liaison (`appointment_type_ids` ou `appointment_ids` sur `pos.config`, ou `pos_config_ids`/`pos_config_id` sur `appointment.type`). Tente les 2 variantes pour compatibilité Odoo 17+. |

---

### 4.5 `models/reservation_invitee.py` (bridge)

**Héritage :** `theresidence.reservation.invitee`

| Méthode | Description |
|---|---|
| `_tr_refresh_calendar_event_description` | Pour chaque réservation avec calendar.event lié → `_sync_update_calendar_event()` (silencieux) |
| `write` | super() → `_tr_refresh_calendar_event_description()` |
| `create` | super() → `_tr_refresh_calendar_event_description()` |
| `unlink` | Capture les réservations avant suppression → super() → refresh calendar.event des réservations |

---

### 4.6 `models/reservation_option.py` (bridge)

**Héritage :** `theresidence.reservation.option`

Identique à `reservation_invitee.py` — même 4 méthodes, même comportement de refresh calendar.

---

### 4.7 `models/pos_order.py` (bridge)

**Héritage :** `pos.order`

| Méthode | Décorateur | Description |
|---|---|---|
| `write` | — | Si `state` ∈ `{paid, done}` → appelle `_cancel_reservation_picking()` pour chaque commande |
| `_cancel_reservation_picking` | — | `(pos_order)` Cherche `sale.order` avec `x_tr_pos_order_id = pos_order.id`. Annule ses `stock.picking` encore ouverts (`action_cancel()`). Journalise. |

**Objectif :** Éviter la double sortie de stock (POS valide ses propres mouvements → picking sale.order devient redondant).

---

### 4.8 `static/src/js/pos_reservation_notify.js`

**Polling :** toutes les **10 000 ms** (10 secondes)

**Variables globales :**
- `lastPollTime` : ISO string de la dernière vérification
- `pollInterval` : ID du setInterval

**Fonctions :**

| Fonction | Description |
|---|---|
| `playNotificationSound()` | Essaie de jouer `new_reservation.wav`. Fallback : génère bip Web Audio (oscillateur sine, fréquence 880→1100 Hz via `linearRampToValueAtTime`, durée 450ms) |
| `showNotification(title, body)` | Affiche un toast Odoo via `owl.__bus__` ou `console.log` si unavailable |
| `pollNewReservations()` | ORM call `sale.order.get_new_pending_reservations([lastPollTime])`. Pour chaque résultat → `showNotification` + `playNotificationSound`. |
| `pollNewOrders()` | ORM call `pos.order.get_new_pending_orders([lastPollTime])`. Même comportement. |
| `startPolling()` | `setInterval` toutes les 10s. Appelle les 2 fonctions poll. Met à jour `lastPollTime`. |

---

### 4.9 `static/src/js/gantt_popover_patch.js`

**Patch sur :** `POSAppointmentBookingGanttRenderer` (`pos_appointment/static/src/gantt/...`)

**Objectif :** Enrichir le popover Gantt avec le statut TR de la réservation.

**Fonction patchée :** `getPopoverProps`

**Comportement :** Lors de l'ouverture du popover, effectue un appel ORM pour lire `x_tr_reservation_status` du `calendar.event` et l'ajoute aux props du popover.

---

### 4.10 `static/src/js/appointment_list_patch.js`

**Objectif :** Enrichir les cartes de la liste de réservations POS (vue kanban/liste).

**Variables globales :**
- `eventMap` : `Map<string, {start, stop}>` — cache des événements calendar indexés par nom
- `dataLoaded` : Boolean — flag one-shot

**Fonctions :**

| Fonction | Description |
|---|---|
| `loadEventData()` | RPC POST `/web/dataset/call_kw` → `calendar.event.search_read` avec filtre `appointment_type_id != False`. Fields: `name`, `start`, `stop`. Limite 500. Remplit `eventMap`. |
| `formatDate(isoStr)` | `toLocaleDateString('fr-FR', {day:'2-digit', month:'short', year:'numeric'})` |
| `formatTime(isoStr)` | `toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'})` |
| `enhanceElement(el)` | Si `data-tr-enhanced` → skip. Cherche `" — "` dans le texte. Split `[space, client]`. Cherche dans `eventMap` par nom complet. Reconstruit le HTML avec div `.tr-row` + labels `.tr-lbl` + valeurs `.tr-val`. Force styles overflow/height sur `el` et 4 parents. |
| `scanNode(root)` | `querySelectorAll('*')` → fix `text-overflow:ellipsis` + appelle `enhanceElement` sur les feuilles |
| `startObserver()` | Lance `MutationObserver` sur `document.body` (childList, subtree). Charge les données lazily au premier noeud ajouté. |

**Attribut DOM :** `data-tr-enhanced="1"` sur les éléments déjà traités (idempotent)

---

### 4.11 `static/src/css/appointment_list.css`

| Sélecteur | Propriétés clés |
|---|---|
| `.tr-row` | `display:flex; align-items:baseline; gap:5px; margin-top:2px; line-height:1.3` |
| `.tr-lbl` | `flex-shrink:0; font-size:10px !important; font-weight:700 !important; letter-spacing:0.4px; color:#aaa !important; text-transform:uppercase; white-space:nowrap` |
| `.tr-val` | `font-size:12px !important; font-weight:500 !important; color:#2c3e50 !important; word-break:break-word; white-space:normal !important; overflow:visible !important` |
| `[data-tr-enhanced]` | `white-space:normal !important; overflow:visible !important; text-overflow:unset !important; height:auto !important; min-height:0 !important` |

---

### 4.12 `security/ir.model.access.csv` (bridge)

| Identifiant | Modèle | Groupe | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_tr_apt_bridge_user` | `appointment.type` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_tr_apt_resource_user` | `appointment.resource` | `base.group_user` | 1 | 0 | 0 | 0 |

---

## 5. Module theresidence_kitchen_bridge

### 5.1 `models/pos_order.py` (kitchen)

**Héritage :** `pos.order`

| Méthode | Décorateur | Description |
|---|---|---|
| `sync_from_ui` | `@api.model` | Override. Si `context.get('preparation')` → pour chaque commande dans le payload, cherche `pos.order` mobile PENDING par `uuid`. Passe à CONFIRMED avec `tr_skip_order_sync=True`. Déclenche webhook `ORDER_STATUS_CHANGED`. Puis `super().sync_from_ui(orders)`. |

**Cas d'usage :** Quand le caissier envoie une commande mobile depuis le POS vers la cuisine, elle passe de PENDING à CONFIRMED avant la synchronisation.

---

### 5.2 `models/pos_prep_order.py` (kitchen)

**Héritage :** `pos.prep.order`

| Méthode | Décorateur | Description |
|---|---|---|
| `process_order` | `@api.model` | `(order_id, options={})` Override. Appelle `super()` d'abord. Si `options.get('cancelled')` → retourne. Sinon, si commande mobile PENDING → CONFIRMED + webhook `ORDER_STATUS_CHANGED`. |

**Cas d'usage :** Quand une commande est prise en charge par la cuisine (bouton "Traiter" dans l'écran cuisine).

---

### 5.3 `models/pos_prep_state.py` (kitchen)

**Héritage :** `pos.prep.state`

| Méthode | Description |
|---|---|
| `_tr_check_and_mark_ready(pos_orders)` | Helper commun. Pour chaque commande mobile CONFIRMED : cherche tous ses `pos.prep.order` → toutes leurs lignes → tous leurs états. Si tous `todo=False` → READY + webhook `ORDER_STATUS_CHANGED`. |
| `change_state_status(todos, prep_display_id)` | Override. `super()` → récupère les commandes POS liées → `_tr_check_and_mark_ready()`. |
| `change_state_stage(stages, prep_display_id)` | Override. `super()` → pour chaque commande mobile CONFIRMED : si tous les états au dernier stage (`is_stage_position(-1)`) → READY + webhook. |

**Logique de détection "prêt" :**
- **Cuisine simple (1 stage) :** Tous les `pos.prep.state.todo = False`
- **Cuisine multi-stages :** Tous les `pos.prep.state.stage_id.is_stage_position(-1)` (dernier stage)

---

## 6. Tableaux de référence rapide

### Tous les modèles custom

| Modèle Odoo | Fichier | Module | Type |
|---|---|---|---|
| `theresidence.api.key` | `models/api_key.py` | theresidence_api | Nouveau |
| `theresidence.webhook` | `models/webhook.py` | theresidence_api | Nouveau |
| `theresidence.webhook.event.type` | `models/webhook.py` | theresidence_api | Nouveau |
| `theresidence.webhook.event` | `models/webhook.py` | theresidence_api | Nouveau |
| `theresidence.membership.type` | `models/membership_type.py` | theresidence_api | Nouveau |
| `theresidence.space.type` | `models/membership_type.py` | theresidence_api | Nouveau |
| `theresidence.reservation.option.def` | `models/membership_type.py` | theresidence_api | Nouveau |
| `theresidence.menu.kind` | `models/membership_type.py` | theresidence_api | Nouveau |
| `res.partner` | `models/res_partner.py` | theresidence_api | Héritage |
| `product.template` | `models/product.py` | theresidence_api | Héritage |
| `product.product` | `models/product.py` | theresidence_api | Héritage |
| `pos.category` | `models/pos_category.py` | theresidence_api | Héritage |
| `sale.order` | `models/sale_order.py` | theresidence_api | Héritage |
| `sale.order.line` | `models/sale_order.py` | theresidence_api | Héritage |
| `pos.order` | `models/pos_order.py` | theresidence_api | Héritage |
| `pos.order.line` | `models/pos_order.py` | theresidence_api | Héritage |
| `pos.config` | `models/pos_session.py` | theresidence_api | Héritage |
| `mobile.order` | `models/mobileOrder.py` | theresidence_api | Nouveau |
| `mobile.order.line` | `models/mobileOrder.py` | theresidence_api | Nouveau |
| `mobile.order.reject.wizard` | `models/wizard_reject_order.py` | theresidence_api | Nouveau (TransientModel) |
| `sale.order` (bridge) | `models/sale_order.py` | theresidence_appointment_bridge | Héritage |
| `pos.order` (bridge) | `models/pos_order.py` | theresidence_appointment_bridge | Héritage |
| `calendar.event` | `models/calendar_event.py` | theresidence_appointment_bridge | Héritage |
| `product.template` (bridge) | `models/product_template.py` | theresidence_appointment_bridge | Héritage |
| `theresidence.reservation.invitee` | `models/reservation_invitee.py` | theresidence_appointment_bridge | Héritage |
| `theresidence.reservation.option` | `models/reservation_option.py` | theresidence_appointment_bridge | Héritage |
| `pos.order` (kitchen) | `models/pos_order.py` | theresidence_kitchen_bridge | Héritage |
| `pos.prep.order` | `models/pos_prep_order.py` | theresidence_kitchen_bridge | Héritage |
| `pos.prep.state` | `models/pos_prep_state.py` | theresidence_kitchen_bridge | Héritage |

### Tous les types d'événements webhook

| Code | Déclenché par | Méthode |
|---|---|---|
| `MEMBER_CREATED` | `res.partner.create()` | (commenté) |
| `MEMBER_UPDATED` | `res.partner.write()` | (commenté) |
| `MEMBER_DELETED` | `res.partner.unlink()` | (commenté) |
| `SPACE_CREATED` | `product.template.create()` | (commenté) |
| `SPACE_UPDATED` | `product.template.write()` | (commenté) |
| `SPACE_DELETED` | `product.template.unlink()` | (commenté) |
| `POS_CATEGORY_CREATED` | `pos.category.create()` | via `theresidence.webhook.service` |
| `POS_CATEGORY_UPDATED` | `pos.category.write()` | via `theresidence.webhook.service` |
| `POS_CATEGORY_DELETED` | `pos.category.unlink()` | via `theresidence.webhook.service` |
| `RESERVATION_CREATED` | `sale.order.create_reservation_from_api()` | `theresidence.webhook.trigger_event()` |
| `RESERVATION_STATUS_CHANGED` | `action_reserve/arrive/reject/release` | `theresidence.webhook.trigger_event()` |
| `RESERVATION_CANCELLED` | `action_cancel_reservation()` | `theresidence.webhook.trigger_event()` |
| `ORDER_CREATED` | `pos.order.create_order_from_api()` | `theresidence.webhook.trigger_event()` |
| `ORDER_STATUS_CHANGED` | `write(state)`, `action_confirm/ready/complete`, kitchen | `theresidence.webhook.trigger_event()` |
| `ORDER_CANCELLED` | `action_cancel_order()` | `theresidence.webhook.trigger_event()` |
| `SUBSCRIPTION_CREATED` | `create_subscription_from_api()` | `theresidence.webhook.trigger_event()` |
| `SUBSCRIPTION_STATUS_CHANGED` | `action_pause/resume_subscription()` | `theresidence.webhook.trigger_event()` |
| `SUBSCRIPTION_CANCELLED` | `action_cancel_subscription()` | `theresidence.webhook.trigger_event()` |

### Flags de contexte anti-boucle

| Flag | Où posé | Effet |
|---|---|---|
| `tr_skip_calendar_sync` | `sale_order.write()`, `calendar_event.write()` | Empêche la boucle de synchronisation sale.order ↔ calendar.event |
| `tr_skip_order_sync` | `pos.order.write()`, kitchen bridge | Empêche la boucle state Odoo ↔ x_tr_order_status |
| `skip_webhook` | `pos.category` | Ignore les webhooks lors de la sync initiale |

---

## 7. Guide de débogage

### Erreurs fréquentes

| Erreur | Cause | Fichier concerné | Solution |
|---|---|---|---|
| `null value in column "x_tr_order_status" violates not-null constraint` | POS normal envoie `null` via `sync_from_ui` | `models/pos_order.py` ligne 87 | `create()` appelle `vals.pop('x_tr_order_status', None)` pour les non-mobiles ✅ corrigé |
| `AttributeError: 'sale.order.line' object has no attribute 'product_uom'` | Odoo 19 utilise `product_uom_id` pas `product_uom` | `theresidence_appointment_bridge/models/sale_order.py` | Toujours utiliser `product_uom_id` ✅ corrigé |
| `KeyError: 'translated_product_name'` | Champ référencé dans une vue POS mais absent | `models/pos_order.py` | Ajouté comme computed field sur `pos.order.line` ✅ corrigé |
| `ValidationError: Espace 'X' non disponible` | Double réservation bloquée | `models/sale_order.py` contrainte `_check_no_double_booking` | Comportement normal |
| Assets JS non mis à jour | Bundle non régénéré | n/a | Ajouter `?debug=assets` dans l'URL |
| Bouton absent dans le POS | Module non mis à jour | views/*.xml | `-u theresidence_appointment_bridge` |
| Webhook FAILED | URL inaccessible / timeout 30s | `models/webhook.py` | Vérifier URL dans menu Webhooks → onglet Événements |

### Commandes de debug (shell Odoo)

```python
# Accéder au shell Odoo
./odoo-bin shell -c odoo.conf

# Vérifier les réservations actives d'un espace
env['sale.order'].search([
    ('x_tr_space_id.name', 'ilike', 'Salle'),
    ('x_tr_reservation_status', 'in', ['PENDING', 'RESERVED', 'ARRIVED']),
])

# Forcer la création d'un calendar.event manquant
order = env['sale.order'].browse(42)
order.sudo()._sync_create_calendar_event()

# Vérifier le statut d'un espace
space = env['product.template'].search([('x_tr_is_space', '=', True), ('name', 'ilike', 'Salle A')], limit=1)
print(space.x_tr_space_status, space.x_tr_is_occupied)

# Tester un webhook manuellement
env['theresidence.webhook'].trigger_event(
    'RESERVATION_CREATED', 'reservation', 'test-uuid',
    {'id': 'test-uuid'}, None, 'PENDING'
)

# Voir les sessions POS ouvertes
env['pos.session'].search([('state', '=', 'opened')])

# Voir les commandes mobiles en attente
env['pos.order'].search([('x_tr_is_mobile_order', '=', True), ('x_tr_order_status', '=', 'PENDING')])
```

### Logs à surveiller

```bash
grep "TR BRIDGE" /var/log/odoo/odoo.log     # sync calendar, notifications, pickings
grep "TR KITCHEN" /var/log/odoo/odoo.log    # statuts cuisine
grep "TR API" /var/log/odoo/odoo.log        # création abonnements
grep "v1/external" /var/log/odoo/odoo.log   # accès API REST
```

---

## 8. Guide d'ajout de fonctionnalités

### Ajouter un champ sur une entité existante

1. `models/[modele].py` → ajouter le champ `x_tr_*`
2. `views/[modele]_views.xml` → ajouter dans la vue form héritée
3. `to_*_api_dict()` → ajouter la clé camelCase correspondante
4. Contrôleur → accepter et mapper le champ dans PUT/POST si applicable
5. `-u theresidence_api`

### Ajouter un nouveau statut de réservation

1. `sale_order.py` → étendre `x_tr_reservation_status` Selection
2. Ajouter méthode `action_*_reservation()` avec validation + webhook
3. Ajouter méthode POS `pos_*_reservation(uuid)` appelable depuis le frontend
4. XML → ajouter bouton dans `sale_order_views.xml` et `bridge_views.xml`
5. `ReservationScreen.js` → ajouter méthode async + `statusLabel()`
6. `-u theresidence_api,theresidence_appointment_bridge`

### Ajouter une route API

```python
# Dans controllers/[nouveau].py
@http.route(f'{API_PREFIX}/ma-ressource', type='http', auth='public', methods=['GET'], csrf=False)
@api_auth('read_membres')
def ma_fonction(self, **kwargs):
    data = [...]
    return success_response(data)
    # ou: return paginated_response(items, total, page, size)
    # ou: return error_response("message", "CODE", 404)
```

Enregistrer dans `controllers/__init__.py` → `-u theresidence_api`

### Activer un webhook commenté

Les webhooks dans `res_partner.py` et `product.py` sont commentés. Pour les activer :

1. Décommenter le bloc `trigger_event` correspondant
2. Vérifier que le type d'événement existe dans `data/reference_data.xml`
3. Créer un webhook en UI qui souscrit à ce type
4. `-u theresidence_api`

### Mise à jour des modules

| Modification | Module(s) à mettre à jour |
|---|---|
| `theresidence_api/models/*.py` | `theresidence_api` |
| `theresidence_api/views/*.xml` | `theresidence_api` |
| `theresidence_api/controllers/*.py` | `theresidence_api` |
| `theresidence_api/static/src/js/*.js` | `theresidence_api` + `?debug=assets` |
| `theresidence_appointment_bridge/models/*.py` | `theresidence_appointment_bridge` |
| `theresidence_appointment_bridge/views/*.xml` | `theresidence_appointment_bridge` |
| `theresidence_appointment_bridge/static/src/js/*.js` | `theresidence_appointment_bridge` + `?debug=assets` |
| `theresidence_kitchen_bridge/models/*.py` | `theresidence_kitchen_bridge` |

```bash
# Mise à jour complète tous modules
./odoo-bin -c odoo.conf -u theresidence_api,theresidence_appointment_bridge,theresidence_kitchen_bridge --stop-after-init
```

---

*Documentation générée à partir du code source réel — The Residence CI — Neurones Technologies — 2026-03-22*
