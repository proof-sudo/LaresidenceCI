# The Residence - API Documentation (Odoo Module)

Documentation technique des APIs REST exposées par le module Odoo `theresidence_api` pour l'intégration avec l'application mobile The Residence.

**Version:** 19.0.1.1.0  
**Date:** 2026-01-18  
**Licence:** LGPL-3

---

## Table des matières

1. [Authentification](#1-authentification)
2. [URL de base](#2-url-de-base)
3. [En-têtes communs](#3-en-têtes-communs)
4. [Gestion des erreurs](#4-gestion-des-erreurs)
5. [Pagination](#5-pagination)
6. [Endpoints API](#6-endpoints-api)
   - [Health Check](#61-health-check)
   - [Types d'adhésion](#62-types-dadhésion-membership-types)
   - [Espaces](#63-espaces-spaces)
   - [Options de réservation](#64-options-de-réservation)
   - [Menu Restaurant](#65-menu-restaurant)
   - [Membres](#66-membres-members)
   - [Réservations](#67-réservations)
   - [Commandes](#68-commandes-orders)
   - [Abonnements](#69-abonnements-subscriptions)
   - [Webhooks](#610-webhooks)
7. [Événements Webhook](#7-événements-webhook)
8. [Sécurité des Webhooks](#8-sécurité-des-webhooks)
9. [Diagrammes de flux](#9-diagrammes-de-flux)
10. [Résumé des endpoints](#10-résumé-des-endpoints)

---

## 1. Authentification

Tous les endpoints nécessitent une authentification via une clé API transmise dans l'en-tête de la requête.

```
X-API-Key: votre-cle-api
```

### Format de la clé

Les clés API sont au format `tr_` suivi de 32 caractères aléatoires :
```
tr_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456
```

### Exemple de requête

```bash
curl -X GET "https://votre-odoo.com/v1/external/reference/spaces" \
  -H "X-API-Key: tr_votre_cle_api" \
  -H "Content-Type: application/json"
```

### Erreurs d'authentification

| Code HTTP | Erreur | Description |
|-----------|--------|-------------|
| 401 | `UNAUTHORIZED` | Clé API manquante ou invalide |
| 403 | `FORBIDDEN` | Clé API sans permission pour cette ressource |

---

## 2. URL de base

| Environnement | URL de base |
|---------------|-------------|
| Production | `https://votre-odoo.com/v1/external` |
| Développement | `http://localhost:8069/v1/external` |

---

## 3. En-têtes communs

| En-tête | Requis | Description |
|---------|--------|-------------|
| `X-API-Key` | Oui | Clé d'authentification API |
| `Content-Type` | Oui (POST/PUT/PATCH) | `application/json` |
| `Accept-Language` | Non | Locale pour le contenu i18n (`fr` ou `en`, défaut: `fr`) |

---

## 4. Gestion des erreurs

Toutes les erreurs suivent un format cohérent :

```json
{
  "success": false,
  "message": "Description de l'erreur",
  "errorCode": "CODE_ERREUR",
  "timestamp": "2026-01-18T10:00:00Z"
}
```

### Codes d'erreur courants

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Authentification requise |
| `FORBIDDEN` | 403 | Accès non autorisé |
| `NOT_FOUND` | 404 | Ressource non trouvée |
| `INVALID_REQUEST` | 400 | Paramètres de requête invalides |
| `INVALID_STATUS_TRANSITION` | 400 | Transition de statut non autorisée |
| `MEMBER_NOT_FOUND` | 404 | Membre inexistant |
| `SPACE_NOT_FOUND` | 404 | Espace inexistant |
| `ORDER_NOT_FOUND` | 404 | Commande inexistante |
| `RESERVATION_NOT_FOUND` | 404 | Réservation inexistante |
| `SUBSCRIPTION_NOT_FOUND` | 404 | Abonnement inexistant |

---

## 5. Pagination

Les endpoints de liste supportent la pagination :

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `page` | integer | 0 | Numéro de page (base 0) |
| `size` | integer | 20 | Éléments par page (max: 100) |

### Format de réponse paginée

```json
{
  "content": [...],
  "totalCount": 150,
  "pagingInfo": {
    "size": 20,
    "pageCount": 8,
    "currentPage": 0,
    "hasPrevious": false,
    "hasNext": true
  }
}
```

---

## 6. Endpoints API

### 6.1 Health Check

#### Vérifier l'état de l'API

```
GET /v1/external/health
```

**Authentification :** Non requise

**Réponse :**

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2026-01-18T10:00:00Z",
    "version": "19.0.1.1.0"
  }
}
```

#### Informations sur la clé API

```
GET /v1/external/info
```

**Réponse :**

```json
{
  "success": true,
  "data": {
    "keyName": "Mobile App Key",
    "permissions": {
      "members": {"read": true, "write": true},
      "spaces": {"read": true},
      "menu": {"read": true},
      "reservations": {"read": true, "write": true},
      "orders": {"read": true, "write": true},
      "subscriptions": {"read": true, "write": true},
      "webhooks": {"manage": true}
    }
  }
}
```

---

### 6.2 Types d'adhésion (Membership Types)

#### Lister tous les types d'adhésion

```
GET /v1/external/membership-types
```

**Réponse :**

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-here",
      "code": "VISITOR",
      "name": "Visiteur",
      "description": "Accès limité aux événements",
      "sortOrder": 1
    },
    {
      "id": "uuid-here",
      "code": "MEMBER",
      "name": "Membre",
      "description": "Accès complet au club",
      "sortOrder": 2
    },
    {
      "id": "uuid-here",
      "code": "PREMIUM",
      "name": "Premium",
      "description": "Accès complet avec avantages exclusifs",
      "sortOrder": 3
    },
    {
      "id": "uuid-here",
      "code": "VIP",
      "name": "VIP",
      "description": "Accès illimité et services personnalisés",
      "sortOrder": 4
    }
  ]
}
```

#### Obtenir un type d'adhésion

```
GET /v1/external/membership-types/{id}
```

**Paramètres de chemin :**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `id` | string | UUID ou code du type (ex: `PREMIUM`) |

---

### 6.3 Espaces (Spaces)

#### Lister tous les espaces

```
GET /v1/external/reference/spaces
```

**Paramètres de requête :**

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `type` | string | Non | Filtrer par type (`MEETING_ROOM`, `CONFERENCE`, `OFFICE`, `COWORKING`, `EVENT`, `LOUNGE`) |
| `locationId` | string | Non | Filtrer par emplacement |
| `locale` | string | Non | Code langue (défaut: `fr`) |

**Réponse :**

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Salle de Conférence A",
      "description": "Grande salle équipée pour les réunions",
      "type": "MEETING_ROOM",
      "capacity": 50,
      "locationId": "660e8400-e29b-41d4-a716-446655440001",
      "locationName": "Bâtiment Principal",
      "pricePerHour": 25000.00,
      "currency": "XOF",
      "imageUrl": "https://votre-odoo.com/web/image/product.template/123/image_1920",
      "media": [
        {
          "url": "https://votre-odoo.com/web/image/...",
          "sortOrder": 1
        }
      ],
      "isAvailable": true
    }
  ]
}
```

#### Obtenir un espace

```
GET /v1/external/reference/spaces/{id}
```

#### Vérifier la disponibilité d'un espace

```
GET /v1/external/reference/spaces/{id}/availability
```

**Paramètres de requête :**

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `startTime` | datetime | Oui | Date/heure de début (ISO 8601) |
| `endTime` | datetime | Oui | Date/heure de fin (ISO 8601) |

**Exemple :**
```
GET /v1/external/reference/spaces/550e8400.../availability?startTime=2026-01-20T10:00:00&endTime=2026-01-20T12:00:00
```

**Réponse (disponible) :**

```json
{
  "success": true,
  "data": {
    "spaceId": "550e8400-e29b-41d4-a716-446655440000",
    "spaceName": "Salle Conférence A",
    "startTime": "2026-01-20T10:00:00",
    "endTime": "2026-01-20T12:00:00",
    "isAvailable": true,
    "conflictingReservations": 0
  }
}
```

**Réponse (non disponible) :**

```json
{
  "success": true,
  "data": {
    "spaceId": "550e8400-e29b-41d4-a716-446655440000",
    "spaceName": "Salle Conférence A",
    "startTime": "2026-01-20T10:00:00",
    "endTime": "2026-01-20T12:00:00",
    "isAvailable": false,
    "conflictingReservations": 1
  }
}
```

---

### 6.4 Options de réservation

#### Lister les options disponibles

```
GET /v1/external/reservation-options
```

**Paramètres de requête :**

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `scope` | string | Non | Filtrer par portée : `SPACE`, `EVENT`, `GLOBAL` |

**Réponse :**

```json
{
  "success": true,
  "data": [
    {
      "id": "opt-uuid-1",
      "code": "PROJECTOR",
      "scope": "SPACE",
      "label": "Vidéoprojecteur",
      "description": "Vidéoprojecteur HD avec écran",
      "price": 5000,
      "currency": "XOF"
    },
    {
      "id": "opt-uuid-2",
      "code": "CATERING",
      "scope": "SPACE",
      "label": "Service traiteur",
      "description": "Pause café, déjeuner ou cocktail",
      "price": 25000,
      "currency": "XOF"
    },
    {
      "id": "opt-uuid-3",
      "code": "WIFI_PREMIUM",
      "scope": "SPACE",
      "label": "WiFi haut débit",
      "description": "Connexion WiFi dédiée haute vitesse",
      "price": 3000,
      "currency": "XOF"
    }
  ]
}
```

#### Obtenir une option

```
GET /v1/external/reservation-options/{id}
```

---

### 6.5 Menu Restaurant

#### Lister les types de menu (kinds)

```
GET /v1/external/reference/menu-kinds
```

**Réponse :**

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-kind-1",
      "code": "BREAKFAST",
      "name": "Petit-déjeuner",
      "sortOrder": 1
    },
    {
      "id": "uuid-kind-2",
      "code": "LUNCH",
      "name": "Déjeuner",
      "sortOrder": 2
    },
    {
      "id": "uuid-kind-3",
      "code": "DINNER",
      "name": "Dîner",
      "sortOrder": 3
    },
    {
      "id": "uuid-kind-4",
      "code": "DRINKS",
      "name": "Boissons",
      "sortOrder": 4
    }
  ]
}
```

#### Catégories par type de menu

```
GET /v1/external/reference/menu-kinds/{kindId}/categories
```

**Réponse :**

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-category-1",
      "kindId": "uuid-kind-2",
      "name": "Entrées",
      "sortOrder": 1
    },
    {
      "id": "uuid-category-2",
      "kindId": "uuid-kind-2",
      "name": "Plats principaux",
      "sortOrder": 2
    },
    {
      "id": "uuid-category-3",
      "kindId": "uuid-kind-2",
      "name": "Desserts",
      "sortOrder": 3
    }
  ]
}
```

#### Lister toutes les catégories

```
GET /v1/external/reference/menu-categories
```

**Réponse :**

```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-category-1",
      "kindId": "uuid-kind-2",
      "kindName": "Déjeuner",
      "name": "Entrées",
      "imageUrl": "https://votre-odoo.com/web/image/pos.category/1/image_128",
      "sortOrder": 1
    }
  ]
}
```

#### Articles par catégorie

```
GET /v1/external/reference/menu-categories/{categoryId}/items
```

**Réponse :**

```json
{
  "success": true,
  "data": [
    {
      "id": "5",
      "categoryId": "uuid-category-1",
      "name": "Salade César",
      "description": "Salade romaine, parmesan, croûtons",
      "price": 8500,
      "currency": "XOF",
      "isAvailable": true,
      "imageUrl": "https://votre-odoo.com/web/image/product.product/5/image_128",
      "sortOrder": 1
    }
  ]
}
```

#### Lister tous les articles

```
GET /v1/external/reference/menu-items
```

**Réponse (avec hiérarchie complète) :**

```json
{
  "success": true,
  "data": [
    {
      "id": "5",
      "name": "Salade César",
      "description": "Salade romaine, parmesan, croûtons",
      "price": 8500,
      "currency": "XOF",
      "isAvailable": true,
      "imageUrl": "https://votre-odoo.com/web/image/product.product/5/image_128",
      "sortOrder": 1,
      "categoryId": "uuid-category-1",
      "categoryName": "Entrées",
      "kindId": "uuid-kind-2",
      "kindName": "Déjeuner"
    }
  ]
}
```

#### Obtenir un article

```
GET /v1/external/reference/menu-items/{id}
```

---

### 6.6 Membres (Members)

#### Rechercher des membres

```
GET /v1/external/reference/members
```

**Paramètres de requête :**

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `query` | string | Non | Recherche par nom, email ou entreprise |
| `page` | integer | Non | Numéro de page |
| `size` | integer | Non | Éléments par page |

**Réponse :**

```json
{
  "content": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440000",
      "firstName": "Jean",
      "lastName": "Dupont",
      "email": "jean.dupont@example.com",
      "phone": "+225070123456",
      "companyName": "Acme Corp",
      "jobTitle": "Directeur",
      "membershipTypeId": "uuid-type",
      "membershipTypeCode": "PREMIUM",
      "membershipTypeName": "Premium",
      "status": "ACTIVE",
      "joinedAt": "2025-01-15",
      "qrToken": "member-qr-abc123"
    }
  ],
  "totalCount": 1,
  "pagingInfo": {...}
}
```

#### Obtenir un membre

```
GET /v1/external/reference/members/{id}
```

#### Créer un membre

```
POST /v1/external/reference/members
```

**Corps de la requête :**

```json
{
  "firstName": "Jean",
  "lastName": "Dupont",
  "email": "jean.dupont@example.com",
  "phone": "+225070123456",
  "companyName": "Acme Corp",
  "jobTitle": "Directeur",
  "membershipTypeCode": "MEMBER"
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `firstName` | string | Oui | Prénom |
| `lastName` | string | Oui | Nom |
| `email` | string | Oui | Adresse email |
| `phone` | string | Non | Numéro de téléphone |
| `companyName` | string | Non | Nom de l'entreprise |
| `jobTitle` | string | Non | Poste |
| `membershipTypeCode` | string | Non | Code du type d'adhésion |

**Réponse :** `201 Created` avec l'objet membre créé.

#### Mettre à jour un membre

```
PUT /v1/external/reference/members/{id}
```

**Corps de la requête :**

```json
{
  "firstName": "Jean",
  "lastName": "Dupont",
  "phone": "+225070000001",
  "companyName": "XYZ Corp",
  "jobTitle": "PDG"
}
```

---

### 6.7 Réservations

#### Lister les réservations

```
GET /v1/external/reservations
```

**Paramètres de requête :**

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `memberId` | string | Non | Filtrer par ID membre |
| `spaceId` | string | Non | Filtrer par ID espace |
| `status` | string | Non | Filtrer par statut |
| `startDate` | datetime | Non | Réservations commençant après cette date |
| `endDate` | datetime | Non | Réservations se terminant avant cette date |
| `page` | integer | Non | Numéro de page |
| `size` | integer | Non | Éléments par page |

**Statuts disponibles :** `PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`, `CHECKED_IN`, `COMPLETED`

**Réponse :**

```json
{
  "content": [
    {
      "id": "bb0e8400-e29b-41d4-a716-446655440000",
      "memberId": "aa0e8400-e29b-41d4-a716-446655440000",
      "memberFirstName": "Jean",
      "memberLastName": "Dupont",
      "memberEmail": "jean.dupont@example.com",
      "spaceId": "550e8400-e29b-41d4-a716-446655440000",
      "spaceName": "Salle de Conférence A",
      "startTime": "2026-01-20T14:00:00",
      "endTime": "2026-01-20T16:00:00",
      "guestCount": 10,
      "status": "PENDING",
      "totalAmount": 50000.00,
      "currency": "XOF",
      "notes": "Réunion client importante",
      "saleOrder": "SO098",
      "qrToken": "abc123",
      "options": [
        {
          "id": "opt-instance-1",
          "optionId": "opt-uuid-1",
          "optionCode": "PROJECTOR",
          "optionLabel": "Vidéoprojecteur",
          "quantity": 1,
          "unitPrice": 5000.00,
          "amount": 5000.00
        }
      ],
      "invitees": [
        {
          "id": "inv-1",
          "name": "Marie Martin",
          "email": "marie.martin@example.com",
          "phone": "+225070987654"
        }
      ],
      "createdAt": "2026-01-10T09:30:00",
      "updatedAt": "2026-01-10T09:30:00"
    }
  ],
  "totalCount": 25,
  "pagingInfo": {...}
}
```

#### Obtenir une réservation

```
GET /v1/external/reservations/{id}
```

#### Créer une réservation

```
POST /v1/external/reservations
```

**Corps de la requête :**

```json
{
  "memberId": "aa0e8400-e29b-41d4-a716-446655440000",
  "spaceId": "550e8400-e29b-41d4-a716-446655440000",
  "startTime": "2026-01-20T10:00:00",
  "endTime": "2026-01-20T12:00:00",
  "guestCount": 8,
  "notes": "Formation interne",
  "optionIds": ["opt-uuid-1", "opt-uuid-2"],
  "invitees": [
    {
      "name": "Pierre Durand",
      "email": "pierre.durand@example.com",
      "phone": "+225070111222"
    }
  ]
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `memberId` | string | Oui | ID du membre |
| `spaceId` | string | Oui | ID de l'espace |
| `startTime` | datetime | Oui | Date/heure de début (ISO 8601) |
| `endTime` | datetime | Oui | Date/heure de fin (ISO 8601) |
| `guestCount` | integer | Non | Nombre de participants |
| `notes` | string | Non | Notes additionnelles |
| `optionIds` | array | Non | IDs des options |
| `invitees` | array | Non | Liste des invités |

**Réponse :** `201 Created` avec l'objet réservation créé.

#### Mettre à jour une réservation

```
PUT /v1/external/reservations/{id}
```

**Note :** Seules les réservations au statut `PENDING` peuvent être modifiées.

**Corps de la requête :**

```json
{
  "startTime": "2026-01-20T14:00:00",
  "endTime": "2026-01-20T16:00:00",
  "guestCount": 12,
  "notes": "Réunion élargie"
}
```

#### Annuler une réservation

```
DELETE /v1/external/reservations/{id}
```

ou

```
POST /v1/external/reservations/{id}/cancel
```

**Réponse :**

```json
{
  "success": true,
  "data": {
    "id": "bb0e8400-e29b-41d4-a716-446655440000",
    "status": "CANCELLED",
    "cancelledAt": "2026-01-15T10:30:00"
  }
}
```

#### Approuver une réservation

```
POST /v1/external/reservations/{id}/approve
```

**Statut requis :** `PENDING`

#### Rejeter une réservation

```
POST /v1/external/reservations/{id}/reject?reason=Salle non disponible
```

**Statut requis :** `PENDING`

#### Check-in d'une réservation

```
POST /v1/external/reservations/{id}/check-in
```

**Statut requis :** `APPROVED`

#### Ajouter/Modifier une option

```
PATCH /v1/external/reservations/{id}/options
```

**Corps de la requête :**

```json
{
  "optionId": "opt-uuid-2",
  "quantity": 1
}
```

**Réponse :**

```json
{
  "success": true,
  "data": {
    "reservationId": "bb0e8400-e29b-41d4-a716-446655440000",
    "options": [
      {
        "optionId": "opt-uuid-1",
        "optionCode": "PROJECTOR",
        "quantity": 1,
        "amount": 5000
      },
      {
        "optionId": "opt-uuid-2",
        "optionCode": "CATERING",
        "quantity": 1,
        "amount": 25000
      }
    ],
    "totalAmount": 80000
  }
}
```

#### Supprimer une option

```
DELETE /v1/external/reservations/{id}/options/{optionId}
```

**Réponse :**

```json
{
  "success": true,
  "data": {
    "reservationId": "bb0e8400-e29b-41d4-a716-446655440000",
    "removedOptionId": "opt-uuid-2",
    "totalAmount": 55000
  }
}
```

#### Ajouter un invité

```
PATCH /v1/external/reservations/{id}/invitees
```

**Corps de la requête :**

```json
{
  "fullName": "Marie Dupont",
  "email": "marie@example.com",
  "phone": "+225070111111"
}
```

#### Supprimer un invité

```
DELETE /v1/external/reservations/{id}/invitees/{inviteeId}
```

#### Réservations d'un membre

```
GET /v1/external/members/{memberId}/reservations
```

---

### 6.8 Commandes (Orders)

#### Lister les commandes

```
GET /v1/external/orders
```

**Paramètres de requête :**

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `memberId` | string | Non | Filtrer par ID membre |
| `status` | string | Non | Filtrer par statut |
| `mode` | string | Non | Filtrer par mode |
| `startDate` | datetime | Non | Commandes créées après cette date |
| `endDate` | datetime | Non | Commandes créées avant cette date |
| `page` | integer | Non | Numéro de page |
| `size` | integer | Non | Éléments par page |

**Statuts disponibles :** `PENDING`, `CONFIRMED`, `READY`, `COMPLETED`, `CANCELLED`

**Modes disponibles :** `PICKUP`, `DELIVERY`, `DINE_IN`

**Réponse :**

```json
{
  "content": [
    {
      "id": "ee0e8400-e29b-41d4-a716-446655440000",
      "memberId": "aa0e8400-e29b-41d4-a716-446655440000",
      "memberFirstName": "Jean",
      "memberLastName": "Dupont",
      "memberEmail": "jean.dupont@example.com",
      "mode": "PICKUP",
      "status": "PENDING",
      "totalAmount": 25500.00,
      "currency": "XOF",
      "qrToken": "order-qr-token-123",
      "deliveryAddress": null,
      "items": [
        {
          "id": "item-1",
          "menuItemId": "5",
          "menuItemName": "Salade César",
          "quantity": 2,
          "unitPrice": 8500.00,
          "amount": 17000.00
        }
      ],
      "createdAt": "2026-01-18T12:30:00",
      "updatedAt": "2026-01-18T12:30:00"
    }
  ],
  "totalCount": 42,
  "pagingInfo": {...}
}
```

#### Obtenir une commande

```
GET /v1/external/orders/{id}
```

#### Créer une commande

```
POST /v1/external/orders
```

**Corps de la requête :**

```json
{
  "memberId": "aa0e8400-e29b-41d4-a716-446655440000",
  "mode": "DELIVERY",
  "deliveryAddress": "Bureau 3A, Immeuble ABC",
  "items": [
    {"menuItemId": "5", "quantity": 2},
    {"menuItemId": "8", "quantity": 1}
  ],
  "notes": "Sans oignons SVP"
}
```

| Mode | Description | deliveryAddress |
|------|-------------|-----------------|
| `PICKUP` | Retrait sur place | Non requis |
| `DELIVERY` | Livraison | Requis |
| `DINE_IN` | Sur place | Non requis |

**Réponse :** `201 Created` avec l'objet commande créé.

#### Mettre à jour une commande

```
PUT /v1/external/orders/{id}
```

**Note :** Seules les commandes au statut `PENDING` peuvent être modifiées. La mise à jour remplace tous les items.

**Corps de la requête :**

```json
{
  "items": [
    {"menuItemId": "5", "quantity": 3},
    {"menuItemId": "10", "quantity": 1}
  ]
}
```

#### Confirmer une commande

```
POST /v1/external/orders/{id}/confirm
```

**Statut requis :** `PENDING`

#### Marquer une commande prête

```
POST /v1/external/orders/{id}/ready
```

**Statut requis :** `CONFIRMED`

#### Terminer une commande

```
POST /v1/external/orders/{id}/complete
```

**Statut requis :** `READY`

#### Annuler une commande

```
POST /v1/external/orders/{id}/cancel?reason=Client annulé
```

**Statuts autorisés :** `PENDING`, `CONFIRMED`, `READY`

**Réponse :**

```json
{
  "success": true,
  "data": {
    "id": "ee0e8400-e29b-41d4-a716-446655440000",
    "status": "CANCELLED",
    "cancelledAt": "2026-01-15T12:15:00"
  }
}
```

#### Commandes d'un membre

```
GET /v1/external/members/{memberId}/orders
```

---

### 6.9 Abonnements (Subscriptions)

#### Lister les abonnements

```
GET /v1/external/subscriptions
```

**Paramètres de requête :**

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `memberId` | string | Non | Filtrer par ID membre |
| `status` | string | Non | Filtrer par statut |
| `planId` | string | Non | Filtrer par ID de plan |
| `page` | integer | Non | Numéro de page |
| `size` | integer | Non | Éléments par page |

**Statuts disponibles :** `ACTIVE`, `PAUSED`, `CANCELLED`, `EXPIRED`

#### Obtenir un abonnement

```
GET /v1/external/subscriptions/{id}
```

#### Créer un abonnement

```
POST /v1/external/subscriptions
```

**Corps de la requête :**

```json
{
  "memberId": "aa0e8400-e29b-41d4-a716-446655440000",
  "planId": "hh0e8400-e29b-41d4-a716-446655440000",
  "billingPeriod": "MONTHLY",
  "autoRenew": true,
  "amount": 150000.00
}
```

#### Mettre en pause un abonnement

```
POST /v1/external/subscriptions/{id}/pause
```

#### Reprendre un abonnement

```
POST /v1/external/subscriptions/{id}/resume
```

#### Annuler un abonnement

```
POST /v1/external/subscriptions/{id}/cancel
```

#### Lister les plans d'abonnement

```
GET /v1/external/subscription-plans
```

**Réponse :**

```json
{
  "success": true,
  "data": [
    {
      "id": "hh0e8400-e29b-41d4-a716-446655440000",
      "name": "Premium Mensuel",
      "description": "Accès illimité aux espaces premium",
      "price": 150000.00,
      "durationMonths": 1,
      "membershipTypeCode": "PREMIUM",
      "currency": "XOF"
    }
  ]
}
```

---

### 6.10 Webhooks

#### Lister les webhooks

```
GET /v1/external/webhooks
```

#### Créer un webhook

```
POST /v1/external/webhooks
```

**Corps de la requête :**

```json
{
  "url": "https://votre-serveur.com/api/theresidence/webhook",
  "secret": "votre-secret-pour-signature",
  "eventTypes": [
    "MEMBER_CREATED",
    "RESERVATION_CREATED",
    "RESERVATION_UPDATED",
    "RESERVATION_CANCELLED",
    "RESERVATION_STATUS_CHANGED",
    "ORDER_CREATED",
    "ORDER_STATUS_CHANGED",
    "ORDER_CANCELLED",
    "SUBSCRIPTION_CREATED",
    "SUBSCRIPTION_STATUS_CHANGED",
    "SUBSCRIPTION_CANCELLED"
  ]
}
```

#### Mettre à jour un webhook

```
PUT /v1/external/webhooks/{id}
```

#### Supprimer un webhook

```
DELETE /v1/external/webhooks/{id}
```

#### Historique des événements

```
GET /v1/external/webhooks/{id}/events
```

#### Envoyer un test

```
POST /v1/external/webhooks/{id}/test
```

---

## 7. Événements Webhook

### Types d'événements

| Type | Déclencheur |
|------|-------------|
| `MEMBER_CREATED` | Nouveau membre créé |
| `RESERVATION_CREATED` | Nouvelle réservation |
| `RESERVATION_UPDATED` | Réservation modifiée |
| `RESERVATION_CANCELLED` | Réservation annulée |
| `RESERVATION_STATUS_CHANGED` | Changement de statut réservation |
| `ORDER_CREATED` | Nouvelle commande |
| `ORDER_STATUS_CHANGED` | Changement de statut commande |
| `ORDER_CANCELLED` | Commande annulée |
| `SUBSCRIPTION_CREATED` | Nouvel abonnement |
| `SUBSCRIPTION_STATUS_CHANGED` | Changement de statut abonnement |
| `SUBSCRIPTION_CANCELLED` | Abonnement annulé |

### Format du payload

```json
{
  "id": "330e8400-e29b-41d4-a716-446655440000",
  "eventType": "RESERVATION_STATUS_CHANGED",
  "entityType": "reservation",
  "entityId": "bb0e8400-e29b-41d4-a716-446655440000",
  "data": {...},
  "previousStatus": "PENDING",
  "newStatus": "APPROVED",
  "timestamp": "2026-01-18T10:30:00Z"
}
```

---

## 8. Sécurité des Webhooks

### Vérification de signature

Si un `secret` est configuré, les livraisons incluent une signature HMAC-SHA256 :

```
X-Webhook-Signature: sha256=<signature>
```

### Exemple de vérification (Python)

```python
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    received = signature.replace('sha256=', '')
    return hmac.compare_digest(expected, received)
```

### Exemple de vérification (JavaScript/Node.js)

```javascript
const crypto = require('crypto');

function verifyWebhookSignature(payload, signature, secret) {
    const expected = crypto
        .createHmac('sha256', secret)
        .update(payload)
        .digest('hex');
    const received = signature.replace('sha256=', '');
    return crypto.timingSafeEqual(
        Buffer.from(expected),
        Buffer.from(received)
    );
}
```

### Politique de retry

| Tentative | Délai |
|-----------|-------|
| 1 | Immédiat |
| 2 | 1 minute |
| 3 | 5 minutes |
| 4 | 30 minutes |
| 5 | 2 heures |

Après 5 tentatives échouées, l'événement est marqué comme `FAILED`.

---

## 9. Diagrammes de flux

### Statuts de réservation

```
PENDING → APPROVED → CHECKED_IN → COMPLETED
    ↓         ↓
 REJECTED  CANCELLED
```

| Status | Description | Transitions possibles |
|--------|-------------|----------------------|
| `PENDING` | Réservation créée, en attente | → `APPROVED`, `REJECTED`, `CANCELLED` |
| `APPROVED` | Réservation confirmée | → `CHECKED_IN`, `CANCELLED` |
| `REJECTED` | Réservation rejetée | (terminal) |
| `CHECKED_IN` | Membre arrivé | → `COMPLETED` |
| `COMPLETED` | Réservation terminée | (terminal) |
| `CANCELLED` | Réservation annulée | (terminal) |

### Statuts de commande

```
PENDING → CONFIRMED → READY → COMPLETED
    ↓         ↓         ↓
CANCELLED CANCELLED CANCELLED
```

| Status | Description | Transitions possibles |
|--------|-------------|----------------------|
| `PENDING` | Commande créée | → `CONFIRMED`, `CANCELLED` |
| `CONFIRMED` | En préparation | → `READY`, `CANCELLED` |
| `READY` | Prête pour retrait/livraison | → `COMPLETED`, `CANCELLED` |
| `COMPLETED` | Livrée/récupérée | (terminal) |
| `CANCELLED` | Annulée | (terminal) |

### Statuts d'abonnement

```
ACTIVE ↔ PAUSED
   ↓        ↓
CANCELLED CANCELLED
   ↓
EXPIRED (automatique)
```

---

## 10. Résumé des endpoints

| Domaine | Méthode | Endpoint | Description |
|---------|---------|----------|-------------|
| **Health** | GET | `/health` | État de l'API |
| | GET | `/info` | Infos clé API |
| **Membership Types** | GET | `/membership-types` | Liste types d'adhésion |
| | GET | `/membership-types/{id}` | Détail type |
| **Spaces** | GET | `/reference/spaces` | Liste espaces |
| | GET | `/reference/spaces/{id}` | Détail espace |
| | GET | `/reference/spaces/{id}/availability` | Vérifier disponibilité |
| **Options** | GET | `/reservation-options` | Liste options |
| | GET | `/reservation-options/{id}` | Détail option |
| **Menu** | GET | `/reference/menu-kinds` | Types de menu |
| | GET | `/reference/menu-kinds/{id}/categories` | Catégories par type |
| | GET | `/reference/menu-categories` | Toutes catégories |
| | GET | `/reference/menu-categories/{id}/items` | Items par catégorie |
| | GET | `/reference/menu-items` | Tous les items |
| | GET | `/reference/menu-items/{id}` | Détail item |
| **Members** | GET | `/reference/members` | Recherche membres |
| | POST | `/reference/members` | Créer membre |
| | GET | `/reference/members/{id}` | Détail membre |
| | PUT | `/reference/members/{id}` | Modifier membre |
| **Reservations** | GET | `/reservations` | Liste réservations |
| | POST | `/reservations` | Créer réservation |
| | GET | `/reservations/{id}` | Détail réservation |
| | PUT | `/reservations/{id}` | Modifier réservation |
| | DELETE | `/reservations/{id}` | Annuler réservation |
| | POST | `/reservations/{id}/approve` | Approuver |
| | POST | `/reservations/{id}/reject` | Rejeter |
| | POST | `/reservations/{id}/check-in` | Check-in |
| | POST | `/reservations/{id}/cancel` | Annuler (POST) |
| | PATCH | `/reservations/{id}/options` | Ajouter/modifier option |
| | DELETE | `/reservations/{id}/options/{optionId}` | Supprimer option |
| | PATCH | `/reservations/{id}/invitees` | Ajouter invité |
| | DELETE | `/reservations/{id}/invitees/{inviteeId}` | Supprimer invité |
| | GET | `/members/{memberId}/reservations` | Réservations d'un membre |
| **Orders** | GET | `/orders` | Liste commandes |
| | POST | `/orders` | Créer commande |
| | GET | `/orders/{id}` | Détail commande |
| | PUT | `/orders/{id}` | Modifier commande |
| | POST | `/orders/{id}/confirm` | Confirmer |
| | POST | `/orders/{id}/ready` | Marquer prête |
| | POST | `/orders/{id}/complete` | Terminer |
| | POST | `/orders/{id}/cancel` | Annuler |
| | GET | `/members/{memberId}/orders` | Commandes d'un membre |
| **Subscriptions** | GET | `/subscriptions` | Liste abonnements |
| | POST | `/subscriptions` | Créer abonnement |
| | GET | `/subscriptions/{id}` | Détail abonnement |
| | POST | `/subscriptions/{id}/pause` | Pause |
| | POST | `/subscriptions/{id}/resume` | Reprendre |
| | POST | `/subscriptions/{id}/cancel` | Annuler |
| | GET | `/subscription-plans` | Liste plans |
| | GET | `/subscription-plans/{id}` | Détail plan |
| | GET | `/members/{memberId}/subscriptions` | Abonnements d'un membre |
| **Webhooks** | GET | `/webhooks` | Liste webhooks |
| | POST | `/webhooks` | Créer webhook |
| | GET | `/webhooks/{id}` | Détail webhook |
| | PUT | `/webhooks/{id}` | Modifier webhook |
| | DELETE | `/webhooks/{id}` | Supprimer webhook |
| | GET | `/webhooks/{id}/events` | Historique événements |
| | POST | `/webhooks/{id}/test` | Envoyer test |

---

## Support

Pour le support technique ou les demandes de clé API, contactez l'équipe de développement.

**Module:** `theresidence_api`  
**Version:** 19.0.1.1.0  
**Licence:** LGPL-3

---

*Fin du document*
