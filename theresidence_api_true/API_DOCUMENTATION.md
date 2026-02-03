# Documentation API The Residence - Odoo 19

## Table des matières
1. [API Subscriptions (Abonnements)](#api-subscriptions)
2. [Service Webhook (Notifications sortantes)](#service-webhook)
3. [Guide d'intégration](#guide-dintégration)

---

## API Subscriptions

### Vue d'ensemble
L'API Subscriptions permet de gérer les abonnements des membres dans Odoo 19. Elle utilise les champs standards d'Odoo (`is_subscription`, `subscription_state`, `plan_id`) pour une meilleure compatibilité.

### Endpoints disponibles

#### 1. Lister les abonnements
```http
GET /api/v1/subscriptions
```

**Paramètres de requête:**
- `page` (int, optionnel): Numéro de page (défaut: 0)
- `size` (int, optionnel): Nombre d'éléments par page (défaut: 20, max: 100)
- `memberId` (string, optionnel): UUID du membre pour filtrer
- `status` (string, optionnel): Statut de l'abonnement
- `planId` (string, optionnel): UUID du plan d'abonnement

**Statuts possibles:**
- `draft` → Odoo: `1_draft`
- `active` ou `progress` → Odoo: `3_progress`
- `paused` → Odoo: `4_paused`
- `expired` → Odoo: `5_expired`
- `cancelled` → Odoo: `6_closed`
- `renewal` → Odoo: `2_renewal`
- `upsell` → Odoo: `7_upsell`

**Réponse exemple:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid-123",
      "memberId": "member-uuid",
      "planId": "plan-uuid",
      "status": "active",
      "startDate": "2026-01-01",
      "nextBillingDate": "2026-02-01"
    }
  ],
  "pagination": {
    "page": 0,
    "size": 20,
    "total": 150
  }
}
```

---

#### 2. Récupérer un abonnement
```http
GET /api/v1/subscriptions/{subscription_id}
```

**Paramètres:**
- `subscription_id`: UUID ou ID Odoo de l'abonnement

**Réponse:**
```json
{
  "success": true,
  "data": {
    "id": "uuid-123",
    "memberId": "member-uuid",
    "memberName": "John Doe",
    "planId": "plan-uuid",
    "planName": "Abonnement CEO",
    "status": "active",
    "startDate": "2026-01-01",
    "nextBillingDate": "2026-02-01",
    "amount": 50000.00
  }
}
```

---

#### 3. Créer un abonnement
```http
POST /api/v1/subscriptions
```

**Corps de la requête:**
```json
{
  "memberId": "member-uuid-123",
  "planId": "plan-uuid-456",
  "productName": "Abonnement CEO",
  "quantity": 1,
  "price": 50000.00,
  "startDate": "2026-02-01",
  "autoConfirm": true
}
```

**Champs:**
- `memberId` (requis): UUID du membre
- `planId` (optionnel): UUID du plan (par défaut: premier plan "mensuel" trouvé)
- `productName` (optionnel): Nom du produit (par défaut: "Abonnement CEO")
- `quantity` (optionnel): Quantité (par défaut: 1)
- `price` (optionnel): Prix unitaire (par défaut: prix du produit)
- `startDate` (optionnel): Date de début
- `autoConfirm` (optionnel): Confirmer automatiquement (par défaut: true)

**Réponse:**
```json
{
  "success": true,
  "data": {
    "id": "new-uuid-789",
    "memberId": "member-uuid-123",
    "status": "active"
  }
}
```

**Codes d'erreur:**
- `400 MISSING_MEMBER_ID`: memberId manquant
- `404 MEMBER_NOT_FOUND`: Membre introuvable
- `404 PRODUCT_NOT_FOUND`: Produit d'abonnement introuvable
- `404 PLAN_NOT_FOUND`: Aucun plan d'abonnement trouvé

---

#### 4. Mettre en pause un abonnement
```http
POST /api/v1/subscriptions/{subscription_id}/pause
```

**Effet:** Change le statut vers `4_paused`

**Réponse:**
```json
{
  "success": true,
  "data": {
    "id": "uuid-123",
    "status": "paused"
  }
}
```

---

#### 5. Reprendre un abonnement
```http
POST /api/v1/subscriptions/{subscription_id}/resume
```

**Effet:** Change le statut vers `3_progress`

**Réponse:**
```json
{
  "success": true,
  "data": {
    "id": "uuid-123",
    "status": "active"
  }
}
```

---

#### 6. Annuler un abonnement
```http
POST /api/v1/subscriptions/{subscription_id}/cancel
```

**Effet:** Change le statut vers `6_closed`

**Réponse:**
```json
{
  "success": true,
  "data": {
    "id": "uuid-123",
    "status": "cancelled"
  }
}
```

---

#### 7. Récupérer les abonnements d'un membre
```http
GET /api/v1/members/{member_id}/subscriptions
```

**Paramètres:**
- `member_id`: UUID ou ID Odoo du membre
- Paramètres de pagination: `page`, `size`

**Réponse:** Identique à `GET /api/v1/subscriptions`

---

## Service Webhook

### Vue d'ensemble
Le Service Webhook envoie des notifications en temps réel vers votre API externe lorsque des événements importants se produisent dans Odoo (création, modification, annulation d'abonnements, etc.).

### Architecture

#### Flux de traitement
```
Événement Odoo → WebhookService.trigger_event() → Queue → Envoi HTTP → Logs
```

1. **Déclenchement**: Un événement se produit (ex: création d'abonnement)
2. **Mapping**: L'événement interne est mappé vers un événement API
3. **Queue**: L'événement est ajouté à la file d'attente
4. **Envoi**: Tentative d'envoi immédiat vers l'API externe
5. **Retry**: En cas d'échec, tentatives automatiques avec délai exponentiel
6. **Logs**: Tous les essais sont enregistrés pour suivi

---

### Événements supportés

#### Événements Abonnements (Subscriptions)

| Événement Odoo | Événement API | Déclencheur |
|----------------|---------------|-------------|
| `SUBSCRIPTION_CREATED` | `subscription.created` | Création d'un nouvel abonnement |
| `SUBSCRIPTION_UPDATED` | `subscription.updated` | Modification d'un abonnement |
| `SUBSCRIPTION_CANCELLED` | `subscription.cancelled` | Annulation d'un abonnement |
| `SUBSCRIPTION_STATUS_CHANGED` (→ ACTIVE) | `subscription.activated` | Premier passage à actif |
| `SUBSCRIPTION_STATUS_CHANGED` (PAUSED → ACTIVE) | `subscription.resumed` | Reprise après pause |
| `SUBSCRIPTION_STATUS_CHANGED` (→ PAUSED) | `subscription.paused` | Mise en pause |

#### Événements Commandes (Orders)

| Événement Odoo | Événement API | Déclencheur |
|----------------|---------------|-------------|
| `ORDER_STATUS_CHANGED` (→ CONFIRMED) | `order.confirmed` | Confirmation de commande |
| `ORDER_STATUS_CHANGED` (→ READY) | `order.ready` | Commande prête |
| `ORDER_STATUS_CHANGED` (→ COMPLETED) | `order.completed` | Commande terminée |
| `ORDER_CANCELLED` | `order.cancelled` | Annulation de commande |

#### Événements Réservations (Reservations)

| Événement Odoo | Événement API | Déclencheur |
|----------------|---------------|-------------|
| `RESERVATION_STATUS_CHANGED` (→ APPROVED) | `reservation.approved` | Réservation approuvée |
| `RESERVATION_STATUS_CHANGED` (→ REJECTED) | `reservation.rejected` | Réservation rejetée |
| `RESERVATION_STATUS_CHANGED` (→ CHECKED_IN) | `reservation.checked_in` | Check-in effectué |
| `RESERVATION_CANCELLED` | `reservation.cancelled` | Réservation annulée |

#### Événements Espaces (Spaces)

| Événement Odoo | Événement API | Déclencheur |
|----------------|---------------|-------------|
| `SPACE_CREATED` | `space.created` | Création d'espace |
| `SPACE_UPDATED` | `space.updated` | Modification d'espace |
| `SPACE_DELETED` | `space.deleted` | Suppression d'espace |
| `SPACE_AVAILABILITY_CHANGED` | `space.availability_changed` | Changement de disponibilité |

#### Événements Catégories POS

| Événement Odoo | Événement API | Déclencheur |
|----------------|---------------|-------------|
| `POS_CATEGORY_CREATED` | `pos_category.created` | Création de catégorie |
| `POS_CATEGORY_UPDATED` | `pos_category.updated` | Modification de catégorie |
| `POS_CATEGORY_DELETED` | `pos_category.deleted` | Suppression de catégorie |

#### Événements Membres (Members)

| Événement Odoo | Événement API | Déclencheur |
|----------------|---------------|-------------|
| `MEMBER_CREATED` | `member.created` | Création de membre |
| `MEMBER_UPDATED` | `member.updated` | Modification de membre |
| `MEMBER_DELETED` | `member.deleted` | Suppression de membre |
| `MEMBER_MEMBERSHIP_CHANGED` | `member.membership_changed` | Changement d'adhésion |

---

### Format du Webhook

#### Structure du payload
```json
{
  "event_type": "subscription.created",
  "event_id": "evt_1707234567_abc123",
  "timestamp": "2026-02-02T14:30:00Z",
  "entity_type": "subscription",
  "entity_id": "sub-uuid-123",
  "data": {
    "memberId": "member-uuid-456",
    "memberName": "John Doe",
    "planId": "plan-uuid-789",
    "planName": "Abonnement CEO",
    "status": "active",
    "startDate": "2026-02-01",
    "amount": 50000.00
  }
}
```

#### Headers envoyés
```http
Content-Type: application/json
X-API-Key: votre-clé-api
User-Agent: Odoo-TheResidence-Webhook/1.0
```

---

### Configuration

#### Paramètres de configuration

| Paramètre | Type | Description | Défaut |
|-----------|------|-------------|--------|
| `base_url` | String | URL de base de votre API | - |
| `api_key` | String | Clé API pour authentification | - |
| `is_active` | Boolean | Activer/Désactiver les webhooks | False |
| `timeout` | Integer | Timeout en secondes | 10 |
| `max_retries` | Integer | Nombre max de tentatives | 3 |
| `retry_delays` | String | Délais entre tentatives (CSV) | "5,30,300" |
| `send_created_events` | Boolean | Envoyer les événements de création | True |
| `enable_debug_logs` | Boolean | Logs détaillés | False |

#### Endpoint de réception
```
{base_url}/v1/external/webhooks/odoo
```

**Votre API doit:**
- Répondre avec HTTP `202 Accepted` pour un succès
- Traiter les webhooks de manière asynchrone
- Être idempotente (utiliser `event_id` pour éviter les doublons)

---

### Gestion des erreurs et retry

#### Stratégie de retry
1. **Première tentative**: Immédiate
2. **Retry 1**: Après 5 secondes (configurable)
3. **Retry 2**: Après 30 secondes
4. **Retry 3**: Après 5 minutes
5. **Échec définitif**: Après 3 tentatives (configurable)

#### Codes de réponse traités

| Code HTTP | Action |
|-----------|--------|
| `202` | Succès ✓ |
| `4xx` | Échec définitif (pas de retry) |
| `5xx` | Retry automatique |
| Timeout | Retry automatique |
| Connection Error | Retry automatique |

---

### Utilisation dans le code

#### Déclencher un webhook manuellement

```python
# Exemple: Déclencher un événement pour un abonnement
self.env['theresidence.webhook.service'].trigger_event(
    internal_event='SUBSCRIPTION_CREATED',
    entity_type='subscription',
    entity_id=subscription.x_tr_uuid,
    data={
        'memberId': subscription.partner_id.x_tr_uuid,
        'memberName': subscription.partner_id.name,
        'planId': subscription.plan_id.x_tr_space_uuid,
        'planName': subscription.plan_id.name,
        'status': 'active',
        'startDate': str(subscription.start_date),
        'amount': subscription.amount_total,
    }
)
```

#### Changement de statut

```python
# Déclencher un événement de changement de statut
self.env['theresidence.webhook.service'].trigger_event(
    internal_event='SUBSCRIPTION_STATUS_CHANGED',
    entity_type='subscription',
    entity_id=subscription.x_tr_uuid,
    old_status='PAUSED',
    new_status='ACTIVE',
    data={...}
)
```

---

### Monitoring et statistiques

#### Obtenir les statistiques

```python
stats = self.env['theresidence.webhook.service'].get_statistics()
```

**Retourne:**
```python
{
    'total_sent': 1250,           # Total envoyés avec succès
    'total_pending': 5,            # En attente d'envoi
    'total_failed': 12,            # Échoués définitivement
    'last_24h_sent': 45,           # Envoyés dans les 24h
    'last_24h_failed': 2,          # Échoués dans les 24h
}
```

#### Traiter manuellement la queue

```python
# Traiter jusqu'à 50 webhooks en attente
count = self.env['theresidence.webhook.service']._process_queue()
```

---

### Tester la connexion

#### Via l'interface Odoo
1. Aller dans **Configuration → Webhooks**
2. Cliquer sur **Tester la connexion**
3. Vérifier le résultat

#### Via code

```python
config = self.env['theresidence.webhook.config'].get_active_config()
result = self.env['theresidence.webhook.service']._send_test_webhook(config)

