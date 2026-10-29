# The Residence — Event Sync API

Documentation des services Odoo exposés pour la synchronisation des événements.
Destinée au développeur backend/mobile du projet The Residence.

---

## Table des matières

1. [Authentification](#authentification)
2. [Base URL & format des réponses](#base-url--format-des-réponses)
3. [Gestion des événements](#gestion-des-événements)
4. [Gestion des inscriptions](#gestion-des-inscriptions)
5. [Gestion des invités nominatifs](#gestion-des-invités-nominatifs)
6. [Codes d'erreur](#codes-derreur)
7. [Workflow complet](#workflow-complet)

---

## Authentification

Toutes les requêtes doivent inclure une clé API dans le header HTTP :

```
X-API-Key: <votre_cle_api>
```

La clé API est fournie par l'équipe Odoo. Sans clé valide, toutes les requêtes retournent `401 Unauthorized`.

---

## Base URL & format des réponses

**Base URL :** `https://proof-sudo-laresidenceci.odoo.com/v1/external`

### Format de succès

```json
{
  "success": true,
  "data": { ... },
  "timestamp": "2026-04-15T10:00:00Z"
}
```

### Format d'erreur

```json
{
  "success": false,
  "message": "Description de l'erreur",
  "errorCode": "CODE_ERREUR",
  "timestamp": "2026-04-15T10:00:00Z"
}
```

### Format des dates

Toutes les dates sont en **ISO 8601 UTC** avec le suffixe `Z` :
```
"2026-04-15T19:00:00Z"
```

Les dates avec offset timezone sont également acceptées en entrée :
```
"2026-04-15T20:00:00+01:00"  →  converti automatiquement en UTC
```

---

## Gestion des événements

### POST `/events` — Créer un événement

Appeler cet endpoint **immédiatement après** la création de l'événement dans votre base de données locale.

**Request body :**

```json
{
  "externalId":    "550e8400-e29b-41d4-a716-446655440000",
  "title":         "Soirée Jazz au Lounge",
  "description":   "Une soirée musicale avec cocktails et jazz live.",
  "startAt":       "2026-04-15T19:00:00Z",
  "endAt":         "2026-04-15T23:00:00Z",
  "capacity":      50,
  "audienceUuids": ["uuid-plan-premium", "uuid-plan-business"]
}
```

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `externalId` | string (UUID) | ✅ | UUID de l'événement dans votre système |
| `title` | string | ✅ | Titre de l'événement (langue par défaut : français) |
| `description` | string | ❌ | Description détaillée |
| `startAt` | string (ISO 8601) | ✅ | Date/heure de début |
| `endAt` | string (ISO 8601) | ✅ | Date/heure de fin |
| `capacity` | integer | ❌ | Capacité max. `null` ou absent = illimité |
| `audienceUuids` | array of strings | ❌ | UUIDs des plans d'abonnement ciblés. Vide ou absent = ouvert à tous |

**Réponse `201 Created` :**

```json
{
  "success": true,
  "data": {
    "odooId":       12,
    "externalId":   "550e8400-e29b-41d4-a716-446655440000",
    "name":         "Soirée Jazz au Lounge",
    "dateBegin":    "2026-04-15T19:00:00Z",
    "dateEnd":      "2026-04-15T23:00:00Z",
    "capacity":     50,
    "seatsAvailable": 50,
    "active":       true,
    "audience": [
      { "odooId": 5, "name": "Premium", "uuid": "uuid-plan-premium" },
      { "odooId": 6, "name": "Business", "uuid": "uuid-plan-business" }
    ]
  },
  "timestamp": "2026-04-15T10:00:00Z"
}
```

> ⚠️ **Important :** Stockez le `odooId` retourné dans votre base de données. Il sera nécessaire pour les opérations suivantes.

---

### PUT `/events/{externalId}` — Modifier un événement

Tous les champs sont optionnels. Seuls les champs présents dans le body sont mis à jour.

**Request body :**

```json
{
  "title":         "Soirée Jazz au Salon Privé",
  "description":   "Nouvelle description...",
  "startAt":       "2026-04-15T20:00:00Z",
  "endAt":         "2026-04-16T00:00:00Z",
  "capacity":      80,
  "audienceUuids": ["uuid-plan-premium"],
  "cancelled":     false
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `title` | string | Nouveau titre |
| `description` | string | Nouvelle description |
| `startAt` | string (ISO 8601) | Nouvelle date de début |
| `endAt` | string (ISO 8601) | Nouvelle date de fin |
| `capacity` | integer | Nouvelle capacité. `0` ou `null` = illimité |
| `audienceUuids` | array | Remplace complètement l'audience. `[]` = ouvert à tous |
| `cancelled` | boolean | `true` = archiver l'événement dans Odoo |

**Réponse `200 OK` :** même format que la création.

---

### DELETE `/events/{externalId}` — Archiver un événement

Correspond au **soft delete** (`deleted_at`) de votre système. L'événement est archivé dans Odoo (non supprimé physiquement, historique conservé).

**Réponse `200 OK` :**

```json
{
  "success": true,
  "data": {
    "odooId":     12,
    "externalId": "550e8400-e29b-41d4-a716-446655440000",
    "archived":   true
  },
  "timestamp": "2026-04-15T10:00:00Z"
}
```

---

## Gestion des inscriptions

### POST `/events/{externalId}/registrations` — Inscrire un membre

À appeler lors de la création d'une `EventRegistration` dans votre système.

**Request body :**

```json
{
  "externalRegistrationId": "reg-550e8400-jean",
  "memberUuid":             "a43e62bb-7afa-496c-b1d9-315b1d4df598",
  "memberOdooId":           42,
  "name":                   "Jean Kouassi",
  "email":                  "jean@example.com",
  "phone":                  "+2250700000000",
  "guestsCount":            2,
  "status":                 "VALIDATED"
}
```

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `externalRegistrationId` | string (UUID) | ✅ | UUID de l'inscription dans votre système |
| `memberUuid` | string | ❌ | UUID du membre dans votre système (utilisé pour retrouver le contact Odoo) |
| `memberOdooId` | integer | ❌ | ID Odoo du membre (prioritaire sur `memberUuid` si fourni) |
| `name` | string | ✅* | Nom complet du membre |
| `email` | string | ✅* | Email du membre |
| `phone` | string | ❌ | Téléphone |
| `guestsCount` | integer | ❌ | Nombre d'invités non-nominatifs déclarés (défaut: 0) |
| `status` | string | ❌ | `VALIDATED` (défaut), `PENDING`, `CANCELLED` |

*Au moins `name` ou `email` est obligatoire.

**Mapping des statuts :**

| Votre statut | Statut Odoo | Cas d'usage |
|---|---|---|
| `VALIDATED` | `open` | Membre non-VISITOR → inscription auto-confirmée |
| `PENDING` | `draft` | Membre VISITOR → en attente de validation admin |
| `CANCELLED` | `cancel` | Inscription annulée |

**Réponse `201 Created` :**

```json
{
  "success": true,
  "data": {
    "odooId":                  88,
    "externalId":              "reg-550e8400-jean",
    "eventOdooId":             12,
    "eventExternalId":         "550e8400-e29b-41d4-a716-446655440000",
    "partnerOdooId":           42,
    "memberUuid":              "a43e62bb-7afa-496c-b1d9-315b1d4df598",
    "name":                    "Jean Kouassi",
    "email":                   "jean@example.com",
    "phone":                   "+2250700000000",
    "guestsCount":             2,
    "state":                   "open",
    "isAttendee":              false,
    "parentRegistrationOdooId": null,
    "attendees":               []
  },
  "timestamp": "2026-04-15T10:05:00Z"
}
```

---

### PUT `/events/{externalId}/registrations/{externalRegistrationId}` — Modifier une inscription

À appeler notamment lors du passage `PENDING → VALIDATED` (validation admin d'un VISITOR).

**Request body :**

```json
{
  "status":      "VALIDATED",
  "guestsCount": 3,
  "name":        "Jean Kouassi",
  "email":       "jean.kouassi@example.com",
  "phone":       "+2250700000001"
}
```

Tous les champs sont optionnels.

**Réponse `200 OK` :** même format que la création.

---

### DELETE `/events/{externalId}/registrations/{externalRegistrationId}` — Annuler une inscription

Annule l'inscription **et tous ses invités nominatifs** associés.

**Réponse `200 OK` :**

```json
{
  "success": true,
  "data": {
    "odooId":     88,
    "externalId": "reg-550e8400-jean",
    "state":      "cancel"
  },
  "timestamp": "2026-04-15T10:10:00Z"
}
```

---

## Gestion des invités nominatifs

Ces endpoints correspondent aux opérations sur vos `EventAttendee`.

### POST `.../registrations/{externalRegistrationId}/attendees` — Ajouter un invité

**Request body :**

```json
{
  "externalAttendeeId": "att-marie-001",
  "fullName":           "Marie Dupont",
  "email":              "marie@gmail.com",
  "phone":              "+2250700000002"
}
```

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `externalAttendeeId` | string (UUID) | ✅ | UUID de l'invité dans votre système |
| `fullName` | string | ✅* | Nom complet de l'invité |
| `email` | string | ✅* | Email de l'invité |
| `phone` | string | ❌ | Téléphone |

*Au moins `fullName` ou `email` est obligatoire.

> ⚠️ **Unicité email :** Un email ne peut être inscrit qu'une seule fois par événement (membre ou invité). Si l'email existe déjà, Odoo retourne `409 DUPLICATE_EMAIL`.

**Réponse `201 Created` :**

```json
{
  "success": true,
  "data": {
    "odooId":                   95,
    "externalId":               "att-marie-001",
    "eventOdooId":              12,
    "eventExternalId":          "550e8400-e29b-41d4-a716-446655440000",
    "partnerOdooId":            null,
    "memberUuid":               "",
    "name":                     "Marie Dupont",
    "email":                    "marie@gmail.com",
    "phone":                    "+2250700000002",
    "guestsCount":              0,
    "state":                    "open",
    "isAttendee":               true,
    "parentRegistrationOdooId": 88,
    "attendees":                []
  },
  "timestamp": "2026-04-15T10:15:00Z"
}
```

---

### PUT `.../registrations/{externalRegistrationId}/attendees/{externalAttendeeId}` — Modifier un invité

**Request body :**

```json
{
  "fullName": "Marie Martin",
  "email":    "marie.martin@gmail.com",
  "phone":    "+2250700000003"
}
```

Tous les champs sont optionnels.

**Réponse `200 OK` :** même format que la création.

---

### DELETE `.../registrations/{externalRegistrationId}/attendees/{externalAttendeeId}` — Supprimer un invité

Suppression **physique** (hard delete) conformément aux règles métier.

**Réponse `200 OK` :**

```json
{
  "success": true,
  "data": {
    "odooId":     95,
    "externalId": "att-marie-001",
    "deleted":    true
  },
  "timestamp": "2026-04-15T10:20:00Z"
}
```

---

## Codes d'erreur

| Code HTTP | errorCode | Description |
|-----------|-----------|-------------|
| 400 | `MISSING_FIELD` | Champ obligatoire absent |
| 400 | `INVALID_DATE` | Format de date invalide ou endAt ≤ startAt |
| 400 | `INVALID_REQUEST` | Erreur générique de validation |
| 401 | `UNAUTHORIZED` | Clé API absente ou invalide |
| 403 | `FORBIDDEN` | Permission insuffisante pour cette opération |
| 404 | `NOT_FOUND` | Ressource introuvable (mauvais externalId) |
| 409 | `DUPLICATE` | Une ressource avec ce externalId existe déjà |
| 409 | `DUPLICATE_EMAIL` | Cet email est déjà inscrit à l'événement |

---

## Workflow complet

Voici l'ordre exact des appels à effectuer dans chaque scénario.

### Scénario A — Créer un événement avec espace

```
1. POST /v1/external/events
   → stocker odooId retourné

2. POST /v1/external/reservations          (réservation espace — API existante)
   → stocker odooReservationId retourné
```

### Scénario B — Inscription d'un membre

```
1. POST /v1/external/events/{externalId}/registrations
   → stocker odooId de l'inscription
```

### Scénario C — Membre ajoute des invités nominatifs

```
Pour chaque EventAttendee :
  POST /v1/external/events/{externalId}/registrations/{regId}/attendees
  → stocker odooId de l'invité
```

### Scénario D — Validation d'un VISITOR (PENDING → VALIDATED)

```
1. PUT /v1/external/events/{externalId}/registrations/{regId}
   { "status": "VALIDATED" }
```

### Scénario E — Annulation d'une inscription

```
1. DELETE /v1/external/events/{externalId}/registrations/{regId}
   → annule automatiquement tous les invités nominatifs liés
```

### Scénario F — Modification de l'espace d'un événement

```
1. DELETE /v1/external/reservations/{odooReservationId}   (annule l'ancienne)
2. POST   /v1/external/reservations                       (crée la nouvelle)
3. PUT    /v1/external/events/{externalId}                (met à jour les dates si besoin)
```

### Scénario G — Soft delete d'un événement

```
1. DELETE /v1/external/events/{externalId}
   → les inscriptions et invités sont conservés dans l'historique Odoo
   → la réservation d'espace doit être annulée séparément si elle existe
```

---

## Récapitulatif des endpoints

| Méthode | Endpoint | Action |
|---------|----------|--------|
| `POST` | `/v1/external/events` | Créer un événement |
| `PUT` | `/v1/external/events/{externalId}` | Modifier un événement |
| `DELETE` | `/v1/external/events/{externalId}` | Archiver un événement |
| `POST` | `/v1/external/events/{externalId}/registrations` | Inscrire un membre |
| `PUT` | `/v1/external/events/{externalId}/registrations/{regId}` | Modifier une inscription |
| `DELETE` | `/v1/external/events/{externalId}/registrations/{regId}` | Annuler une inscription |
| `POST` | `/v1/external/events/{externalId}/registrations/{regId}/attendees` | Ajouter un invité |
| `PUT` | `/v1/external/events/{externalId}/registrations/{regId}/attendees/{attId}` | Modifier un invité |
| `DELETE` | `/v1/external/events/{externalId}/registrations/{regId}/attendees/{attId}` | Supprimer un invité |

---

*Document généré le 2026-03-29 — The Residence Business Club*
