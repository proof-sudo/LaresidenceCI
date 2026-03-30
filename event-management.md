# Gestion des Événements - The Residence API

> Documentation technique destinée à l'équipe Odoo pour le mapping des données événementielles.

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Modèle de données](#modèle-de-données)
3. [Cycle de vie d'un événement](#cycle-de-vie-dun-événement)
4. [Inscriptions et participants](#inscriptions-et-participants)
5. [Liaison Événement ↔ Réservation](#liaison-événement--réservation)
6. [Intégration Odoo actuelle](#intégration-odoo-actuelle)
7. [API Endpoints](#api-endpoints)
8. [Règles métier](#règles-métier)

---

## Vue d'ensemble

Les événements sont gérés localement dans l'API The Residence. Contrairement aux entités comme les membres, espaces ou commandes qui sont synchronisées via webhooks Odoo, **les événements ne sont pas directement synchronisés avec Odoo**. Le seul point d'intégration actuel est la **réservation d'espace liée à un événement**, qui elle est synchronisée avec Odoo.

### Architecture résumée

```
┌─────────────────────────────────────────────────────────────┐
│                    The Residence API                         │
│                                                             │
│  ┌──────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │  Event   │───▶│ Event Registration│───▶│Event Attendee │  │
│  └────┬─────┘    └──────────────────┘    └───────────────┘  │
│       │                                                      │
│       │ 1:1 (via event_id)                                   │
│       ▼                                                      │
│  ┌──────────────┐         ┌──────────────────┐              │
│  │ Reservation  │────────▶│   Odoo Sync      │──────────┐   │
│  └──────────────┘         └──────────────────┘          │   │
│       │                                                  │   │
│       ▼                                                  ▼   │
│  ┌──────────┐                                    ┌──────────┐│
│  │  Space   │                                    │  Odoo    ││
│  └──────────┘                                    └──────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## Modèle de données

### Table `event`

| Colonne              | Type             | Nullable | Description                                      |
|----------------------|------------------|----------|--------------------------------------------------|
| `id`                 | CHAR(36) UUID    | NON      | Clé primaire                                     |
| `space_id`           | CHAR(36) FK      | OUI      | Espace où se déroule l'événement                 |
| `start_at`           | TIMESTAMP        | NON      | Date/heure de début                              |
| `end_at`             | TIMESTAMP        | NON      | Date/heure de fin                                |
| `capacity`           | INTEGER          | OUI      | Capacité max (NULL = illimité)                   |
| `max_guests_per_member` | INTEGER       | NON      | Nb max d'invités par membre (défaut: 3)          |
| `created_at`         | TIMESTAMP        | NON      | Date de création                                 |
| `updated_at`         | TIMESTAMP        | OUI      | Date de mise à jour                              |
| `deleted_at`         | TIMESTAMP        | OUI      | Suppression logique (soft delete)                |

**Relations :**
- `space_id` → `space(id)` (ManyToOne, optionnel)
- `event_audience` → table de jointure vers `membership_type` (ManyToMany)

### Table `event_i18n` (Internationalisation)

| Colonne      | Type        | Nullable | Description                    |
|--------------|-------------|----------|--------------------------------|
| `event_id`   | CHAR(36) FK | NON      | Clé composite – FK vers event  |
| `locale`     | VARCHAR     | NON      | Clé composite – code langue    |
| `title`      | TEXT        | NON      | Titre localisé                 |
| `description`| TEXT        | OUI      | Description localisée          |

> **Langues supportées :** Français (`fr`) par défaut. L'architecture supporte le multilingue.

### Table `event_audience` (Ciblage par type d'adhésion)

| Colonne             | Type        | Description                        |
|---------------------|-------------|------------------------------------|
| `event_id`          | CHAR(36) FK | FK vers event                      |
| `membership_type_id`| CHAR(36) FK | FK vers membership_type            |

> Si aucune entrée dans `event_audience`, l'événement est **ouvert à tous les membres**.

### Table `event_media`

| Colonne      | Type        | Nullable | Description                     |
|--------------|-------------|----------|---------------------------------|
| `id`         | CHAR(36)    | NON      | Clé primaire                    |
| `event_id`   | CHAR(36) FK | NON      | FK vers event                   |
| `url`        | TEXT        | NON      | URL du média                    |
| `media_type` | TEXT        | NON      | Type : `IMAGE` ou `VIDEO`       |
| `sort_order` | INTEGER     | OUI      | Ordre d'affichage               |
| `deleted_at` | TIMESTAMP   | OUI      | Soft delete                     |

### Table `event_registration`

| Colonne       | Type        | Nullable | Description                                |
|---------------|-------------|----------|--------------------------------------------|
| `id`          | CHAR(36)    | NON      | Clé primaire                               |
| `event_id`    | CHAR(36) FK | NON      | FK vers event                              |
| `member_id`   | CHAR(36) FK | NON      | FK vers member                             |
| `guests_count`| INTEGER     | NON      | Nombre d'invités (hors membre, défaut: 0)  |
| `status`      | VARCHAR     | NON      | `PENDING`, `VALIDATED`, ou `CANCELLED`     |
| `created_at`  | TIMESTAMP   | NON      | Date d'inscription                         |
| `deleted_at`  | TIMESTAMP   | OUI      | Soft delete                                |

### Table `event_attendee`

| Colonne          | Type        | Nullable | Description                           |
|------------------|-------------|----------|---------------------------------------|
| `id`             | CHAR(36)    | NON      | Clé primaire                          |
| `event_id`       | CHAR(36) FK | NON      | FK vers event                         |
| `registration_id`| CHAR(36) FK | NON      | FK vers event_registration            |
| `full_name`      | TEXT        | NON      | Nom complet de l'invité               |
| `email`          | TEXT        | NON      | Email de l'invité                     |
| `phone`          | TEXT        | OUI      | Téléphone                             |
| `deleted_at`     | TIMESTAMP   | OUI      | Soft delete                           |

**Contraintes d'unicité :**
- `(event_id, email)` — un même email ne peut être invité qu'une fois par événement
- `(registration_id, email)` — un même email ne peut apparaître qu'une fois par inscription

> **Note :** Les attendees sont supprimés physiquement (hard delete), contrairement aux autres entités.

---

## Cycle de vie d'un événement

```
Création (backoffice)
       │
       ▼
  ┌─────────────┐
  │   ACTIF     │  ← visible si endAt >= maintenant
  │             │     ET membre dans audience (ou audience vide)
  └──────┬──────┘
         │
         │ endAt < maintenant
         ▼
  ┌─────────────┐
  │   EXPIRÉ    │  ← invisible dans l'API mobile
  └──────┬──────┘
         │
         │ soft delete (deleted_at)
         ▼
  ┌─────────────┐
  │  SUPPRIMÉ   │  ← invisible partout
  └─────────────┘
```

**Filtrage des événements actifs :**
- `deleted_at IS NULL`
- `end_at >= NOW()`
- Le `membership_type` du membre est dans `event_audience`, OU `event_audience` est vide

---

## Inscriptions et participants

### Flux d'inscription d'un membre

```
Membre s'inscrit à un événement
         │
         ├── Membre VISITOR → status = PENDING (attente validation admin)
         │
         └── Autre type     → status = VALIDATED (approuvé automatiquement)
         │
         ▼
  Création EventRegistration
         │
         ├── Ajout d'invités (EventAttendee)
         │     │
         │     ├── Email = membre existant → notification in-app
         │     │
         │     └── Email = non-membre → génération code invitation
         │           • Code format : INV-XXXXXXXX (8 chars UUID)
         │           • Validité : 30 jours
         │           • Email d'invitation envoyé
         │
         ▼
  Inscription active
```

### Calcul de la capacité

```
Places occupées = SUM(guests_count + 1) pour chaque inscription active
Places disponibles = capacity - places occupées
```

- `+1` compte le membre inscrit lui-même
- Si `capacity` est NULL → capacité illimitée
- Validations : `1 (membre) + nb_invités <= places disponibles`

### Statuts d'inscription

| Statut      | Description                                        |
|-------------|----------------------------------------------------|
| `PENDING`   | En attente de validation (membres VISITOR)          |
| `VALIDATED` | Inscription confirmée (auto pour non-VISITOR)       |
| `CANCELLED` | Inscription annulée                                 |

---

## Liaison Événement ↔ Réservation

Quand un événement est associé à un espace, une **réservation** est automatiquement créée via l'API externe. Cette réservation est le pont vers Odoo.

### Table `reservation` — champ ajouté

| Colonne    | Type        | Description                                         |
|------------|-------------|-----------------------------------------------------|
| `event_id` | CHAR(36) FK | FK vers event (UNIQUE — relation 1:1)               |

### Flux de création

```
Système externe (ex: backoffice)
         │
         │ POST /external/event-reservations
         │ Body: { "eventId": "..." }
         │
         ▼
┌─────────────────────────────────┐
│ ExternalEventReservationService │
│                                 │
│ 1. Récupère le "system member"  │
│    (member sans user_id)        │
│                                 │
│ 2. Vérifie que l'event existe   │
│    et a un espace assigné       │
│                                 │
│ 3. Vérifie pas de réservation   │
│    déjà liée                    │
│                                 │
│ 4. Vérifie disponibilité espace │
│    (pas de chevauchement)       │
│                                 │
│ 5. Crée la Reservation locale   │
│    • member = system member     │
│    • status = APPROVED          │
│    • startAt/endAt = de l'event │
│    • totalAmount = 0            │
│    • event_id = lien 1:1        │
│                                 │
│ 6. Sync vers Odoo               │
│    (si member + space ont des   │
│     odoo_id)                    │
└─────────────────────────────────┘
```

### Opérations sur la réservation liée

| Opération    | Endpoint                                    | Comportement                                                                  |
|--------------|---------------------------------------------|-------------------------------------------------------------------------------|
| **Créer**    | `POST /external/event-reservations`         | Crée réservation locale + sync Odoo                                           |
| **Modifier** | `PUT /external/event-reservations/{eventId}`| Si changement d'espace : annule ancienne résa Odoo + crée nouvelle. Si changement de dates : met à jour. |
| **Annuler**  | `DELETE /external/event-reservations/{eventId}` | Status → CANCELLED + annulation Odoo                                      |

### Détection de chevauchement

La vérification de disponibilité d'un espace utilise cette logique :

```sql
-- Trouve les événements qui chevauchent la période demandée
SELECT * FROM event
WHERE space_id = :spaceId
  AND start_at < :endAt
  AND end_at > :startAt
  AND id != :excludeEventId
  AND deleted_at IS NULL
```

---

## Intégration Odoo actuelle

### Ce qui est synchronisé avec Odoo

| Entité              | Synchronisée ? | Méthode                              |
|---------------------|----------------|--------------------------------------|
| Event               | **NON**        | Géré localement uniquement           |
| Event i18n          | **NON**        | Géré localement                      |
| Event Registration  | **NON**        | Géré localement                      |
| Event Attendee      | **NON**        | Géré localement                      |
| Reservation (liée)  | **OUI**        | Via `OdooSyncService`                |

### Méthodes Odoo utilisées pour les réservations liées aux événements

```java
// Création d'une réservation dans Odoo
odooSyncService.syncReservationCreate(reservation, memberId, spaceId, optionsList)
// → Retourne un odoo_id stocké dans la réservation locale

// Mise à jour (changement de dates)
odooSyncService.syncReservationUpdate(reservation, optionsList)

// Annulation
odooSyncService.syncReservationCancel(odooId)
```

### Données envoyées à Odoo pour la réservation

| Champ Reservation     | Description                              |
|-----------------------|------------------------------------------|
| `odooMemberId`        | ID Odoo du system member                 |
| `odooSpaceId`         | ID Odoo de l'espace                      |
| `startAt`             | Date/heure de début (= event.startAt)    |
| `endAt`               | Date/heure de fin (= event.endAt)        |
| `totalAmount`         | Toujours 0 pour les events               |
| `personsCount`        | Toujours 0 pour les events               |
| `status`              | APPROVED                                 |
| `options`             | Liste vide                               |

### System Member

Un membre spécial sans `user_id` (pas de compte utilisateur associé) est utilisé comme porteur de toutes les réservations liées aux événements. Ce membre est créé via migration SQL et sert d'identifiant système pour les opérations automatiques.

---

## API Endpoints

### Endpoints mobiles (authentifiés par Bearer Token)

Base URL : `/api/v1/events`

| Méthode | Endpoint                                  | Description                                  |
|---------|-------------------------------------------|----------------------------------------------|
| GET     | `/api/v1/events`                          | Liste paginée des événements actifs          |
| GET     | `/api/v1/events/{id}`                     | Détail d'un événement                        |
| POST    | `/api/v1/events/{id}/register`            | Inscription à un événement (+ invités)       |
| POST    | `/api/v1/events/{id}/cancel-registration` | Annulation de l'inscription                  |
| GET     | `/api/v1/events/{id}/attendees`           | Liste des invités du membre pour cet event   |
| GET     | `/api/v1/events/invitations`              | Événements où le membre est invité           |
| POST    | `/api/v1/events/{eventId}/attendees`      | Ajout d'invités à une inscription existante  |
| PATCH   | `/api/v1/events/{eventId}/attendees/{id}` | Modification d'un invité                     |
| DELETE  | `/api/v1/events/{eventId}/attendees/{id}` | Suppression d'un invité                      |

### Endpoints externes (authentifiés par API Key)

Base URL : `/external/event-reservations`

| Méthode | Endpoint                                    | Description                            |
|---------|---------------------------------------------|----------------------------------------|
| POST    | `/external/event-reservations`              | Créer une réservation liée à un event  |
| PUT     | `/external/event-reservations/{eventId}`    | Mettre à jour la réservation           |
| DELETE  | `/external/event-reservations/{eventId}`    | Annuler la réservation                 |

### Format de réponse paginée

```json
{
  "totalCount": 42,
  "pagingInfo": {
    "size": 20,
    "pageCount": 3,
    "currentPage": 0,
    "hasPrevious": false,
    "hasNext": true
  },
  "content": [ ... ]
}
```

### Exemple de réponse EventDto

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Soirée Jazz au Lounge",
  "description": "Une soirée musicale avec cocktails...",
  "spaceId": "660e8400-e29b-41d4-a716-446655440001",
  "spaceName": "Le Lounge",
  "startAt": "2026-04-15T19:00:00",
  "endAt": "2026-04-15T23:00:00",
  "capacity": 50,
  "maxGuestsPerMember": 3,
  "availableSeats": 32,
  "isRegistered": false,
  "media": [
    {
      "id": "...",
      "url": "https://storage.example.com/events/jazz-night.jpg",
      "mediaType": "IMAGE",
      "sortOrder": 0
    }
  ],
  "createdAt": "2026-03-20T10:00:00",
  "updatedAt": "2026-03-20T10:00:00"
}
```

---

## Règles métier

### Événements

1. Un événement peut exister **sans espace** (espace optionnel)
2. Un événement est **actif** si `endAt >= maintenant` et `deleted_at IS NULL`
3. Le ciblage par audience est optionnel — pas d'audience = ouvert à tous
4. La capacité est optionnelle — NULL = illimitée
5. Suppression logique (soft delete) sur les événements

### Inscriptions

1. Un membre ne peut s'inscrire qu'**une seule fois** par événement
2. Les membres **VISITOR** ont un statut `PENDING` (validation manuelle requise)
3. Les autres membres sont **automatiquement validés** (`VALIDATED`)
4. Le nombre d'invités ne peut pas dépasser `max_guests_per_member`
5. L'annulation supprime physiquement l'inscription et ses invités

### Invités (Attendees)

1. Un email ne peut apparaître qu'**une seule fois** par événement
2. Si l'email correspond à un membre existant → notification in-app
3. Si l'email est un non-membre → code d'invitation généré (format `INV-XXXXXXXX`, validité 30 jours)
4. Les invités sont supprimés physiquement (hard delete)
5. Un membre non-VISITOR ne peut pas être ajouté comme invité (il doit s'inscrire lui-même)

### Réservations liées

1. Relation **1:1** entre événement et réservation (contrainte UNIQUE sur `event_id`)
2. Toujours créées avec le **system member** comme porteur
3. Status toujours **APPROVED** à la création
4. Montant toujours **0** (pas de facturation)
5. Si changement d'espace → annulation de l'ancienne réservation Odoo + création d'une nouvelle
6. Si changement de dates (même espace) → mise à jour simple
7. Vérification de chevauchement d'espace avant création/modification