if result['success']:
    print(f"✓ {result['message']}")
else:
    print(f"✗ {result['error']}")
```

---

## Guide d'intégration

### Étape 1: Configurer l'API externe

**Créer un endpoint webhook:**
```python
@app.post("/v1/external/webhooks/odoo")
async def receive_odoo_webhook(request: Request):
    # Valider la clé API
    api_key = request.headers.get("X-API-Key")
    if api_key != YOUR_API_KEY:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    
    # Récupérer le payload
    payload = await request.json()
    event_type = payload.get("event_type")
    event_id = payload.get("event_id")
    
    # Vérifier les doublons (idempotence)
    if await is_event_already_processed(event_id):
        return JSONResponse(status_code=202, content={"status": "already_processed"})
    
    # Traiter l'événement de manière asynchrone
    await queue_event_processing(payload)
    
    # Répondre immédiatement
    return JSONResponse(status_code=202, content={"status": "accepted"})
```

---

### Étape 2: Configurer Odoo

1. **Installer le module** `theresidence_api`
2. **Configurer les webhooks:**
   - Base URL: `https://votre-api.com`
   - API Key: `votre-clé-secrète`
   - Activer: ✓
   - Timeout: 10s
   - Max Retries: 3

3. **Tester la connexion** via le bouton dans l'interface

