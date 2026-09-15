# Documentation API Webhooks - The Residence

## Vue d'ensemble

Ce document décrit le système de webhooks émis par Odoo vers votre API externe. Les webhooks sont déclenchés automatiquement lors d'événements CRUD (Create, Read, Update, Delete) sur les entités principales de The Residence.

---

## Configuration technique

### Endpoint requis
Votre API doit exposer un endpoint HTTP/HTTPS capable de recevoir des requêtes POST.

### Format des requêtes

**Méthode :** `POST`  
**Content-Type :** `application/json`  
**Authentification :** Header `X-API-Key` (optionnel, configurable)  
**Timeout :** 5 secondes par défaut (configurable entre 1-60s)

### Code de réponse attendu
- **202 Accepted** : Traitement réussi (recommandé)
- **200 OK** : Accepté également
- Autres codes : Considérés comme des échecs et enregistrés dans les logs

---

## Structure générale du payload

Tous les webhooks suivent cette structure JSON :

```json
{
  "event_type": "entity_type.action",
  "event_id": "evt_20260207_a3f5bc12",
  "timestamp": "2026-02-07T14:30:00Z",
  "entity_type": "member|product|order|space|subscription|reservation|pos_category",
  "entity_id": "12345",
  "data": {
    // Champs spécifiques selon l'entité (voir sections ci-dessous)
  }
}
```

### Champs communs

| Champ | Type | Description |
|-------|------|-------------|
| `event_type` | string | Type d'événement (format: `entity.action`) |
| `event_id` | string | Identifiant unique de l'événement |
| `timestamp` | string (ISO 8601) | Date/heure de l'événement |
| `entity_type` | string | Type d'entité concernée |
| `entity_id` | string | ID Odoo de l'enregistrement |
| `data` | object | Données de l'entité |

---

## Types d'événements

### Actions standard
- `created` : Création d'un nouvel enregistrement
- `updated` : Modification d'un enregistrement existant
- `deleted` : Suppression d'un enregistrement

### Actions spécifiques (basées sur les statuts)
- **Membres :** `active`, `suspended`, `expired`, `pending`
- **Réservations :** `confirmed`, `cancelled`, `completed`
- **Abonnements :** `active`, `suspended`, `cancelled`

---

## 1. Membres (res.partner)

### Types d'événements
- `member.created`
- `member.updated`
- `member.deleted`
- `member.active` / `member.suspended` / `member.expired` (selon statut)

### Payload exemple

```json
{
  "event_type": "member.created",
  "event_id": "evt_20260207_f8a3c521",
  "timestamp": "2026-02-07T10:15:00Z",
  "entity_type": "member",
  "entity_id": "456",
  "data": {
    "name": "Jean Dupont",
    "display_name": "Jean Dupont",
    "email": "jean.dupont@example.com",
    "phone": "+225 01 02 03 04 05",
    "mobile": "+225 07 08 09 10 11",
    "active": true,
    
    "x_tr_is_member": true,
    "x_tr_member_status": "active",
    "x_tr_member_type": "individual",
    "x_tr_member_number": "MEM-2026-001",
    "x_tr_member_since": "2026-02-07",
    "x_tr_member_expiry": "2027-02-07",
    "x_tr_credits_balance": 150.0,
    "x_tr_notes": "VIP member",
    
    "image_url": "/web/image/res.partner/456/image_1920"
  }
}
```

### Champs importants

**Champs standards Odoo :**
- `name` : Nom complet
- `email` : Email principal
- `phone` / `mobile` : Numéros de téléphone
- `active` : Statut actif/archivé

**Champs personnalisés The Residence (préfixe `x_tr_`) :**
- `x_tr_is_member` : Identifie un contact comme membre TR (toujours `true` dans les webhooks)
- `x_tr_member_status` : `active`, `suspended`, `expired`, `pending`
- `x_tr_member_type` : `individual`, `corporate`, `student`
- `x_tr_member_number` : Numéro de membre unique
- `x_tr_member_since` : Date d'adhésion (ISO 8601)
- `x_tr_member_expiry` : Date d'expiration (ISO 8601)
- `x_tr_credits_balance` : Solde de crédits (float)
- `x_tr_notes` : Notes internes

