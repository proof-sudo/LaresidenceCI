# Odoo Webhook Integration Specification

## Overview

This document describes how Odoo should send webhook events to The Residence API when orders or reservations are validated, cancelled, or change status.

---

## Endpoint

```
POST /v1/external/webhooks/odoo
```

**Base URL** (Production): `https://api.laresidence-abidjan.com`

---

## Authentication

All requests must include an API key in the header.

| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | Yes | API key provided by The Residence |

**Example:**
```
X-API-Key: your-api-key-here
```

---

## Request Format

### Headers

```
Content-Type: application/json
X-API-Key: <your-api-key>
```

### Body Schema

```json
{
  "event_type": "string",
  "event_id": "string",
  "timestamp": "string (ISO 8601)",
  "entity_type": "string",
  "entity_id": "string",
  "data": { }
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_type` | string | Yes | Type of event (see Event Types below) |
| `event_id` | string | Yes | Unique identifier for this event (for idempotency) |
| `timestamp` | string | Yes | ISO 8601 timestamp when event occurred |
| `entity_type` | string | Yes | Type of entity: `order`, `reservation`, `subscription`, `member` |
| `entity_id` | string | Yes | Odoo ID of the entity (must match `odoo_id` in The Residence DB) |
| `data` | object | No | Additional data specific to the event type |

---

## Event Types

### Order Events

| Event Type | Description | Status Set |
|------------|-------------|------------|
| `order.confirmed` | Order has been confirmed by staff | `CONFIRMED` |
| `order.ready` | Order is ready for pickup/delivery | `READY` |
| `order.completed` | Order has been delivered/picked up | `COMPLETED` |
| `order.cancelled` | Order has been cancelled | `CANCELLED` |

### Reservation Events

| Event Type | Description | Status Set |
|------------|-------------|------------|
| `reservation.approved` | Reservation has been approved | `APPROVED` |
| `reservation.rejected` | Reservation has been rejected | `REJECTED` |
| `reservation.cancelled` | Reservation has been cancelled | `CANCELLED` |
| `reservation.checked_in` | Member has checked in | `CHECK_IN` |

### Subscription Events

| Event Type | Description |
|------------|-------------|
| `subscription.activated` | Subscription is now active |
| `subscription.paused` | Subscription has been paused |
| `subscription.resumed` | Subscription has been resumed |
| `subscription.cancelled` | Subscription has been cancelled |
| `subscription.expired` | Subscription has expired |
| `subscription.renewed` | Subscription has been renewed |

### Member Events

| Event Type | Description |
|------------|-------------|
| `member.updated` | Member information has been updated |

---

## Examples

### Order Confirmed

```json
{
  "event_type": "order.confirmed",
  "event_id": "evt_20260126_001",
  "timestamp": "2026-01-26T10:30:00Z",
  "entity_type": "order",
  "entity_id": "ODOO-ORDER-12345",
  "data": {
    "confirmed_by": "staff_user_id",
    "estimated_ready_time": "2026-01-26T11:00:00Z"
  }
}
```

### Reservation Approved

```json
{
  "event_type": "reservation.approved",
  "event_id": "evt_20260126_002",
  "timestamp": "2026-01-26T09:15:00Z",
  "entity_type": "reservation",
  "entity_id": "ODOO-RESV-67890",
  "data": {
    "approved_by": "manager_user_id",
    "notes": "Approved with special setup requirements"
  }
}
```

### Order Cancelled

```json
{
  "event_type": "order.cancelled",
  "event_id": "evt_20260126_003",
  "timestamp": "2026-01-26T14:45:00Z",
  "entity_type": "order",
  "entity_id": "ODOO-ORDER-12346",
  "data": {
    "cancelled_by": "member",
    "reason": "Member requested cancellation"
  }
}
```

---

## Response Format

### Success (HTTP 202 Accepted)

The API acknowledges receipt immediately and processes the event asynchronously.

```json
{
  "success": true,
  "message": "Event accepted for processing",
  "eventId": "evt_20260126_001"
}
```

### Error Responses

| HTTP Code | Description | Response |
|-----------|-------------|----------|
| 401 | Missing or invalid API key | `{"success": false, "message": "Missing API key. Provide X-API-Key header", "eventId": null}` |
| 400 | Invalid JSON payload | `{"success": false, "message": "Invalid payload format", "eventId": null}` |
| 503 | Webhooks disabled | `{"success": false, "message": "Webhooks are disabled", "eventId": null}` |

---

## Important Notes

### Entity ID Matching

The `entity_id` field **must match** the `odoo_id` stored in The Residence database. When The Residence creates an order or reservation and syncs to Odoo, we store the Odoo ID returned. Use this same ID when sending webhooks.

### Idempotency

Use unique `event_id` values for each event. If an event is sent multiple times with the same `event_id`, the API will process it only once.

### Async Processing

The API returns `HTTP 202 Accepted` immediately and processes events in the background. This means:
- Fast response time (< 100ms)
- If processing fails, it won't affect Odoo's request
- Check logs on The Residence side to verify processing

### Retry Policy

If The Residence API is unavailable:
- Retry with exponential backoff: 1s, 2s, 4s, 8s, 16s (max 5 retries)
- Store failed events for manual retry if all attempts fail

---

## Testing

### Test Endpoint

```bash
curl -X POST https://api.laresidence-abidjan.com/v1/external/webhooks/odoo \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-test-api-key" \
  -d '{
    "event_type": "order.confirmed",
    "event_id": "test_001",
    "timestamp": "2026-01-26T10:00:00Z",
    "entity_type": "order",
    "entity_id": "TEST-ORDER-001",
    "data": {}
  }'
```

### Expected Response

```json
{
  "success": true,
  "message": "Event accepted for processing",
  "eventId": "test_001"
}
```

---

## Contact

For API key requests or technical questions, contact The Residence development team.
