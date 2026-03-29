# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime, timezone
from odoo import http
from odoo.http import request
from theresidence_api.controllers.main import API_PREFIX, api_auth, success_response, error_response

_logger = logging.getLogger(__name__)

# Mapping statut externe → state Odoo event.registration
REGISTRATION_STATE_MAP = {
    'VALIDATED': 'open',
    'PENDING':   'draft',
    'CANCELLED': 'cancel',
}


def _parse_dt(dt_str):
    """Parse ISO 8601 (avec ou sans timezone) → naive UTC datetime."""
    if not dt_str:
        return None
    dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _resolve_event(external_id):
    """Retourne l'event.event correspondant à l'externalId, ou None."""
    return request.env['event.event'].sudo().search(
        [('x_tr_external_id', '=', external_id)], limit=1
    )


def _resolve_registration(external_id, event):
    """Retourne l'event.registration correspondant à l'externalId pour cet event."""
    return request.env['event.registration'].sudo().search([
        ('event_id', '=', event.id),
        ('x_tr_external_id', '=', external_id),
        ('x_tr_is_attendee', '=', False),
    ], limit=1)


class EventSyncController(http.Controller):
    """Endpoints de synchronisation des événements depuis le backend externe."""

    # ═══════════════════════════════════════════════════════════════
    # ÉVÉNEMENTS
    # ═══════════════════════════════════════════════════════════════

    @http.route(f'{API_PREFIX}/events', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_reservations')
    def create_event(self, **kwargs):
        """
        Crée un événement dans Odoo.

        Body JSON :
        {
            "externalId":   "uuid-event",
            "title":        "Soirée Jazz",
            "description":  "...",                   // optionnel
            "startAt":      "2026-04-15T19:00:00Z",
            "endAt":        "2026-04-15T23:00:00Z",
            "capacity":     50,                      // null ou absent = illimité
            "audienceUuids": ["uuid-plan-1", "uuid-plan-2"]  // optionnel, vide = ouvert à tous
        }
        """
        try:
            data = json.loads(request.httprequest.data)

            if not data.get('externalId'):
                return error_response('externalId est obligatoire', 'MISSING_FIELD', 400)
            if not data.get('title'):
                return error_response('title est obligatoire', 'MISSING_FIELD', 400)
            if not data.get('startAt') or not data.get('endAt'):
                return error_response('startAt et endAt sont obligatoires', 'MISSING_FIELD', 400)

            existing = _resolve_event(data['externalId'])
            if existing:
                return error_response(
                    f"Un événement avec externalId '{data['externalId']}' existe déjà (odooId={existing.id}).",
                    'DUPLICATE', 409
                )

            start_dt = _parse_dt(data['startAt'])
            end_dt = _parse_dt(data['endAt'])
            if not start_dt or not end_dt:
                return error_response('Dates invalides', 'INVALID_DATE', 400)
            if end_dt <= start_dt:
                return error_response('endAt doit être postérieur à startAt', 'INVALID_DATE', 400)

            capacity = data.get('capacity') or 0

            event_vals = {
                'name': data['title'],
                'date_begin': start_dt,
                'date_end': end_dt,
                'x_tr_external_id': data['externalId'],
                'seats_availability': 'limited' if capacity else 'unlimited',
                'seats_max': capacity,
            }
            if data.get('description'):
                event_vals['description'] = data['description']

            # Audience : résolution par UUID de plan d'abonnement
            audience_ids = _resolve_audience(data.get('audienceUuids', []))
            if audience_ids:
                event_vals['x_tr_audience_ids'] = [(6, 0, audience_ids)]

            event = request.env['event.event'].sudo().create(event_vals)
            _logger.info('[TR EVENT SYNC] Événement créé : odooId=%s externalId=%s', event.id, data['externalId'])
            return success_response(event.to_sync_dict(), 201)

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur create_event : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/events/<string:external_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    @api_auth('write_reservations')
    def update_event(self, external_id, **kwargs):
        """
        Met à jour un événement (titre, description, dates, capacité, audience, archivage).

        Body JSON (tous optionnels) :
        {
            "title":        "Nouveau titre",
            "description":  "...",
            "startAt":      "2026-04-15T20:00:00Z",
            "endAt":        "2026-04-16T00:00:00Z",
            "capacity":     80,
            "audienceUuids": ["uuid-plan-1"],
            "cancelled":    true    // true = archiver l'événement
        }
        """
        try:
            event = _resolve_event(external_id)
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            data = json.loads(request.httprequest.data)
            vals = {}

            if 'title' in data:
                vals['name'] = data['title']
            if 'description' in data:
                vals['description'] = data['description']
            if 'startAt' in data:
                vals['date_begin'] = _parse_dt(data['startAt'])
            if 'endAt' in data:
                vals['date_end'] = _parse_dt(data['endAt'])
            if 'capacity' in data:
                capacity = data['capacity'] or 0
                vals['seats_max'] = capacity
                vals['seats_availability'] = 'limited' if capacity else 'unlimited'
            if 'audienceUuids' in data:
                audience_ids = _resolve_audience(data['audienceUuids'] or [])
                vals['x_tr_audience_ids'] = [(6, 0, audience_ids)]
            if data.get('cancelled'):
                vals['active'] = False

            if vals:
                event.sudo().write(vals)
                _logger.info('[TR EVENT SYNC] Événement mis à jour : odooId=%s', event.id)

            return success_response(event.to_sync_dict())

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur update_event : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/events/<string:external_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    @api_auth('write_reservations')
    def delete_event(self, external_id, **kwargs):
        """
        Archive un événement (soft delete → active=False).
        L'historique des inscriptions est conservé.
        """
        try:
            event = _resolve_event(external_id)
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            event.sudo().write({'active': False})
            _logger.info('[TR EVENT SYNC] Événement archivé : odooId=%s externalId=%s', event.id, external_id)
            return success_response({'odooId': event.id, 'externalId': external_id, 'archived': True})

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur delete_event : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    # ═══════════════════════════════════════════════════════════════
    # INSCRIPTIONS
    # ═══════════════════════════════════════════════════════════════

    @http.route(
        f'{API_PREFIX}/events/<string:external_id>/registrations',
        type='http', auth='public', methods=['POST'], csrf=False
    )
    @api_auth('write_reservations')
    def create_registration(self, external_id, **kwargs):
        """
        Inscrit un membre à un événement.

        Body JSON :
        {
            "externalRegistrationId": "uuid-registration",
            "memberUuid":   "uuid-membre-tr",    // optionnel
            "memberOdooId": 42,                  // optionnel, prioritaire sur memberUuid
            "name":         "Jean Dupont",
            "email":        "jean@example.com",
            "phone":        "+2250700000000",    // optionnel
            "guestsCount":  2,                   // nb invités non-nominatifs (défaut: 0)
            "status":       "VALIDATED"          // VALIDATED | PENDING | CANCELLED
        }
        """
        try:
            event = _resolve_event(external_id)
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            data = json.loads(request.httprequest.data)

            if not data.get('externalRegistrationId'):
                return error_response('externalRegistrationId est obligatoire', 'MISSING_FIELD', 400)
            if not data.get('name') and not data.get('email'):
                return error_response('name ou email est obligatoire', 'MISSING_FIELD', 400)

            existing = request.env['event.registration'].sudo().search([
                ('event_id', '=', event.id),
                ('x_tr_external_id', '=', data['externalRegistrationId']),
                ('x_tr_is_attendee', '=', False),
            ], limit=1)
            if existing:
                return error_response(
                    f"Une inscription avec externalRegistrationId '{data['externalRegistrationId']}' existe déjà.",
                    'DUPLICATE', 409
                )

            partner = _resolve_partner(data)
            odoo_state = REGISTRATION_STATE_MAP.get(data.get('status', 'VALIDATED'), 'open')

            reg_vals = {
                'event_id': event.id,
                'x_tr_external_id': data['externalRegistrationId'],
                'x_tr_member_uuid': data.get('memberUuid', ''),
                'x_tr_guests_count': int(data.get('guestsCount', 0)),
                'name': data.get('name', ''),
                'email': data.get('email', ''),
                'mobile': data.get('phone', ''),
                'state': odoo_state,
                'x_tr_is_attendee': False,
            }
            if partner:
                reg_vals['partner_id'] = partner.id

            reg = request.env['event.registration'].sudo().create(reg_vals)
            _logger.info(
                '[TR EVENT SYNC] Inscription créée : odooId=%s event=%s member=%s',
                reg.id, external_id, data.get('memberUuid', '?')
            )
            return success_response(reg.to_sync_dict(), 201)

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur create_registration : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(
        f'{API_PREFIX}/events/<string:external_id>/registrations/<string:external_reg_id>',
        type='http', auth='public', methods=['PUT'], csrf=False
    )
    @api_auth('write_reservations')
    def update_registration(self, external_id, external_reg_id, **kwargs):
        """
        Met à jour une inscription (statut, nombre d'invités).

        Body JSON (tous optionnels) :
        {
            "status":      "VALIDATED" | "CANCELLED" | "PENDING",
            "guestsCount": 3
        }
        """
        try:
            event = _resolve_event(external_id)
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            reg = _resolve_registration(external_reg_id, event)
            if not reg:
                return error_response(
                    f"Inscription '{external_reg_id}' introuvable", 'NOT_FOUND', 404
                )

            data = json.loads(request.httprequest.data)
            vals = {}

            if 'status' in data:
                vals['state'] = REGISTRATION_STATE_MAP.get(data['status'], 'open')
            if 'guestsCount' in data:
                vals['x_tr_guests_count'] = int(data['guestsCount'])
            if 'name' in data:
                vals['name'] = data['name']
            if 'email' in data:
                vals['email'] = data['email']
            if 'phone' in data:
                vals['mobile'] = data['phone']

            if vals:
                reg.sudo().write(vals)
                _logger.info('[TR EVENT SYNC] Inscription mise à jour : odooId=%s', reg.id)

            return success_response(reg.to_sync_dict())

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur update_registration : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(
        f'{API_PREFIX}/events/<string:external_id>/registrations/<string:external_reg_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    @api_auth('write_reservations')
    def cancel_registration(self, external_id, external_reg_id, **kwargs):
        """
        Annule une inscription (state → cancel) et tous ses invités nominatifs.
        """
        try:
            event = _resolve_event(external_id)
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            reg = _resolve_registration(external_reg_id, event)
            if not reg:
                return error_response(
                    f"Inscription '{external_reg_id}' introuvable", 'NOT_FOUND', 404
                )

            # Annuler aussi les invités nominatifs liés
            reg.sudo().x_tr_attendee_ids.write({'state': 'cancel'})
            reg.sudo().write({'state': 'cancel'})
            _logger.info('[TR EVENT SYNC] Inscription annulée : odooId=%s', reg.id)
            return success_response({'odooId': reg.id, 'externalId': external_reg_id, 'state': 'cancel'})

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur cancel_registration : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    # ═══════════════════════════════════════════════════════════════
    # INVITÉS NOMINATIFS (EventAttendee)
    # ═══════════════════════════════════════════════════════════════

    @http.route(
        f'{API_PREFIX}/events/<string:external_id>/registrations/<string:external_reg_id>/attendees',
        type='http', auth='public', methods=['POST'], csrf=False
    )
    @api_auth('write_reservations')
    def create_attendee(self, external_id, external_reg_id, **kwargs):
        """
        Ajoute un invité nominatif à une inscription.

        Body JSON :
        {
            "externalAttendeeId": "uuid-attendee",
            "fullName": "Marie Dupont",
            "email":    "marie@example.com",
            "phone":    "+2250700000001"    // optionnel
        }
        """
        try:
            event = _resolve_event(external_id)
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            reg = _resolve_registration(external_reg_id, event)
            if not reg:
                return error_response(
                    f"Inscription '{external_reg_id}' introuvable", 'NOT_FOUND', 404
                )

            data = json.loads(request.httprequest.data)

            if not data.get('externalAttendeeId'):
                return error_response('externalAttendeeId est obligatoire', 'MISSING_FIELD', 400)
            if not data.get('fullName') and not data.get('email'):
                return error_response('fullName ou email est obligatoire', 'MISSING_FIELD', 400)

            # Vérifier doublon (même email dans le même événement)
            if data.get('email'):
                dup = request.env['event.registration'].sudo().search([
                    ('event_id', '=', event.id),
                    ('email', '=', data['email']),
                ], limit=1)
                if dup:
                    return error_response(
                        f"Un participant avec l'email '{data['email']}' est déjà inscrit à cet événement.",
                        'DUPLICATE_EMAIL', 409
                    )

            # Vérifier doublon par externalAttendeeId
            dup_ext = request.env['event.registration'].sudo().search([
                ('event_id', '=', event.id),
                ('x_tr_external_id', '=', data['externalAttendeeId']),
                ('x_tr_is_attendee', '=', True),
            ], limit=1)
            if dup_ext:
                return error_response(
                    f"Un invité avec externalAttendeeId '{data['externalAttendeeId']}' existe déjà.",
                    'DUPLICATE', 409
                )

            attendee = request.env['event.registration'].sudo().create({
                'event_id': event.id,
                'x_tr_external_id': data['externalAttendeeId'],
                'x_tr_parent_registration_id': reg.id,
                'x_tr_is_attendee': True,
                'name': data.get('fullName', ''),
                'email': data.get('email', ''),
                'mobile': data.get('phone', ''),
                'state': 'open',
            })
            _logger.info(
                '[TR EVENT SYNC] Invité ajouté : odooId=%s inscription=%s',
                attendee.id, reg.id
            )
            return success_response(attendee.to_sync_dict(), 201)

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur create_attendee : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(
        f'{API_PREFIX}/events/<string:external_id>/registrations/<string:external_reg_id>/attendees/<string:external_attendee_id>',
        type='http', auth='public', methods=['PUT'], csrf=False
    )
    @api_auth('write_reservations')
    def update_attendee(self, external_id, external_reg_id, external_attendee_id, **kwargs):
        """
        Modifie les informations d'un invité nominatif.

        Body JSON (tous optionnels) :
        {
            "fullName": "Marie Martin",
            "email":    "marie.martin@example.com",
            "phone":    "+2250700000002"
        }
        """
        try:
            event = _resolve_event(external_id)
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            attendee = request.env['event.registration'].sudo().search([
                ('event_id', '=', event.id),
                ('x_tr_external_id', '=', external_attendee_id),
                ('x_tr_is_attendee', '=', True),
            ], limit=1)
            if not attendee:
                return error_response(
                    f"Invité '{external_attendee_id}' introuvable", 'NOT_FOUND', 404
                )

            data = json.loads(request.httprequest.data)
            vals = {}
            if 'fullName' in data:
                vals['name'] = data['fullName']
            if 'email' in data:
                vals['email'] = data['email']
            if 'phone' in data:
                vals['mobile'] = data['phone']

            if vals:
                attendee.sudo().write(vals)
                _logger.info('[TR EVENT SYNC] Invité mis à jour : odooId=%s', attendee.id)

            return success_response(attendee.to_sync_dict())

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur update_attendee : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(
        f'{API_PREFIX}/events/<string:external_id>/registrations/<string:external_reg_id>/attendees/<string:external_attendee_id>',
        type='http', auth='public', methods=['DELETE'], csrf=False
    )
    @api_auth('write_reservations')
    def delete_attendee(self, external_id, external_reg_id, external_attendee_id, **kwargs):
        """
        Supprime un invité nominatif (hard delete, conformément aux règles métier du backend).
        """
        try:
            event = _resolve_event(external_id)
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            attendee = request.env['event.registration'].sudo().search([
                ('event_id', '=', event.id),
                ('x_tr_external_id', '=', external_attendee_id),
                ('x_tr_is_attendee', '=', True),
            ], limit=1)
            if not attendee:
                return error_response(
                    f"Invité '{external_attendee_id}' introuvable", 'NOT_FOUND', 404
                )

            odoo_id = attendee.id
            attendee.sudo().unlink()
            _logger.info('[TR EVENT SYNC] Invité supprimé : odooId=%s', odoo_id)
            return success_response({'odooId': odoo_id, 'externalId': external_attendee_id, 'deleted': True})

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur delete_attendee : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _resolve_partner(data):
    """Retrouve le res.partner depuis memberOdooId ou memberUuid."""
    if data.get('memberOdooId'):
        partner = request.env['res.partner'].sudo().browse(int(data['memberOdooId']))
        if partner.exists():
            return partner
    if data.get('memberUuid'):
        return request.env['res.partner'].sudo().search(
            [('x_tr_uuid', '=', data['memberUuid'])], limit=1
        ) or False
    return False


def _resolve_audience(uuids):
    """Retourne la liste des IDs product.template correspondant aux UUIDs de plans."""
    if not uuids:
        return []
    plans = request.env['product.template'].sudo().search([
        ('x_tr_space_uuid', 'in', uuids),
        ('x_tr_is_subscription_plan', '=', True),
    ])
    return plans.ids
