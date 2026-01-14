# Odoo – Mobile API Documentation

Cette documentation décrit l’API exposée par **Odoo 19** à destination de l’application mobile.
Elle est volontairement **lisible, fonctionnelle et orientée mobile**, sur le même format que l’API *The Residence*.

---

## Table of Contents

1. Authentication
2. Base URL
3. Common Headers
4. Error Handling
5. API Endpoints
   - Reference Data
   - Members & Subscriptions
   - Space Reservations
   - Restaurant Orders

---

## 1. Authentication

Toutes les requêtes doivent être authentifiées via une **API Key** fournie par Odoo.

### Header requis
```
X-API-Key: your-api-key-here
```

### Erreurs d’authentification

| Status | Error | Description |
|------|------|-------------|
| 401 | UNAUTHORIZED | API key manquante ou invalide |
| 403 | FORBIDDEN | Accès non autorisé |

---

## 2. Base URL

| Environment | Base URL |
|------------|----------|
| Production | https://laresidenceci.odoo.com/ |
| Staging | https://proof-sudo-laresidenceci-main-27482954.dev.odoo.com/odoo |

---

## 3. Common Headers

| Header | Required | Description |
|------|----------|-------------|
| X-API-Key | Yes | Clé d’authentification |
| Content-Type | Yes | application/json |
| Accept-Language | No | fr / en (default: fr) |

---

## 4. Error Handling

Toutes les erreurs retournent le format suivant :

```json
{
  "success": false,
  "message": "Salle non disponible",
  "errorCode": "SPACE_NOT_AVAILABLE",
  "timestamp": "2026-01-15T10:30:00Z"
}
```

### Codes d’erreur courants

| Code | HTTP | Description |
|-----|------|-------------|
| INVALID_REQUEST | 400 | Données invalides |
| NOT_FOUND | 404 | Ressource inexistante |
| SPACE_NOT_AVAILABLE | 409 | Salle déjà réservée |
| MEMBER_NOT_FOUND | 404 | Client introuvable |
| INTERNAL_ERROR | 500 | Erreur serveur |

---

## 5. API Endpoints

# Reference Data

## List all spaces

```
GET /spaces
```

### Response
```json
[
  {
    "id": 12,
    "name": "Salle Conférence A",
    "description": "Grande salle équipée",
    "capacity": 50,
    "pricePerHour": 25000,
    "isAvailable": true
  }
]
```

---

## Get space by ID

```
GET /spaces/{id}
```

---

## List restaurant menu items

```
GET /menu/items
```

```json
[
  {
    "id": 5,
    "name": "Salade César",
    "category": "Entrées",
    "price": 12500,
    "isAvailable": true
  }
]
```

---

# Members & Subscriptions

## Create member (customer)

```
POST /members
```

```json
{
  "firstName": "Jean",
  "lastName": "Dupont",
  "email": "jean@example.com",
  "phone": "+22507000000"
}
```

### Response
```json
{
  "id": 45,
  "status": "ACTIVE"
}
```

---

## List subscription plans

```
GET /subscriptions
```

```json
[
  {
    "id": 1,
    "name": "Premium",
    "price": 50000,
    "durationMonths": 1
  }
]
```

---

## Subscribe member

```
POST /subscriptions/subscribe
```

```json
{
  "memberId": 45,
  "subscriptionId": 1
}
```

---

# Space Reservations

## Create reservation

```
POST /reservations
```

```json
{
  "memberId": 45,
  "spaceId": 12,
  "startTime": "2026-01-20T10:00:00",
  "endTime": "2026-01-20T12:00:00",
  "notes": "Réunion client"
}
```

### Response
```json
{
  "id": 98,
  "status": "PENDING",
  "saleOrder": "SO098",
  "totalAmount": 50000
}
```

---

## Get reservation by ID

```
GET /reservations/{id}
```

---

# Restaurant Orders

## Create restaurant order

```
POST /orders
```

```json
{
  "memberId": 45,
  "items": [
    {"menuItemId": 5, "quantity": 2},
    {"menuItemId": 8, "quantity": 1}
  ]
}
```

### Response
```json
{
  "id": 120,
  "status": "PENDING",
  "totalAmount": 45500
}
```

---

## Order Status Flow

| Status | Description |
|------|-------------|
| PENDING | Commande créée |
| IN_PREPARATION | En cuisine |
| READY | Prête |
| PAID | Payée |
| CANCELLED | Annulée |

---

## Notes importantes pour le mobile

- Toujours considérer Odoo comme **source de vérité**
- Ne jamais supposer une disponibilité sans validation API
- Conserver les IDs retournés par Odoo
- Gérer tous les codes d’erreur

---

**End of document**

