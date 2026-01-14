# The Residence - External API Documentation

This document describes the External API for integrating third-party systems (such as Odoo) with The Residence platform.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Base URL](#base-url)
3. [Common Headers](#common-headers)
4. [Error Handling](#error-handling)
5. [Pagination](#pagination)
6. [API Endpoints](#api-endpoints)
   - [Reference Data](#reference-data)
   - [Reservations](#reservations)
   - [Orders](#orders)
   - [Webhooks](#webhooks)
7. [Webhook Events](#webhook-events)
8. [Webhook Security](#webhook-security)

---

## Authentication

All external API endpoints require authentication via an API key passed in the request header.

```
X-API-Key: your-api-key-here
```

Contact the system administrator to obtain your API key.

### Example Request

```bash
curl -X GET "https://api.theresidence.com/v1/external/reference/spaces" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json"
```

### Authentication Errors

| Status Code | Error | Description |
|-------------|-------|-------------|
| 401 | Unauthorized | Missing or invalid API key |
| 403 | Forbidden | API key does not have access to this resource |

---

## Base URL

| Environment | Base URL                            |
|-------------|-------------------------------------|
| Production | `https://api.laresidence-abidjan.com/v1/external`   |

---

## Common Headers

| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | Yes | Your API authentication key |
| `Content-Type` | Yes (for POST/PUT) | `application/json` |
| `Accept-Language` | No | Locale for i18n content (default: `fr`) |

---

## Error Handling

All errors follow a consistent format:

```json
{
  "success": false,
  "message": "Error description",
  "errorCode": "ERROR_CODE",
  "timestamp": "2026-01-12T10:00:00Z"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NOT_FOUND` | 404 | Resource not found |
| `INVALID_REQUEST` | 400 | Invalid request parameters |
| `INVALID_STATUS_TRANSITION` | 400 | Status change not allowed |
| `MEMBER_NOT_FOUND` | 404 | Member does not exist |
| `SPACE_NOT_FOUND` | 404 | Space does not exist |
| `ORDER_NOT_FOUND` | 404 | Order does not exist |
| `RESERVATION_NOT_FOUND` | 404 | Reservation does not exist |

---

## Pagination

List endpoints support pagination with the following query parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | integer | 0 | Page number (0-indexed) |
| `size` | integer | 20 | Items per page (max: 100) |
| `sort` | string | varies | Sort field and direction (e.g., `createdAt,desc`) |

### Paginated Response Format

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

## API Endpoints

### Reference Data

Reference data endpoints provide read-only access to spaces, menu items, and members.

#### Spaces

##### List All Spaces

```
GET /v1/external/reference/spaces
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `locale` | string | Language code (default: `fr`) |

**Response:**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Salle de Conférence A",
    "description": "Grande salle équipée pour les réunions",
    "capacity": 50,
    "locationId": "660e8400-e29b-41d4-a716-446655440001",
    "locationName": "Bâtiment Principal",
    "imageUrl": "https://cdn.theresidence.com/spaces/conf-a.jpg"
  }
]
```

##### Get Space by ID

```
GET /v1/external/reference/spaces/{id}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string (UUID) | Space ID |

---

#### Menu

##### List Menu Kinds

```
GET /v1/external/reference/menu-kinds
```

**Response:**

```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "name": "Restaurant",
    "description": "Menu du restaurant principal"
  },
  {
    "id": "770e8400-e29b-41d4-a716-446655440001",
    "name": "Bar",
    "description": "Boissons et snacks"
  }
]
```

##### Get Categories by Kind

```
GET /v1/external/reference/menu-kinds/{kindId}/categories
```

##### List All Categories

```
GET /v1/external/reference/menu-categories
```

**Response:**

```json
[
  {
    "id": "880e8400-e29b-41d4-a716-446655440000",
    "kindId": "770e8400-e29b-41d4-a716-446655440000",
    "name": "Entrées",
    "description": "Nos entrées fraîches",
    "imageUrl": "https://cdn.theresidence.com/menu/entrees.jpg"
  }
]
```

##### Get Items by Category

```
GET /v1/external/reference/menu-categories/{categoryId}/items
```

##### List All Menu Items

```
GET /v1/external/reference/menu-items
```

**Response:**

```json
[
  {
    "id": "990e8400-e29b-41d4-a716-446655440000",
    "categoryId": "880e8400-e29b-41d4-a716-446655440000",
    "name": "Salade César",
    "description": "Salade romaine, parmesan, croûtons, sauce César maison",
    "price": 12.50,
    "imageUrl": "https://cdn.theresidence.com/menu/caesar.jpg",
    "isAvailable": true
  }
]
```

##### Get Menu Item by ID

```
GET /v1/external/reference/menu-items/{id}
```

---

#### Members

##### Search Members

```
GET /v1/external/reference/members
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search by name, email, or company |
| `page` | integer | Page number |
| `size` | integer | Items per page |

**Response:**

```json
{
  "content": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440000",
      "firstName": "Jean",
      "lastName": "Dupont",
      "email": "jean.dupont@example.com",
      "phone": "+33612345678",
      "companyName": "Acme Corp",
      "jobTitle": "Directeur",
      "membershipTypeName": "Premium",
      "status": "ACTIVE",
      "joinedAt": "2025-01-15",
      "qrToken": "abc123xyz"
    }
  ],
  "totalCount": 1,
  "pagingInfo": {
    "size": 20,
    "pageCount": 1,
    "currentPage": 0,
    "hasPrevious": false,
    "hasNext": false
  }
}
```

##### Get Member by ID

```
GET /v1/external/reference/members/{id}
```

---

### Reservations

Full CRUD operations and status management for space reservations.

#### List Reservations

```
GET /v1/external/reservations
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `memberId` | string | Filter by member ID |
| `spaceId` | string | Filter by space ID |
| `status` | string | Filter by status: `PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`, `CHECKED_IN`, `COMPLETED` |
| `startDate` | datetime | Filter reservations starting after this date (ISO 8601) |
| `endDate` | datetime | Filter reservations ending before this date (ISO 8601) |
| `locale` | string | Language code (default: `fr`) |
| `page` | integer | Page number |
| `size` | integer | Items per page |

**Response:**

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
      "startTime": "2026-01-15T14:00:00",
      "endTime": "2026-01-15T16:00:00",
      "guestCount": 10,
      "status": "PENDING",
      "totalAmount": 150.00,
      "notes": "Réunion client importante",
      "options": [
        {
          "id": "cc0e8400-e29b-41d4-a716-446655440000",
          "name": "Vidéoprojecteur",
          "quantity": 1,
          "unitPrice": 25.00,
          "amount": 25.00
        }
      ],
      "invitees": [
        {
          "id": "dd0e8400-e29b-41d4-a716-446655440000",
          "name": "Marie Martin",
          "email": "marie.martin@example.com",
          "phone": "+33698765432"
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

#### Get Reservation by ID

```
GET /v1/external/reservations/{id}
```

#### Create Reservation

```
POST /v1/external/reservations
```

**Request Body:**

```json
{
  "memberId": "aa0e8400-e29b-41d4-a716-446655440000",
  "spaceId": "550e8400-e29b-41d4-a716-446655440000",
  "startTime": "2026-01-20T10:00:00",
  "endTime": "2026-01-20T12:00:00",
  "guestCount": 8,
  "notes": "Formation interne",
  "optionIds": [
    "cc0e8400-e29b-41d4-a716-446655440000"
  ],
  "invitees": [
    {
      "name": "Pierre Durand",
      "email": "pierre.durand@example.com",
      "phone": "+33611223344"
    }
  ]
}
```

**Response:** `201 Created` with the created reservation object.

#### Update Reservation

```
PUT /v1/external/reservations/{id}
```

**Request Body:** Same as create, all fields optional.

**Response:** `200 OK` with the updated reservation object.

#### Delete (Cancel) Reservation

```
DELETE /v1/external/reservations/{id}
```

**Response:** `200 OK`

```json
{
  "success": true,
  "message": "Reservation cancelled successfully"
}
```

#### Approve Reservation

```
POST /v1/external/reservations/{id}/approve
```

**Allowed from status:** `PENDING`

**Response:** Updated reservation with status `APPROVED`

#### Reject Reservation

```
POST /v1/external/reservations/{id}/reject
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `reason` | string | Rejection reason (optional) |

**Allowed from status:** `PENDING`

**Response:** Updated reservation with status `REJECTED`

#### Check-in Reservation

```
POST /v1/external/reservations/{id}/check-in
```

**Allowed from status:** `APPROVED`

**Response:** Updated reservation with status `CHECKED_IN`

---

### Orders

Read and status management for food orders.

#### List Orders

```
GET /v1/external/orders
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `memberId` | string | Filter by member ID |
| `status` | string | Filter by status: `PENDING`, `CONFIRMED`, `READY`, `COMPLETED`, `CANCELLED` |
| `mode` | string | Filter by mode: `PICKUP`, `DELIVERY` |
| `startDate` | datetime | Filter orders created after this date |
| `endDate` | datetime | Filter orders created before this date |
| `locale` | string | Language code (default: `fr`) |
| `page` | integer | Page number |
| `size` | integer | Items per page |

**Response:**

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
      "totalAmount": 45.50,
      "qrToken": "order-qr-token-123",
      "deliveryAddress": null,
      "items": [
        {
          "id": "ff0e8400-e29b-41d4-a716-446655440000",
          "menuItemId": "990e8400-e29b-41d4-a716-446655440000",
          "menuItemName": "Salade César",
          "quantity": 2,
          "unitPrice": 12.50,
          "amount": 25.00
        },
        {
          "id": "ff0e8400-e29b-41d4-a716-446655440001",
          "menuItemId": "990e8400-e29b-41d4-a716-446655440001",
          "menuItemName": "Café Espresso",
          "quantity": 2,
          "unitPrice": 3.50,
          "amount": 7.00
        }
      ],
      "createdAt": "2026-01-12T12:30:00",
      "updatedAt": "2026-01-12T12:30:00"
    }
  ],
  "totalCount": 42,
  "pagingInfo": {...}
}
```

#### Get Order by ID

```
GET /v1/external/orders/{id}
```

#### Confirm Order

```
POST /v1/external/orders/{id}/confirm
```

**Allowed from status:** `PENDING`

**Response:** Updated order with status `CONFIRMED`

#### Mark Order Ready

```
POST /v1/external/orders/{id}/ready
```

**Allowed from status:** `CONFIRMED`

**Response:** Updated order with status `READY`

#### Complete Order

```
POST /v1/external/orders/{id}/complete
```

**Allowed from status:** `READY`

**Response:** Updated order with status `COMPLETED`

#### Cancel Order

```
POST /v1/external/orders/{id}/cancel
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `reason` | string | Cancellation reason (optional) |

**Allowed from status:** `PENDING`, `CONFIRMED`, `READY`

**Response:** Updated order with status `CANCELLED`

---

### Webhooks

Register webhook endpoints to receive real-time event notifications.

#### List Webhooks

```
GET /v1/external/webhooks
```

**Response:**

```json
[
  {
    "id": "110e8400-e29b-41d4-a716-446655440000",
    "url": "https://your-odoo-instance.com/api/theresidence/webhook",
    "eventTypes": ["MEMBER_CREATED", "RESERVATION_CREATED", "ORDER_STATUS_CHANGED"],
    "isActive": true,
    "createdAt": "2026-01-10T08:00:00",
    "updatedAt": "2026-01-10T08:00:00"
  }
]
```

#### Get Webhook by ID

```
GET /v1/external/webhooks/{id}
```

#### Register Webhook

```
POST /v1/external/webhooks
```

**Request Body:**

```json
{
  "url": "https://your-odoo-instance.com/api/theresidence/webhook",
  "secret": "your-webhook-secret-for-signature-verification",
  "eventTypes": [
    "MEMBER_CREATED",
    "RESERVATION_CREATED",
    "RESERVATION_UPDATED",
    "RESERVATION_CANCELLED",
    "RESERVATION_STATUS_CHANGED",
    "ORDER_CREATED",
    "ORDER_STATUS_CHANGED",
    "ORDER_CANCELLED"
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | HTTPS endpoint to receive webhook events |
| `secret` | string | No | Secret key for HMAC signature verification |
| `eventTypes` | array | Yes | List of event types to subscribe to |

**Response:** `201 Created` with the created webhook object.

#### Update Webhook

```
PUT /v1/external/webhooks/{id}
```

**Request Body:** Same as create.

#### Delete Webhook

```
DELETE /v1/external/webhooks/{id}
```

**Response:** `200 OK`

#### Get Webhook Events (Delivery History)

```
GET /v1/external/webhooks/{id}/events
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | integer | Page number |
| `size` | integer | Items per page |

**Response:**

```json
{
  "content": [
    {
      "id": "220e8400-e29b-41d4-a716-446655440000",
      "eventType": "RESERVATION_CREATED",
      "entityType": "reservation",
      "entityId": "bb0e8400-e29b-41d4-a716-446655440000",
      "status": "DELIVERED",
      "attempts": 1,
      "responseStatus": 200,
      "createdAt": "2026-01-12T10:15:00",
      "lastAttemptAt": "2026-01-12T10:15:01"
    }
  ],
  "totalCount": 156,
  "pagingInfo": {...}
}
```

---

## Webhook Events

### Event Types

| Event Type | Trigger |
|------------|---------|
| `MEMBER_CREATED` | When a member application is approved/validated |
| `RESERVATION_CREATED` | When a new reservation is created via external API |
| `RESERVATION_UPDATED` | When a reservation is updated via external API |
| `RESERVATION_CANCELLED` | When a reservation is cancelled |
| `RESERVATION_STATUS_CHANGED` | When reservation status changes (approve, reject, check-in) |
| `ORDER_CREATED` | When a new order is placed (via mobile app) |
| `ORDER_STATUS_CHANGED` | When order status changes (confirm, ready, complete) |
| `ORDER_CANCELLED` | When an order is cancelled |

### Webhook Payload Format

All webhook events are delivered as HTTP POST requests with the following JSON payload:

```json
{
  "id": "330e8400-e29b-41d4-a716-446655440000",
  "eventType": "MEMBER_CREATED",
  "entityType": "member",
  "entityId": "aa0e8400-e29b-41d4-a716-446655440000",
  "data": {
    "id": "aa0e8400-e29b-41d4-a716-446655440000",
    "firstName": "Jean",
    "lastName": "Dupont",
    "email": "jean.dupont@example.com",
    "phone": "+33612345678",
    "companyName": "Acme Corp",
    "jobTitle": "Directeur",
    "membershipTypeName": "Premium",
    "status": "ACTIVE",
    "joinedAt": "2026-01-12",
    "qrToken": "member-qr-abc123"
  },
  "previousStatus": null,
  "newStatus": "ACTIVE",
  "timestamp": "2026-01-12T10:30:00Z"
}
```

### Payload Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique event ID |
| `eventType` | string | Type of event (see Event Types) |
| `entityType` | string | Type of entity: `member`, `reservation`, `order` |
| `entityId` | string | ID of the affected entity |
| `data` | object | Full entity data at the time of the event |
| `previousStatus` | string | Previous status (for status change events) |
| `newStatus` | string | New status (for status change events) |
| `timestamp` | datetime | When the event occurred (ISO 8601) |

---

## Webhook Security

### Signature Verification

If you provide a `secret` when registering your webhook, all webhook deliveries will include an HMAC-SHA256 signature in the `X-Webhook-Signature` header.

**Header Format:**
```
X-Webhook-Signature: sha256=<hex-encoded-signature>
```

### Verifying the Signature

The signature is computed as: `HMAC-SHA256(secret, request_body)`

**Python Example:**

```python
import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify the webhook signature."""
    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()

    # signature format: "sha256=<hex>"
    received = signature.replace('sha256=', '')

    return hmac.compare_digest(expected, received)

# Usage in your Odoo controller
@http.route('/api/theresidence/webhook', type='json', auth='public', methods=['POST'])
def handle_webhook(self, **kwargs):
    payload = request.httprequest.data
    signature = request.httprequest.headers.get('X-Webhook-Signature', '')
    secret = 'your-webhook-secret'

    if not verify_webhook_signature(payload, signature, secret):
        return {'error': 'Invalid signature'}, 401

    # Process the webhook
    data = json.loads(payload)
    event_type = data['eventType']
    # ... handle event
```

**JavaScript/Node.js Example:**

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

### Retry Policy

Failed webhook deliveries are automatically retried with exponential backoff:

| Attempt | Delay |
|---------|-------|
| 1 | Immediate |
| 2 | 1 minute |
| 3 | 5 minutes |
| 4 | 30 minutes |
| 5 | 2 hours |

After 5 failed attempts, the event is marked as `FAILED` and no further retries are attempted.

### Best Practices

1. **Always verify signatures** when a secret is configured
2. **Respond quickly** (within 30 seconds) to avoid timeouts
3. **Return 2xx status** to acknowledge receipt
4. **Process asynchronously** - queue the event and process later if needed
5. **Handle duplicates** - events may be delivered more than once; use the event `id` for deduplication

---

## Odoo Integration Example

Here's a basic example of an Odoo controller to receive webhook events:

```python
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import hmac
import hashlib
import logging

_logger = logging.getLogger(__name__)

class TheResidenceWebhook(http.Controller):

    WEBHOOK_SECRET = 'your-webhook-secret'

    def _verify_signature(self, payload, signature):
        expected = hmac.new(
            self.WEBHOOK_SECRET.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        received = signature.replace('sha256=', '') if signature else ''
        return hmac.compare_digest(expected, received)

    @http.route('/api/theresidence/webhook', type='json', auth='public',
                methods=['POST'], csrf=False)
    def handle_webhook(self, **kwargs):
        payload = request.httprequest.data
        signature = request.httprequest.headers.get('X-Webhook-Signature', '')

        # Verify signature
        if self.WEBHOOK_SECRET and not self._verify_signature(payload, signature):
            _logger.warning("Invalid webhook signature received")
            return {'success': False, 'error': 'Invalid signature'}

        try:
            data = json.loads(payload)
            event_type = data.get('eventType')
            entity_data = data.get('data', {})

            _logger.info(f"Received webhook: {event_type}")

            # Route to appropriate handler
            if event_type == 'MEMBER_CREATED':
                self._handle_member_created(entity_data)
            elif event_type == 'RESERVATION_CREATED':
                self._handle_reservation_created(entity_data)
            elif event_type == 'RESERVATION_STATUS_CHANGED':
                self._handle_reservation_status_changed(data)
            elif event_type == 'ORDER_STATUS_CHANGED':
                self._handle_order_status_changed(data)
            # ... handle other events

            return {'success': True}

        except Exception as e:
            _logger.error(f"Error processing webhook: {str(e)}")
            return {'success': False, 'error': str(e)}

    def _handle_member_created(self, member_data):
        """Create or update partner from member data."""
        Partner = request.env['res.partner'].sudo()

        # Check if partner exists
        partner = Partner.search([
            ('email', '=', member_data.get('email'))
        ], limit=1)

        vals = {
            'name': f"{member_data.get('firstName', '')} {member_data.get('lastName', '')}",
            'email': member_data.get('email'),
            'phone': member_data.get('phone'),
            'company_name': member_data.get('companyName'),
            'function': member_data.get('jobTitle'),
            'x_theresidence_id': member_data.get('id'),
            'x_theresidence_qr': member_data.get('qrToken'),
        }

        if partner:
            partner.write(vals)
            _logger.info(f"Updated partner: {partner.id}")
        else:
            partner = Partner.create(vals)
            _logger.info(f"Created partner: {partner.id}")

    def _handle_reservation_created(self, reservation_data):
        """Create calendar event from reservation."""
        Event = request.env['calendar.event'].sudo()

        # Find or create partner
        partner = request.env['res.partner'].sudo().search([
            ('x_theresidence_id', '=', reservation_data.get('memberId'))
        ], limit=1)

        Event.create({
            'name': f"Reservation - {reservation_data.get('spaceName')}",
            'start': reservation_data.get('startTime'),
            'stop': reservation_data.get('endTime'),
            'partner_ids': [(4, partner.id)] if partner else [],
            'description': reservation_data.get('notes'),
            'x_theresidence_id': reservation_data.get('id'),
        })

    def _handle_reservation_status_changed(self, event_data):
        """Update reservation status."""
        reservation_id = event_data.get('entityId')
        new_status = event_data.get('newStatus')

        Event = request.env['calendar.event'].sudo()
        event = Event.search([
            ('x_theresidence_id', '=', reservation_id)
        ], limit=1)

        if event:
            event.write({'x_theresidence_status': new_status})

    def _handle_order_status_changed(self, event_data):
        """Update order status in POS or custom model."""
        order_data = event_data.get('data', {})
        order_id = event_data.get('entityId')
        new_status = event_data.get('newStatus')

        # Implement your order handling logic
        _logger.info(f"Order {order_id} status changed to {new_status}")
```

---

## Rate Limits

| Endpoint Category | Rate Limit |
|-------------------|------------|
| Reference Data | 100 requests/minute |
| Reservations | 60 requests/minute |
| Orders | 60 requests/minute |
| Webhooks | 30 requests/minute |

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when the limit resets

---

## Support

For technical support or API key requests, contact:
- Email: api-support@theresidence.com
- Documentation: https://docs.theresidence.com/external-api