---

### Étape 3: Créer des abonnements automatiquement

**Créer un bouton dans res.partner:**

```python
def action_generate_ceo_subscriptions(self):
    """Crée automatiquement des abonnements pour tous les membres"""
    all_members = self.env['res.partner'].search([
        ('x_tr_is_member', '=', True)
    ])
    
    for member in all_members:
        # Créer l'abonnement
        subscription = self.env['sale.order'].create({
            'partner_id': member.id,
            'is_subscription': True,
            'plan_id': plan.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1,
                'product_uom_id': product.uom_id.id,
                'price_unit': product.list_price,
            })],
        })
        
        subscription.action_confirm()
```

---

### Étape 4: Gérer les webhooks reçus

**Exemple de traitement:**

```python
async def process_subscription_created(payload):
    subscription_id = payload['entity_id']
    data = payload['data']
    
    # Enregistrer dans votre base
    await db.subscriptions.insert({
        'odoo_id': subscription_id,
        'member_id': data['memberId'],
        'plan_id': data['planId'],
        'status': data['status'],
        'start_date': data['startDate'],
        'amount': data['amount'],
        'synced_at': datetime.now()
    })
    
    # Déclencher d'autres actions
    await send_welcome_email(data['memberId'])
    await update_member_benefits(data['memberId'])
```