**Média :**
- `image_url` : URL relative vers la photo de profil (présent uniquement lors de la création ou si l'image a été modifiée)

### Déclencheurs de webhooks
- Création d'un nouveau membre
- Modification du profil (nom, email, téléphone)
- Changement de statut membre
- Mise à jour de la photo de profil
- Suppression/archivage

---

## 2. Produits & Espaces (product.template)

### Types d'événements
- `product.created` : Produit POS standard
- `space.created` : Espace réservable
- `subscription_plan.created` : Plan d'abonnement
- `*.updated` / `*.deleted` : Modifications et suppressions

### Payload exemple - Produit POS

```json
{
  "event_type": "product.created",
  "event_id": "evt_20260207_d4e9f123",
  "timestamp": "2026-02-07T11:20:00Z",
  "entity_type": "product",
  "entity_id": "789",
  "data": {
    "name": "Café Espresso",
    "display_name": "Café Espresso",
    "list_price": 2.50,
    "default_code": "CAFE-ESP-001",
    "barcode": "5412345678901",
    "available_in_pos": true,
    "active": true,
    
    "x_tr_pos_category": "Beverages",
    "x_tr_cost_price": 0.80,
    "x_tr_stock_alert_threshold": 10,
    
    "image_url": "/web/image/product.template/789/image_1920"
  }
}
```

> **Note importante :** Le champ `image_url` n'est présent dans le payload que lors de la création du produit ou si l'image a été explicitement modifiée lors d'une mise à jour.

### Payload exemple - Espace réservable

```json
{
  "event_type": "space.created",
  "event_id": "evt_20260207_b2c8a456",
  "timestamp": "2026-02-07T12:00:00Z",
  "entity_type": "space",
  "entity_id": "890",
  "data": {
    "name": "Salle de réunion A",
    "display_name": "Salle de réunion A - 8 personnes",
    "list_price": 50.00,
    "active": true,
    
    "x_tr_is_space": true,
    "x_tr_space_type": "meeting_room",
    "x_tr_capacity": 8,
    "x_tr_hourly_rate": 50.00,
    "x_tr_daily_rate": 300.00,
    "x_tr_amenities": "Vidéoprojecteur, Wifi, Tableau blanc",
    "x_tr_available_hours": "08:00-20:00",
    
    "image_url": "/web/image/product.template/890/image_1920"
  }
}
```

### Champs importants

**Produits POS :**
- `list_price` : Prix de vente
- `default_code` : Référence interne
- `barcode` : Code-barres EAN/UPC
- `available_in_pos` : Disponible dans le point de vente
- `x_tr_pos_category` : Catégorie POS personnalisée
- `x_tr_cost_price` : Prix d'achat
- `x_tr_stock_alert_threshold` : Seuil d'alerte stock

**Espaces :**
- `x_tr_is_space` : Identifie un produit comme espace réservable
- `x_tr_space_type` : `meeting_room`, `office`, `event_space`, `desk`
- `x_tr_capacity` : Capacité maximale (personnes)
- `x_tr_hourly_rate` / `x_tr_daily_rate` : Tarifs
- `x_tr_amenities` : Équipements disponibles
- `x_tr_available_hours` : Plages horaires

---

## 3. Commandes POS (pos.order)

### Types d'événements
- `order.created` : Nouvelle commande POS
- `order.updated` : Modification de commande
- `order.deleted` : Annulation de commande

### Payload exemple

```json
{
  "event_type": "order.created",
  "event_id": "evt_20260207_e5f1a789",
  "timestamp": "2026-02-07T15:45:00Z",
  "entity_type": "order",
  "entity_id": "1234",
  "data": {
    "name": "Order 00001-001-0001",
    "x_tr_order_ref": "POS-2026-001",
    "x_tr_order_date": "2026-02-07T15:45:00Z",
    "x_tr_customer_id": 456,
    "x_tr_total_amount": 15.50,
    "x_tr_payment_method": "card",
    "x_tr_order_items": [
      {
        "product_id": 789,
        "product_name": "Café Espresso",
        "quantity": 2,
        "unit_price": 2.50,
        "subtotal": 5.00
      },
      {
        "product_id": 790,
        "product_name": "Croissant",
        "quantity": 3,
        "unit_price": 3.50,
        "subtotal": 10.50
      }
    ],
    "x_tr_session_id": "SESSION-2026-02-07-001"
  }
}
```

### Champs importants
- `x_tr_order_ref` : Référence de commande unique
- `x_tr_customer_id` : ID du membre/client (res.partner)
- `x_tr_total_amount` : Montant total TTC
- `x_tr_payment_method` : `cash`, `card`, `credits`, `mobile_money`
- `x_tr_order_items` : Liste des articles (array)
- `x_tr_session_id` : Référence de session POS

---

## 4. Réservations (sale.order avec x_tr_is_reservation)

### Types d'événements
- `reservation.created`
- `reservation.confirmed` / `reservation.cancelled` / `reservation.completed`
- `reservation.updated`
- `reservation.deleted`

### Payload exemple

```json
{
  "event_type": "reservation.confirmed",
  "event_id": "evt_20260207_c3d8f567",
  "timestamp": "2026-02-07T16:00:00Z",
  "entity_type": "reservation",
  "entity_id": "5678",
  "data": {
    "name": "RES/2026/001",
    "x_tr_is_reservation": true,
    "x_tr_reservation_status": "confirmed",
    "x_tr_member_id": 456,
    "x_tr_space_id": 890,
    "x_tr_start_datetime": "2026-02-10T09:00:00Z",
    "x_tr_end_datetime": "2026-02-10T12:00:00Z",
    "x_tr_duration_hours": 3.0,
    "x_tr_total_price": 150.00,
    "x_tr_payment_status": "paid",
    "x_tr_attendees": 6,
    "x_tr_notes": "Réunion de direction"
  }
}
```

### Champs importants
- `x_tr_is_reservation` : Toujours `true`
- `x_tr_reservation_status` : `draft`, `confirmed`, `cancelled`, `completed`
- `x_tr_member_id` : ID du membre réservant
- `x_tr_space_id` : ID de l'espace (product.template)
- `x_tr_start_datetime` / `x_tr_end_datetime` : Période de réservation
- `x_tr_duration_hours` : Durée totale
- `x_tr_payment_status` : `pending`, `paid`, `refunded`
- `x_tr_attendees` : Nombre de participants

---

## 5. Abonnements (sale.order avec x_tr_is_subscription)

### Types d'événements
- `subscription.created`
- `subscription.active` / `subscription.suspended` / `subscription.cancelled`
- `subscription.updated`

### Payload exemple

```json
{
  "event_type": "subscription.active",
  "event_id": "evt_20260207_a1b2c3d4",
  "timestamp": "2026-02-07T17:00:00Z",
  "entity_type": "subscription",
  "entity_id": "9012",
  "data": {
    "name": "SUB/2026/001",
    "x_tr_is_subscription": true,
    "x_tr_subscription_status": "active",
    "x_tr_member_id": 456,
    "x_tr_subscription_plan_id": 901,
    "x_tr_start_date": "2026-02-07",
    "x_tr_end_date": "2027-02-07",
    "x_tr_billing_period": "monthly",
    "x_tr_monthly_amount": 150.00,
    "x_tr_credits_included": 20,
    "x_tr_auto_renew": true,
    "x_tr_next_billing_date": "2026-03-07"
  }
}
```

### Champs importants
- `x_tr_is_subscription` : Toujours `true`
- `x_tr_subscription_status` : `active`, `suspended`, `cancelled`, `expired`
- `x_tr_subscription_plan_id` : ID du plan (product.template)
- `x_tr_billing_period` : `monthly`, `quarterly`, `yearly`
- `x_tr_monthly_amount` : Montant de facturation
- `x_tr_credits_included` : Crédits inclus par période
- `x_tr_auto_renew` : Renouvellement automatique

---

## 6. Catégories POS (pos.category)

### Types d'événements
- `pos_category.created`
- `pos_category.updated`
- `pos_category.deleted`

### Payload exemple

```json
{
  "event_type": "pos_category.created",
  "event_id": "evt_20260207_f9e8d7c6",
  "timestamp": "2026-02-07T18:00:00Z",
  "entity_type": "pos_category",
  "entity_id": "123",
  "data": {
    "name": "Boissons Chaudes",
    "x_tr_category_code": "HOT-DRINKS",
    "x_tr_display_order": 1,
    "x_tr_color": "#FF5733",
    "image_url": "/web/image/pos.category/123/image_1920"
  }
}
```

---

## Gestion des erreurs

### Côté Odoo
- **Timeout :** Si votre API ne répond pas dans le délai configuré (5s par défaut), l'appel est abandonné
- **Logging :** Tous les webhooks sont enregistrés dans `webhook.log` avec :
  - Payload envoyé
  - Code de réponse HTTP
  - Corps de la réponse
  - Timestamp

### Recommandations pour votre API
1. **Répondre rapidement** : Idéalement < 2 secondes
2. **Traitement asynchrone** : Acceptez le webhook (202), puis traitez en arrière-plan
3. **Gestion des doublons** : Utilisez `event_id` pour détecter les rejeux
4. **Retry stratégique** : Odoo ne gère pas les retries automatiques

---

## Sécurité

### Authentification
- Header `X-API-Key` contient votre clé secrète (configurable dans Odoo)
- Validez systématiquement ce header

### Validation des données
- Vérifiez l'intégrité du JSON
- Validez les types de données (`entity_id`, `timestamp`)
- Rejetez les événements inconnus ou malformés

### HTTPS obligatoire
Les URLs en `http://` sont bloquées en production (contrainte Odoo).

---

## Exemples d'implémentation

### Python (Flask)

```python
from flask import Flask, request, jsonify
import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)

EXPECTED_API_KEY = "votre_cle_secrete_ici"

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    # 1. Vérification authentification
    api_key = request.headers.get('X-API-Key')
    if api_key != EXPECTED_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    # 2. Parsing du payload
    try:
        payload = request.get_json()
        event_type = payload.get('event_type')
        entity_id = payload.get('entity_id')
        data = payload.get('data', {})
        
        logger.info(f"Received webhook: {event_type} for entity {entity_id}")
        
        # 3. Traitement selon le type d'événement
        if event_type.startswith('member.'):
            process_member_event(event_type, entity_id, data)
        elif event_type.startswith('product.'):
            process_product_event(event_type, entity_id, data)
        # ... autres types
        
        return jsonify({"status": "accepted"}), 202
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return jsonify({"error": "Internal error"}), 500

def process_member_event(event_type, entity_id, data):
    # Votre logique métier ici
    if event_type == 'member.created':
        # Créer le membre dans votre système
        pass
    elif event_type == 'member.updated':
        # Mettre à jour le membre
        pass
    # ...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### Node.js (Express)

```javascript
const express = require('express');
const app = express();

const EXPECTED_API_KEY = 'votre_cle_secrete_ici';

app.use(express.json());

app.post('/webhook', (req, res) => {
    // 1. Authentification
    const apiKey = req.headers['x-api-key'];
    if (apiKey !== EXPECTED_API_KEY) {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    
    // 2. Traitement
    const { event_type, entity_id, data } = req.body;
    console.log(`Webhook received: ${event_type} for ${entity_id}`);
    
    // 3. Dispatch asynchrone
    processWebhookAsync(event_type, entity_id, data)
        .catch(err => console.error('Processing error:', err));
    
    // 4. Réponse immédiate
    return res.status(202).json({ status: 'accepted' });
});

async function processWebhookAsync(event_type, entity_id, data) {
    if (event_type.startsWith('member.')) {
        await processMemberEvent(event_type, entity_id, data);
    }
    // ...
}

app.listen(3000, () => {
    console.log('Webhook server running on port 3000');
});
```

---

## Tests et debugging

### Endpoint de test
Configurez temporairement l'URL vers un service comme :
- **RequestBin** : https://requestbin.com
- **Webhook.site** : https://webhook.site
- **Ngrok** : Pour exposer votre serveur local

### Logs Odoo
Tous les webhooks sont consultables dans :
- **Menu Odoo :** Configuration → Technique → Historique Webhooks
- **Modèle :** `webhook.log`

### Données de test
Utilisez l'environnement de développement Odoo pour créer/modifier des entités et observer les webhooks en temps réel.

---

## Exemples réels de production

Voici des exemples de webhooks réellement envoyés par le système Odoo :

### Exemple 1 : Création d'une commande (sale.order)

```json
{
  "event_type": "order.updated",
  "event_id": "evt_20260207_63e861f4",
  "timestamp": "2026-02-07T02:53:52Z",
  "entity_type": "order",
  "entity_id": "5",
  "data": {
    "x_tr_uuid": false,
    "x_tr_is_reservation": false,
    "x_tr_reservation_status": "PENDING",
    "x_tr_space_id": false,
    "x_tr_start_time": false,
    "x_tr_end_time": false,
    "x_tr_guest_count": 0,
    "x_tr_notes": false,
    "x_tr_rejection_reason": false,
    "x_tr_qr_token": false,
    "x_tr_invitee_ids": false,
    "x_tr_option_ids": false,
    "x_tr_is_subscription": false,
    "x_tr_subscription_status": "ACTIVE",
    "x_tr_plan_id": false,
    "x_tr_billing_period": "MONTHLY",
    "x_tr_auto_renew": true,
    "x_tr_sub_start_date": false,
    "x_tr_sub_end_date": false
  }
}
```

**Observations :**
- Les champs non définis retournent `false` (pas `null`)
- Le statut par défaut "PENDING" et "ACTIVE" sont présents même si non utilisés
- Aucun champ `image_url` car non applicable aux commandes

### Exemple 2 : Mise à jour d'un espace (product.template)

```json
{
  "event_type": "space.updated",
  "event_id": "evt_20260207_5dc7e8f1",
  "timestamp": "2026-02-07T04:29:09Z",
  "entity_type": "space",
  "entity_id": "2263",
  "data": {
    "x_tr_is_space": true,
    "x_tr_space_uuid": "c2c72b02-7625-4828-8378-adfa15859a57",
    "x_tr_space_capacity": 2,
    "x_tr_space_type_id": 7,
    "x_tr_space_description": false,
    "x_tr_is_subscription_plan": false,
    "x_tr_membership_type_id": false,
    "x_tr_duration_months": 1,
    "name": "Chambre Assiniet",
    "display_name": "Chambre Assiniet",
    "list_price": 196000.0,
    "available_in_pos": true,
    "barcode": false,
    "default_code": false,
    "active": true
  }
}
```

**Observations :**
- Code HTTP retourné : **401** (authentification requise)
- Champ `x_tr_space_uuid` : UUID unique généré côté Odoo
- `list_price` en float avec précision décimale
- Pas de champ `image_url` → l'image n'a pas été modifiée

### Exemple 3 : Mise à jour d'un espace (deuxième événement)

```json
{
  "event_type": "space.updated",
  "event_id": "evt_20260207_02b8b007",
  "timestamp": "2026-02-07T04:34:18Z",
  "entity_type": "space",
  "entity_id": "2263",
  "data": {
    "x_tr_is_space": true,
    "x_tr_space_uuid": "c2c72b02-7625-4828-8378-adfa15859a57",
    "x_tr_space_capacity": 2,
    "x_tr_space_type_id": 7,
    "x_tr_space_description": false,
    "x_tr_is_subscription_plan": false,
    "x_tr_membership_type_id": false,
    "x_tr_duration_months": 1,
    "name": "Chambre Assinie",
    "display_name": "Chambre Assinie",
    "list_price": 196000.0,
    "available_in_pos": true,
    "barcode": false,
    "default_code": false,
    "active": true
  }
}
```

**Observations :**
- Même entité (ID 2263), événement différent (5 minutes plus tard)
- Changement détecté : `"name": "Chambre Assiniet"` → `"Chambre Assinie"`
- Pas de champ `image_url` → seul le nom a été modifié

### Exemple 4 : Mise à jour d'un produit standard avec image

```json
{
  "event_type": "product.updated",
  "event_id": "evt_20260207_c2c3750d",
  "timestamp": "2026-02-07T04:46:19Z",
  "entity_type": "product",
  "entity_id": "23",
  "data": {
    "x_tr_is_space": false,
    "x_tr_space_uuid": false,
    "x_tr_space_capacity": 0,
    "x_tr_space_type_id": false,
    "x_tr_space_description": false,
    "x_tr_is_subscription_plan": false,
    "x_tr_membership_type_id": false,
    "x_tr_duration_months": 1,
    "name": "Annulation gratuite",
    "display_name": "Annulation gratuite",
    "list_price": 50.0,
    "available_in_pos": false,
    "barcode": false,
    "default_code": false,
    "active": true,
    "image_url": "/web/image/product.template/23/image_1920"
  }
}
```

**Observations :**
- Le champ `image_url` **est présent** → l'image a été ajoutée/modifiée
- Produit non disponible en POS : `"available_in_pos": false`
- Tous les champs `x_tr_is_*` retournent `false` → produit standard

### Analyse des patterns

#### Gestion des valeurs vides
- **false** : Champ non défini, relation vide, ou booléen faux
- **0** : Valeur numérique zéro (integer)
- **0.0** : Valeur numérique zéro (float)

#### Champs conditionnels
| Champ | Présent quand |
|-------|---------------|
| `image_url` | Image créée/modifiée |
| `x_tr_space_*` | `x_tr_is_space = true` |
| `x_tr_subscription_*` | `x_tr_is_subscription = true` |

#### Codes HTTP observés
- **202** : Succès (recommandé à implémenter)
- **401** : Échec d'authentification (vérifier `X-API-Key`)

---

## FAQ

### Q : Les webhooks sont-ils synchrones ?
**R :** Oui, Odoo attend votre réponse HTTP. Privilégiez un traitement asynchrone côté API.

### Q : Que se passe-t-il si mon API est indisponible ?
**R :** Le webhook est enregistré dans les logs Odoo comme échec. Aucun retry automatique.

### Q : Comment éviter les doublons ?
**R :** Utilisez le champ `event_id` (unique) ou la combinaison `entity_type` + `entity_id` + `timestamp`.

### Q : Les images sont-elles envoyées en base64 ?
**R :** Non, uniquement l'URL relative (`image_url`). Récupérez l'image via `https://votre-odoo.com/web/image/...`  
**Important :** Le champ `image_url` n'apparaît que si l'image a été créée ou modifiée lors de l'événement.

### Q : Pourquoi certains champs valent `false` au lieu de `null` ?
**R :** C'est le comportement par défaut d'Odoo. Traitez `false` comme une valeur vide/nulle dans votre logique métier.

### Q : Comment différencier un produit d'un espace d'un plan d'abonnement ?
**R :** Utilisez les flags :
- `x_tr_is_space = true` → Espace réservable
- `x_tr_is_subscription_plan = true` → Plan d'abonnement
- Les deux à `false` → Produit POS standard

### Q : Comment tester sans impacter la production ?
**R :** Utilisez la base de données de test Odoo et pointez vers un endpoint de staging.

---

## Support

Pour toute question technique :
- **Email :** support@theresidence.com
- **Documentation Odoo :** https://odoo.com/documentation

**Version du document :** 1.0  
**Dernière mise à jour :** 7 février 2026
