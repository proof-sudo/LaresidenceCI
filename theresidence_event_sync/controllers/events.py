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


class EventSyncController(http.Controller):
    """Endpoints de synchronisation des événements depuis le backend externe."""

    # ─────────────────────────────────────────────────────────────
    # ÉVÉNEMENTS
    # ─────────────────────────────────────────────────────────────

    @http.route(f'{API_PREFIX}/events', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_reservations')
    def create_event(self, **kwargs):
        """
        Crée un événement dans Odoo.

        Body JSON :
        {
            "externalId": "uuid-event",
            "title":      "Soirée Jazz",
            "description": "...",
            "startAt":    "2026-04-15T19:00:00Z",
            "endAt":      "2026-04-15T23:00:00Z",
            "capacity":   50           // null ou absent = illimité
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

            # Vérifier doublon
            existing = request.env['event.event'].sudo().search(
                [('x_tr_external_id', '=', data['externalId'])], limit=1
            )
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
        Met à jour un événement existant (titre, dates, capacité, archivage).

        Body JSON (tous les champs sont optionnels) :
        {
            "title":      "Nouveau titre",
            "description": "...",
            "startAt":    "2026-04-15T20:00:00Z",
            "endAt":      "2026-04-16T00:00:00Z",
            "capacity":   80,
            "cancelled":  true   // true = archiver l'événement
        }
        """
        try:
            event = request.env['event.event'].sudo().search(
                [('x_tr_external_id', '=', external_id)], limit=1
            )
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
            if data.get('cancelled'):
                vals['active'] = False

            if vals:
                event.sudo().write(vals)
                _logger.info('[TR EVENT SYNC] Événement mis à jour : odooId=%s externalId=%s', event.id, external_id)

            return success_response(event.to_sync_dict())

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur update_event : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/events/<string:external_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    @api_auth('write_reservations')
    def delete_event(self, external_id, **kwargs):
        """
        Archive un événement (soft delete — active=False).
        Ne supprime pas physiquement pour conserver l'historique.
        """
        try:
            event = request.env['event.event'].sudo().search(
                [('x_tr_external_id', '=', external_id)], limit=1
            )
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            event.sudo().write({'active': False})
            _logger.info('[TR EVENT SYNC] Événement archivé : odooId=%s externalId=%s', event.id, external_id)
            return success_response({'odooId': event.id, 'externalId': external_id, 'archived': True})

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur delete_event : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)

    # ─────────────────────────────────────────────────────────────
    # INSCRIPTIONS
    # ─────────────────────────────────────────────────────────────

    @http.route(f'{API_PREFIX}/events/<string:external_id>/registrations', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_reservations')
    def create_registration(self, external_id, **kwargs):
        """
        Crée une inscription à un événement.

        Body JSON :
        {
            "externalRegistrationId": "uuid-registration",
            "memberUuid":  "uuid-membre-tr",   // optionnel
            "memberOdooId": 42,                // optionnel, prioritaire sur memberUuid
            "name":   "Jean Dupont",
            "email":  "jean@example.com",
            "phone":  "+2250700000000",        // optionnel
            "status": "VALIDATED"              // VALIDATED | PENDING | CANCELLED
        }
        """
        try:
            event = request.env['event.event'].sudo().search(
                [('x_tr_external_id', '=', external_id)], limit=1
            )
            if not event:
                return error_response(f"Événement '{external_id}' introuvable", 'NOT_FOUND', 404)

            data = json.loads(request.httprequest.data)

            if not data.get('externalRegistrationId'):
                return error_response('externalRegistrationId est obligatoire', 'MISSING_FIELD', 400)
            if not data.get('name') and not data.get('email'):
                return error_response('name ou email est obligatoire', 'MISSING_FIELD', 400)

            # Vérifier doublon
            existing = request.env['event.registration'].sudo().search([
                ('event_id', '=', event.id),
                ('x_tr_external_id', '=', data['externalRegistrationId']),
            ], limit=1)
            if existing:
                return error_response(
                    f"Une inscription avec externalRegistrationId '{data['externalRegistrationId']}' existe déjà.",
                    'DUPLICATE', 409
                )

            # Résoudre le partner
            partner = False
            if data.get('memberOdooId'):
                partner = request.env['res.partner'].sudo().browse(int(data['memberOdooId']))
                if not partner.exists():
                    partner = False
            if not partner and data.get('memberUuid'):
                partner = request.env['res.partner'].sudo().search(
                    [('x_tr_uuid', '=', data['memberUuid'])], limit=1
                )

            odoo_state = REGISTRATION_STATE_MAP.get(data.get('status', 'VALIDATED'), 'open')

            reg_vals = {
                'event_id': event.id,
                'x_tr_external_id': data['externalRegistrationId'],
                'x_tr_member_uuid': data.get('memberUuid', ''),
                'name': data.get('name', ''),
                'email': data.get('email', ''),
                'mobile': data.get('phone', ''),
                'state': odoo_state,
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
        Met à jour le statut d'une inscription.

        Body JSON :
        {
            "status": "VALIDATED" | "CANCELLED" | "PENDING"
        }
        """
        try:
            reg = request.env['event.registration'].sudo().search([
                ('event_id.x_tr_external_id', '=', external_id),
                ('x_tr_external_id', '=', external_reg_id),
            ], limit=1)
            if not reg:
                return error_response(
                    f"Inscription '{external_reg_id}' introuvable pour l'événement '{external_id}'",
                    'NOT_FOUND', 404
                )

            data = json.loads(request.httprequest.data)
            vals = {}

            if 'status' in data:
                vals['state'] = REGISTRATION_STATE_MAP.get(data['status'], 'open')
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
        Annule une inscription (state → cancel).
        """
        try:
            reg = request.env['event.registration'].sudo().search([
                ('event_id.x_tr_external_id', '=', external_id),
                ('x_tr_external_id', '=', external_reg_id),
            ], limit=1)
            if not reg:
                return error_response(
                    f"Inscription '{external_reg_id}' introuvable pour l'événement '{external_id}'",
                    'NOT_FOUND', 404
                )

            reg.sudo().write({'state': 'cancel'})
            _logger.info('[TR EVENT SYNC] Inscription annulée : odooId=%s', reg.id)
            return success_response({'odooId': reg.id, 'externalId': external_reg_id, 'state': 'cancel'})

        except Exception as e:
            _logger.error('[TR EVENT SYNC] Erreur cancel_registration : %s', str(e))
            return error_response(str(e), 'INVALID_REQUEST', 400)
