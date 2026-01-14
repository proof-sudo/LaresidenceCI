# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime

from odoo import http
from odoo.http import request

from .main import api_response, api_error

_logger = logging.getLogger(__name__)


class ResidenceWebhookController(http.Controller):
    """Controller pour recevoir les webhooks du mobile"""

    @http.route('/api/v1/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def receive_webhook(self):
        """Réception des webhooks du mobile"""
        start_time = datetime.now()

        try:
            # Récupérer le payload
            payload = request.httprequest.data
            if not payload:
                return api_error('Payload vide', error_code='INVALID_REQUEST', status=400)

            # Parser le JSON
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                return api_error('JSON invalide', error_code='INVALID_REQUEST', status=400)

            # Récupérer la signature
            signature = request.httprequest.headers.get('X-Webhook-Signature')

            # Récupérer la configuration
            config = request.env['residence.config'].sudo().get_config()

            # Vérifier la signature
            if config and config.webhook_secret:
                if not config.verify_webhook_signature(payload, signature):
                    self._log_webhook(
                        data=data,
                        payload=payload.decode('utf-8') if isinstance(payload, bytes) else payload,
                        state='failed',
                        error='Signature invalide',
                        processing_time=(datetime.now() - start_time).total_seconds() * 1000
                    )
                    return api_error('Signature invalide', error_code='UNAUTHORIZED', status=401)

            # Extraire les informations
            event_type = data.get('eventType')
            entity_type = data.get('entityType')
            entity_id = data.get('entityId')
            event_data = data.get('data', {})

            if not event_type:
                return api_error('eventType requis', error_code='INVALID_REQUEST', status=400)

            # Logger le webhook entrant
            log = self._log_webhook(
                data=data,
                payload=payload.decode('utf-8') if isinstance(payload, bytes) else payload,
                state='processing'
            )

            # Traiter selon le type d'événement
            result = self._process_webhook(event_type, entity_type, entity_id, event_data)

            # Mettre à jour le log
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            log.write({
                'state': 'success' if result.get('success') else 'failed',
                'error_message': result.get('error'),
                'processing_time': processing_time,
                'processed_date': datetime.now()
            })

            if result.get('success'):
                return api_response(
                    {'webhookId': data.get('id'), 'processed': True},
                    message='Webhook traité avec succès'
                )
            else:
                return api_error(
                    result.get('error', 'Erreur de traitement'),
                    error_code='PROCESSING_ERROR',
                    status=400
                )

        except Exception as e:
            _logger.error(f"Erreur webhook: {str(e)}")
            return api_error(str(e), status=500)

    def _log_webhook(self, data, payload, state='pending', error=None, processing_time=None):
        """Enregistrer le webhook dans les logs"""
        return request.env['residence.webhook.log'].sudo().create({
            'direction': 'incoming',
            'event_type': data.get('eventType'),
            'entity_type': data.get('entityType'),
            'entity_id': data.get('entityId'),
            'payload': payload,
            'headers': json.dumps(dict(request.httprequest.headers)),
            'state': state,
            'error_message': error,
            'processing_time': processing_time
        })

    def _process_webhook(self, event_type, entity_type, entity_id, data):
        """Traiter le webhook selon son type"""
        handlers = {
            # Membres
            'MEMBER_CREATED': self._handle_member_created,
            'MEMBER_UPDATED': self._handle_member_updated,

            # Réservations
            'RESERVATION_CREATED': self._handle_reservation_created,
            'RESERVATION_UPDATED': self._handle_reservation_updated,
            'RESERVATION_CANCELLED': self._handle_reservation_cancelled,
            'RESERVATION_STATUS_CHANGED': self._handle_reservation_status_changed,

            # Commandes
            'ORDER_CREATED': self._handle_order_created,
            'ORDER_STATUS_CHANGED': self._handle_order_status_changed,
            'ORDER_CANCELLED': self._handle_order_cancelled,

            # Abonnements
            'SUBSCRIPTION_CREATED': self._handle_subscription_created,
            'SUBSCRIPTION_CANCELLED': self._handle_subscription_cancelled,
        }

        handler = handlers.get(event_type)
        if handler:
            try:
                return handler(entity_type, entity_id, data)
            except Exception as e:
                _logger.error(f"Erreur handler {event_type}: {str(e)}")
                return {'success': False, 'error': str(e)}
        else:
            _logger.warning(f"Type d'événement non géré: {event_type}")
            return {'success': True, 'message': 'Event type ignored'}

    # ==========================================
    # Handlers Membres
    # ==========================================
    def _handle_member_created(self, entity_type, entity_id, data):
        """Traiter création membre"""
        Partner = request.env['res.partner'].sudo()

        # Vérifier si existe déjà
        existing = Partner.get_by_external_id(entity_id)
        if existing:
            return {'success': True, 'message': 'Member already exists'}

        # Vérifier par email
        if data.get('email'):
            existing = Partner.search([
                ('email', '=', data['email']),
                ('is_residence_member', '=', True)
            ], limit=1)
            if existing:
                # Mettre à jour l'ID externe
                existing.residence_external_id = entity_id
                return {'success': True, 'message': 'Member linked'}

        # Créer le membre
        data['id'] = entity_id
        Partner.create_from_api(data)
        return {'success': True, 'message': 'Member created'}

    def _handle_member_updated(self, entity_type, entity_id, data):
        """Traiter mise à jour membre"""
        partner = request.env['res.partner'].sudo().get_by_external_id(entity_id)
        if not partner:
            return {'success': False, 'error': 'Member not found'}

        partner.update_from_api(data)
        return {'success': True, 'message': 'Member updated'}

    # ==========================================
    # Handlers Réservations
    # ==========================================
    def _handle_reservation_created(self, entity_type, entity_id, data):
        """Traiter création réservation"""
        SaleOrder = request.env['sale.order'].sudo()

        # Vérifier si existe déjà
        existing = SaleOrder.get_by_external_id(entity_id)
        if existing:
            return {'success': True, 'message': 'Reservation already exists'}

        # Créer la réservation
        data['id'] = entity_id
        SaleOrder.create_reservation_from_api(data)
        return {'success': True, 'message': 'Reservation created'}

    def _handle_reservation_updated(self, entity_type, entity_id, data):
        """Traiter mise à jour réservation"""
        reservation = request.env['sale.order'].sudo().get_by_external_id(entity_id)
        if not reservation:
            return {'success': False, 'error': 'Reservation not found'}

        # Mise à jour des champs
        vals = {}
        if 'guestCount' in data:
            vals['residence_guest_count'] = data['guestCount']
        if 'notes' in data:
            vals['residence_notes'] = data['notes']

        if vals:
            reservation.write(vals)

        return {'success': True, 'message': 'Reservation updated'}

    def _handle_reservation_cancelled(self, entity_type, entity_id, data):
        """Traiter annulation réservation"""
        reservation = request.env['sale.order'].sudo().get_by_external_id(entity_id)
        if not reservation:
            return {'success': False, 'error': 'Reservation not found'}

        if reservation.residence_reservation_status != 'cancelled':
            reservation.action_cancel_reservation()

        return {'success': True, 'message': 'Reservation cancelled'}

    def _handle_reservation_status_changed(self, entity_type, entity_id, data):
        """Traiter changement de statut réservation"""
        reservation = request.env['sale.order'].sudo().get_by_external_id(entity_id)
        if not reservation:
            return {'success': False, 'error': 'Reservation not found'}

        new_status = data.get('newStatus', '').lower()
        status_actions = {
            'approved': reservation.action_approve_reservation,
            'rejected': lambda: reservation.action_reject_reservation(data.get('rejectionReason')),
            'checked_in': reservation.action_checkin_reservation,
            'completed': reservation.action_complete_reservation,
            'cancelled': reservation.action_cancel_reservation,
        }

        action = status_actions.get(new_status)
        if action:
            action()
            return {'success': True, 'message': f'Reservation status changed to {new_status}'}

        return {'success': False, 'error': f'Unknown status: {new_status}'}

    # ==========================================
    # Handlers Commandes
    # ==========================================
    def _handle_order_created(self, entity_type, entity_id, data):
        """Traiter création commande"""
        ResidenceOrder = request.env['residence.order'].sudo()

        # Vérifier si existe déjà
        existing = ResidenceOrder.get_by_external_id(entity_id)
        if existing:
            return {'success': True, 'message': 'Order already exists'}

        # Créer la commande
        data['id'] = entity_id
        ResidenceOrder.create_from_api(data)
        return {'success': True, 'message': 'Order created'}

    def _handle_order_status_changed(self, entity_type, entity_id, data):
        """Traiter changement de statut commande"""
        order = request.env['residence.order'].sudo().get_by_external_id(entity_id)
        if not order:
            return {'success': False, 'error': 'Order not found'}

        new_status = data.get('newStatus', '').lower()
        status_actions = {
            'confirmed': order.action_confirm,
            'preparing': order.action_start_preparation,
            'ready': order.action_mark_ready,
            'completed': order.action_complete,
            'cancelled': lambda: order.action_cancel(data.get('cancellationReason')),
        }

        action = status_actions.get(new_status)
        if action:
            action()
            return {'success': True, 'message': f'Order status changed to {new_status}'}

        return {'success': False, 'error': f'Unknown status: {new_status}'}

    def _handle_order_cancelled(self, entity_type, entity_id, data):
        """Traiter annulation commande"""
        order = request.env['residence.order'].sudo().get_by_external_id(entity_id)
        if not order:
            return {'success': False, 'error': 'Order not found'}

        if order.state != 'cancelled':
            order.action_cancel(data.get('cancellationReason'))

        return {'success': True, 'message': 'Order cancelled'}

    # ==========================================
    # Handlers Abonnements
    # ==========================================
    def _handle_subscription_created(self, entity_type, entity_id, data):
        """Traiter création abonnement"""
        # On gère normalement les abonnements côté Odoo
        # Ce webhook sert surtout à la synchronisation
        return {'success': True, 'message': 'Subscription webhook acknowledged'}

    def _handle_subscription_cancelled(self, entity_type, entity_id, data):
        """Traiter annulation abonnement"""
        subscription = request.env['residence.member.subscription'].sudo().get_by_external_id(entity_id)
        if not subscription:
            return {'success': False, 'error': 'Subscription not found'}

        if subscription.state != 'cancelled':
            subscription.action_cancel()

        return {'success': True, 'message': 'Subscription cancelled'}