---

### Bonnes pratiques

#### Sécurité
- ✓ Toujours valider la clé API
- ✓ Utiliser HTTPS uniquement
- ✓ Ne jamais exposer les clés dans les logs
- ✓ Limiter le taux de requêtes (rate limiting)

#### Performance
- ✓ Traiter les webhooks de manière asynchrone
- ✓ Répondre rapidement (< 5 secondes)
- ✓ Utiliser une queue pour le traitement
- ✓ Éviter les opérations bloquantes

#### Fiabilité
- ✓ Implémenter l'idempotence avec `event_id`
- ✓ Logger tous les webhooks reçus
- ✓ Gérer les doublons
- ✓ Monitorer les échecs

#### Monitoring
- ✓ Alerter sur les webhooks échoués
- ✓ Surveiller les délais de traitement
- ✓ Vérifier régulièrement les statistiques Odoo
- ✓ Tester périodiquement la connexion

---

## Codes d'erreur

### API Subscriptions

| Code | Message | Description |
|------|---------|-------------|
| `400` | `MISSING_MEMBER_ID` | Le champ memberId est requis |
| `400` | `INVALID_REQUEST` | Données de requête invalides |
| `400` | `INVALID_STATUS_TRANSITION` | Transition de statut impossible |
| `404` | `SUBSCRIPTION_NOT_FOUND` | Abonnement introuvable |
| `404` | `MEMBER_NOT_FOUND` | Membre introuvable |
| `404` | `PRODUCT_NOT_FOUND` | Produit d'abonnement introuvable |
| `404` | `PLAN_NOT_FOUND` | Plan d'abonnement introuvable |

### Service Webhook

| État | Description |
|------|-------------|
| `pending` | En attente d'envoi |
| `sent` | Envoyé avec succès (HTTP 202) |
| `failed` | Échoué (après tous les retries) |

---

## Support

Pour toute question ou problème:
1. Vérifier les logs Odoo: `theresidence.webhook.service`
2. Consulter la queue des webhooks dans l'interface Odoo
3. Tester la connexion depuis la configuration
4. Vérifier les statistiques de webhooks

---

## Changelog

### Version 1.0.0 (Odoo 19)
- ✓ Migration vers champs standards Odoo 19
- ✓ Support de `is_subscription`, `subscription_state`, `plan_id`
- ✓ Correction du champ `product_uom_id`
- ✓ API REST complète pour les abonnements
- ✓ Service webhook avec retry automatique
- ✓ Support de 6 types d'entités (subscriptions, orders, reservations, spaces, pos_categories, members)
- ✓ Logs et monitoring complets
