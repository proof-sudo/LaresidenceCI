# Webhook Events Reference — The Residence (Odoo)

**Version :** 2.0
**Dernière mise à jour :** Mars 2026
**Source :** Module `webhook_manager` — Odoo 19

---

## Sommaire

1. [Configuration technique](#1-configuration-technique)
2. [Structure commune du payload](#2-structure-commune-du-payload)
3. [Membre (`member`)](#3-membre-respartner)
4. [Réservation (`reservation`)](#4-réservation-saleorder)
5. [Abonnement (`subscription`)](#5-abonnement-saleorder)
6. [Espace / Plan (`space`, `subscription_plan`, `product`)](#6-espace--plan-producttemplate)
7. [Commande POS (`order`)](#7-commande-pos-posorder)
8. [Catégorie POS (`pos_category`)](#8-catégorie-pos-poscategory)
9. [Gestion des valeurs](#9-gestion-des-valeurs)
10. [Réponse attendue](#10-réponse-attendue)

---

## 1. Configuration technique

| Paramètre | Valeur |
|-----------|--------|
| Méthode | `POST` |
| Content-Type | `application/json` |
| Authentification | Header `X-API-Key: <votre_clé>` |
| Timeout | 5 secondes (configurable) |
| Succès attendu | HTTP `202 Accepted` |

---

## 2. Structure commune du payload

Tous les webhooks partagent cette enveloppe JSON :

```json
{
  "event_type": "entity_type.action",
  "event_id": "evt_20260307_a1b2c3d4",
  "timestamp": "2026-03-07T10:00:00Z",
  "entity_type": "member",
  "entity_id": "456",
  "data": { }
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `event_type` | string | Format `entity.action` (ex: `member.active`) |
| `event_id` | string | ID unique de l'événement (préfixe `evt_`) |
| `timestamp` | string ISO 8601 | Date/heure UTC de l'envoi |
| `entity_type` | string | Type d'entité (voir tableau par section) |
| `entity_id` | string | ID Odoo numérique de l'enregistrement |
| `data` | object | Données de l'entité (voir sections ci-dessous) |

---

## 3. Membre (`res.partner`)

### Events déclenchés

| Action Odoo | `event_type` envoyé |
|-------------|---------------------|
| Création membre | `member.created` |
| Modification → statut `ACTIVE` | `member.active` |
| Modification → statut `PENDING` | `member.pending` |
| Modification → statut `SUSPENDED` | `member.suspended` |
| Modification → statut `INACTIVE` | `member.inactive` |
| Suppression | `member.deleted` |

> **Filtre :** seuls les contacts avec `x_tr_is_member = true` déclenchent un webhook.

### Payload `data`

```json
{
  "x_tr_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "x_tr_is_member": true,
  "x_tr_member_status": "ACTIVE",
  "x_tr_membership_type_id": 3,
  "x_tr_membership_type_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "x_tr_joined_at": "2026-01-15",
  "x_tr_qr_token": "member-xK9mL2nP4qR8sT6u",

  "name": "Jean Kouadio",
  "display_name": "Jean Kouadio",
  "email": "jean.kouadio@example.com",
  "phone": "+225 07 00 00 00 00",
  "mobile": false,
  "active": true,

  "image_url": "/web/image/res.partner/456/image_1920"
}
```

### Description des champs

| Champ | Type | Description |
|-------|------|-------------|
| `x_tr_uuid` | string UUID | Identifiant unique du membre (à utiliser comme clé primaire côté API) |
| `x_tr_is_member` | boolean | Toujours `true` dans ce contexte |
| `x_tr_member_status` | string | `ACTIVE`, `PENDING`, `SUSPENDED`, `INACTIVE` |
| `x_tr_membership_type_id` | integer | ID Odoo du type d'adhésion |
| `x_tr_membership_type_uuid` | string UUID | UUID du type d'adhésion (référence stable) |
| `x_tr_joined_at` | string ISO 8601 | Date d'adhésion |
| `x_tr_qr_token` | string | Token QR unique du membre |
| `name` | string | Nom complet |
| `email` | string | Email principal |
| `phone` / `mobile` | string ou `false` | Numéros de téléphone |
| `active` | boolean | `false` si archivé dans Odoo |
| `image_url` | string | URL relative de la photo *(présent uniquement à la création ou si l'image a été modifiée)* |

---

## 4. Réservation (`sale.order`)

### Events déclenchés

| Action Odoo | `event_type` envoyé |
|-------------|---------------------|
| Création | `reservation.created` |
| Statut → `PENDING` | `reservation.pending` |
| Statut → `APPROVED` | `reservation.approved` |
| Statut → `REJECTED` | `reservation.rejected` |
| Statut → `CHECKED_IN` | `reservation.checked_in` |
| Statut → `COMPLETED` | `reservation.completed` |
| Statut → `CANCELLED` | `reservation.cancelled` |
| Suppression | `reservation.deleted` |

### Payload `data`

```json
{
  "x_tr_uuid": "c2d3e4f5-a6b7-8901-bcde-f12345678901",
  "x_tr_is_reservation": true,
  "x_tr_reservation_status": "APPROVED",
  "x_tr_space_id": 890,
  "x_tr_space_uuid": "d4e5f6a7-b8c9-0123-cdef-123456789012",
  "x_tr_start_time": "2026-03-10T09:00:00",
  "x_tr_end_time": "2026-03-10T12:00:00",
  "x_tr_guest_count": 6,
  "x_tr_notes": "Réunion de direction",
  "x_tr_rejection_reason": false,
  "x_tr_qr_token": "res-4f8a2b1c3d5e",
  "x_tr_invitee_ids": [12, 13, 14],
  "x_tr_option_ids": [5, 6],

  "x_tr_member_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",

  "name": "S00042",
  "active": true
}
```

### Description des champs

| Champ | Type | Description |
|-------|------|-------------|
| `x_tr_uuid` | string UUID | Identifiant unique de la réservation |
| `x_tr_is_reservation` | boolean | Toujours `true` |
| `x_tr_reservation_status` | string | `PENDING`, `APPROVED`, `REJECTED`, `CHECKED_IN`, `COMPLETED`, `CANCELLED` |
| `x_tr_space_id` | integer | ID Odoo de l'espace réservé |
| `x_tr_space_uuid` | string UUID | UUID de l'espace réservé (référence stable) |
| `x_tr_start_time` | string ISO 8601 | Début de la réservation |
| `x_tr_end_time` | string ISO 8601 | Fin de la réservation |
| `x_tr_guest_count` | integer | Nombre d'invités |
| `x_tr_notes` | string ou `false` | Notes du client |
| `x_tr_rejection_reason` | string ou `false` | Raison du rejet (si `REJECTED`) |
| `x_tr_qr_token` | string | Token QR de la réservation |
| `x_tr_invitee_ids` | array[integer] | IDs Odoo des invités |
| `x_tr_option_ids` | array[integer] | IDs Odoo des options choisies |
| `x_tr_member_uuid` | string UUID | UUID du membre qui réserve |

---

## 5. Abonnement (`sale.order`)

### Events déclenchés

| Action Odoo | `event_type` envoyé |
|-------------|---------------------|
| Création | `subscription.created` |
| Statut → `ACTIVE` | `subscription.active` |
| Statut → `PAUSED` | `subscription.paused` |
| Statut → `CANCELLED` | `subscription.cancelled` |
| Statut → `EXPIRED` | `subscription.expired` |
| Suppression | `subscription.deleted` |

### Payload `data`

```json
{
  "x_tr_uuid": "e5f6a7b8-c9d0-1234-defa-234567890123",
  "x_tr_is_subscription": true,
  "x_tr_subscription_status": "ACTIVE",
  "x_tr_plan_id": 901,
  "x_tr_plan_uuid": "b8c9d0e1-f2a3-4567-bcde-345678901234",
  "x_tr_billing_period": "MONTHLY",
  "x_tr_auto_renew": true,
  "x_tr_sub_start_date": "2026-03-01",
  "x_tr_sub_end_date": "2027-03-01",

  "x_tr_member_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",

  "name": "S00043",
  "active": true
}
```

### Description des champs

| Champ | Type | Description |
|-------|------|-------------|
| `x_tr_uuid` | string UUID | Identifiant unique de l'abonnement |
| `x_tr_is_subscription` | boolean | Toujours `true` |
| `x_tr_subscription_status` | string | `ACTIVE`, `PAUSED`, `CANCELLED`, `EXPIRED` |
| `x_tr_plan_id` | integer | ID Odoo du plan d'abonnement |
| `x_tr_plan_uuid` | string UUID | UUID du plan d'abonnement (référence stable) |
| `x_tr_billing_period` | string | `MONTHLY`, `QUARTERLY`, `YEARLY` |
| `x_tr_auto_renew` | boolean | Renouvellement automatique activé |
| `x_tr_sub_start_date` | string ISO 8601 | Date de début |
| `x_tr_sub_end_date` | string ISO 8601 | Date de fin |
| `x_tr_member_uuid` | string UUID | UUID du membre abonné |

---

## 6. Espace / Plan (`product.template`)

Le `entity_type` dépend du type de produit :

| Condition | `entity_type` |
|-----------|---------------|
| `x_tr_is_space = true` | `space` |
| `x_tr_is_subscription_plan = true` | `subscription_plan` |
| Aucun des deux | `product` |

### Events déclenchés

| Action Odoo | `event_type` envoyé |
|-------------|---------------------|
| Création | `space.created` / `product.created` / `subscription_plan.created` |
| Modification | `space.updated` / `product.updated` / `subscription_plan.updated` |
| Suppression | `space.deleted` / etc. |

### Payload `data` — Espace

```json
{
  "x_tr_is_space": true,
  "x_tr_space_uuid": "d4e5f6a7-b8c9-0123-cdef-123456789012",
  "x_tr_space_capacity": 8,
  "x_tr_space_type_id": 2,
  "x_tr_space_description": "Grande salle avec vue",
  "x_tr_is_occupied": false,
  "x_tr_is_subscription_plan": false,
  "x_tr_membership_type_id": false,
  "x_tr_duration_months": 1,

  "name": "Salle Cocody",
  "display_name": "Salle Cocody",
  "list_price": 75000.0,
  "available_in_pos": true,
  "barcode": false,
  "default_code": false,
  "active": true,

  "image_url": "/web/image/product.template/890/image_1920"
}
```

### Payload `data` — Plan d'abonnement

```json
{
  "x_tr_is_space": false,
  "x_tr_space_uuid": false,
  "x_tr_is_subscription_plan": true,
  "x_tr_membership_type_id": 3,
  "x_tr_duration_months": 12,

  "name": "Abonnement Annuel CEO",
  "list_price": 1200000.0,
  "active": true
}
```

### Description des champs

| Champ | Type | Description |
|-------|------|-------------|
| `x_tr_is_space` | boolean | `true` si c'est un espace réservable |
| `x_tr_space_uuid` | string UUID | UUID de l'espace (identifiant stable côté API) |
| `x_tr_space_capacity` | integer | Capacité maximale (personnes) |
| `x_tr_space_type_id` | integer | ID Odoo du type d'espace |
| `x_tr_space_description` | string ou `false` | Description de l'espace |
| `x_tr_is_occupied` | boolean | Espace actuellement occupé |
| `x_tr_is_subscription_plan` | boolean | `true` si c'est un plan d'abonnement |
| `x_tr_membership_type_id` | integer ou `false` | ID Odoo du type d'adhésion lié (pour les plans) |
| `x_tr_duration_months` | integer | Durée du plan en mois |
| `list_price` | float | Prix de vente (XOF) |
| `available_in_pos` | boolean | Disponible dans le point de vente |
| `image_url` | string | URL relative de l'image *(présent uniquement si image créée/modifiée)* |

---

## 7. Commande POS (`pos.order`)

### Events déclenchés

| Action Odoo | `event_type` envoyé |
|-------------|---------------------|
| Création | `order.created` |
| Modification | `order.updated` |
| Suppression | `order.deleted` |

### Payload `data`

```json
{
  "x_tr_uuid": "a9b0c1d2-e3f4-5678-abcd-456789012345",
  "x_tr_is_mobile_order": true,
  "x_tr_order_status": "CONFIRMED",
  "x_tr_order_mode": "DINE_IN",
  "x_tr_delivery_address": false,
  "x_tr_qr_token": "order-7f3b2a1c4d5e",
  "x_tr_member_id": 456,
  "x_tr_member_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",

  "name": "Order 00001-001-0042",
  "active": true
}
```

### Description des champs

| Champ | Type | Description |
|-------|------|-------------|
| `x_tr_uuid` | string UUID | UUID de la commande *(uniquement pour les commandes mobiles)* |
| `x_tr_is_mobile_order` | boolean | `true` si commande passée via mobile |
| `x_tr_order_status` | string | `PENDING`, `CONFIRMED`, `SENT_TO_POS`, `REJECTED`, `PAID`, `COMPLETED` |
| `x_tr_order_mode` | string | `PICKUP`, `DELIVERY`, `DINE_IN` |
| `x_tr_delivery_address` | string ou `false` | Adresse de livraison |
| `x_tr_qr_token` | string | Token QR de la commande |
| `x_tr_member_id` | integer | ID Odoo du membre |
| `x_tr_member_uuid` | string UUID | UUID du membre *(présent si membre associé)* |

---

## 8. Catégorie POS (`pos.category`)

### Events déclenchés

| Action Odoo | `event_type` envoyé |
|-------------|---------------------|
| Création | `pos_category.created` |
| Modification | `pos_category.updated` |
| Suppression | `pos_category.deleted` |

### Payload `data`

```json
{
  "x_tr_uuid": "b0c1d2e3-f4a5-6789-bcde-567890123456",
  "x_tr_menu_kind_id": 2,
  "x_tr_parent_uuid": "c1d2e3f4-a5b6-7890-cdef-678901234567",

  "name": "Boissons Chaudes",
  "active": true,

  "image_url": "/web/image/pos.category/12/image_1920"
}
```

### Description des champs

| Champ | Type | Description |
|-------|------|-------------|
| `x_tr_uuid` | string UUID | UUID de la catégorie |
| `x_tr_menu_kind_id` | integer ou `false` | ID Odoo du type de menu (petit-déj., déjeuner, etc.) |
| `x_tr_parent_uuid` | string UUID ou absent | UUID de la catégorie parente *(présent uniquement si la catégorie a un parent)* |
| `name` | string | Nom de la catégorie |
| `active` | boolean | `false` si archivée |
| `image_url` | string | URL relative de l'image *(présent uniquement si image créée/modifiée)* |

---

## 9. Gestion des valeurs

### Conventions Odoo

| Valeur reçue | Signification |
|-------------|---------------|
| `false` | Champ vide, relation non définie, ou booléen `false` |
| `0` | Valeur numérique zéro |
| `[]` | Relation vide (One2many) |

> Traiter `false` comme `null` dans votre logique métier.

### Champ `image_url`

- **Présent** uniquement si l'image a été créée ou modifiée lors de l'événement
- **Absent** si seules d'autres données ont changé
- Format : `/web/image/{model}/{id}/image_1920`
- Pour récupérer l'image : `GET https://odoo.laresidence-abidjan.com{image_url}`

### Relations Many2one

Les champs Many2one (ex: `x_tr_space_id`, `x_tr_member_id`) retournent l'**ID Odoo entier**.
Les UUID correspondants sont fournis séparément (ex: `x_tr_space_uuid`, `x_tr_member_uuid`) — utiliser ces UUIDs comme références stables.

---

## 10. Réponse attendue

| Code HTTP | Interprétation |
|-----------|---------------|
| `202 Accepted` | ✅ Succès — webhook traité |
| `200 OK` | ✅ Accepté |
| Tout autre code | ❌ Échec — enregistré dans les logs Odoo |

**Recommandations :**
- Répondre en **moins de 5 secondes** (timeout Odoo)
- Accepter immédiatement (`202`) et traiter en arrière-plan
- Utiliser `event_id` pour détecter les doublons (pas de retry automatique)
- Valider le header `X-API-Key` avant tout traitement

---

## Annexe — Tableau récapitulatif des UUIDs

| Entité | Champ UUID dans `data` | Utilisation |
|--------|----------------------|-------------|
| Membre | `x_tr_uuid` | Identifiant primaire du membre |
| Membre | `x_tr_membership_type_uuid` | Référence vers le type d'adhésion |
| Réservation | `x_tr_uuid` | Identifiant primaire de la réservation |
| Réservation | `x_tr_space_uuid` | Référence vers l'espace réservé |
| Réservation | `x_tr_member_uuid` | Référence vers le membre |
| Abonnement | `x_tr_uuid` | Identifiant primaire de l'abonnement |
| Abonnement | `x_tr_plan_uuid` | Référence vers le plan |
| Abonnement | `x_tr_member_uuid` | Référence vers le membre |
| Espace/Plan | `x_tr_space_uuid` | Identifiant primaire de l'espace ou plan |
| Commande POS | `x_tr_uuid` | Identifiant primaire (commandes mobiles) |
| Commande POS | `x_tr_member_uuid` | Référence vers le membre |
| Catégorie POS | `x_tr_uuid` | Identifiant primaire de la catégorie |
| Catégorie POS | `x_tr_parent_uuid` | Référence vers la catégorie parente |
