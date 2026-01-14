# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.http import request

from .main import (
    api_response, api_error, validate_api_key,
    paginate, get_pagination_params, parse_json_body
)

_logger = logging.getLogger(__name__)


class ResidenceAPISubscriptions(http.Controller):
    """APIs pour les abonnements membres"""

    # ==========================================
    # Membership Types
    # ==========================================
    @http.route('/api/v1/membership-types', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_membership_types(self):
        """Liste des types d'abonnement"""
        try:
            types = request.env['residence.membership.type'].sudo().search(
                [('active', '=', True)],
                order='sequence, name'
            )

            data = [t.to_api_dict() for t in types]
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_membership_types: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/membership-types/<string:type_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_membership_type(self, type_id):
        """Détail d'un type d'abonnement"""
        try:
            mtype = request.env['residence.membership.type'].sudo().get_by_external_id(type_id)

            if not mtype:
                # Essayer par code
                mtype = request.env['residence.membership.type'].sudo().get_by_code(type_id)

            if not mtype:
                return api_error('Type d\'abonnement non trouvé', error_code='NOT_FOUND', status=404)

            return api_response(mtype.to_api_dict())

        except Exception as e:
            _logger.error(f"Erreur get_membership_type: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Subscriptions
    # ==========================================
    @http.route('/api/v1/subscriptions', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_subscriptions(self):
        """Liste des abonnements"""
        try:
            page, size = get_pagination_params()

            domain = []

            # Filtre par membre
            member_id = request.params.get('memberId')
            if member_id:
                partner = request.env['res.partner'].sudo().get_by_external_id(member_id)
                if partner:
                    domain.append(('partner_id', '=', partner.id))

            # Filtre par statut
            state = request.params.get('state')
            if state:
                domain.append(('state', '=', state.lower()))

            # Filtre par type
            type_id = request.params.get('typeId')
            if type_id:
                mtype = request.env['residence.membership.type'].sudo().get_by_external_id(type_id)
                if mtype:
                    domain.append(('membership_type_id', '=', mtype.id))

            subscriptions = request.env['residence.member.subscription'].sudo().search(
                domain, order='date_start desc'
            )

            data = [sub.to_api_dict() for sub in subscriptions]
            result = paginate(data, page, size)

            return api_response(result)

        except Exception as e:
            _logger.error(f"Erreur get_subscriptions: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/subscriptions/<string:subscription_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_subscription(self, subscription_id):
        """Détail d'un abonnement"""
        try:
            subscription = request.env['residence.member.subscription'].sudo().get_by_external_id(subscription_id)

            if not subscription:
                return api_error('Abonnement non trouvé', error_code='NOT_FOUND', status=404)

            return api_response(subscription.to_api_dict())

        except Exception as e:
            _logger.error(f"Erreur get_subscription: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/subscriptions', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def create_subscription(self):
        """Créer un nouvel abonnement"""
        try:
            data = parse_json_body()
            if data is None:
                return api_error('Corps JSON invalide', error_code='INVALID_REQUEST', status=400)

            # Validation
            if not data.get('memberId'):
                return api_error('Champ requis: memberId', error_code='INVALID_REQUEST', status=400)

            if not data.get('membershipTypeId') and not data.get('membershipTypeCode'):
                return api_error(
                    'Champ requis: membershipTypeId ou membershipTypeCode',
                    error_code='INVALID_REQUEST',
                    status=400
                )

            # Trouver le membre
            partner = request.env['res.partner'].sudo().get_by_external_id(data['memberId'])
            if not partner:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            # Trouver le type d'abonnement
            mtype = None
            if data.get('membershipTypeId'):
                mtype = request.env['residence.membership.type'].sudo().get_by_external_id(
                    data['membershipTypeId']
                )
            elif data.get('membershipTypeCode'):
                mtype = request.env['residence.membership.type'].sudo().get_by_code(
                    data['membershipTypeCode']
                )

            if not mtype:
                return api_error(
                    'Type d\'abonnement non trouvé',
                    error_code='MEMBERSHIP_TYPE_NOT_FOUND',
                    status=404
                )

            # Vérifier si un abonnement actif existe déjà
            existing = request.env['residence.member.subscription'].sudo().search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'active')
            ], limit=1)

            if existing:
                return api_error(
                    'Un abonnement actif existe déjà pour ce membre',
                    error_code='SUBSCRIPTION_EXISTS',
                    status=409
                )

            # Date de début
            from odoo import fields
            date_start = data.get('dateStart')
            if date_start:
                try:
                    from datetime import datetime
                    date_start = datetime.fromisoformat(date_start.replace('Z', '+00:00')).date()
                except ValueError:
                    date_start = fields.Date.today()
            else:
                date_start = fields.Date.today()

            # Créer l'abonnement
            subscription = request.env['residence.member.subscription'].sudo().create({
                'partner_id': partner.id,
                'membership_type_id': mtype.id,
                'date_start': date_start,
                'auto_renew': data.get('autoRenew', False),
                'state': 'draft'
            })

            # Activer automatiquement si demandé
            if data.get('activateNow', True):
                subscription.action_activate()

            # Créer le devis si demandé
            if data.get('createSaleOrder', True):
                subscription.action_create_sale_order()

            # Envoyer webhook
            config = request.env['residence.config'].sudo().get_config()
            if config:
                config.send_webhook(
                    event_type='SUBSCRIPTION_CREATED',
                    entity_type='subscription',
                    entity_id=subscription.external_id,
                    data=subscription.to_api_dict(),
                    new_status=subscription.state.upper()
                )

            return api_response(
                subscription.to_api_dict(),
                message='Abonnement créé avec succès',
                status=201
            )

        except Exception as e:
            _logger.error(f"Erreur create_subscription: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/subscriptions/<string:subscription_id>/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def cancel_subscription(self, subscription_id):
        """Annuler un abonnement"""
        try:
            subscription = request.env['residence.member.subscription'].sudo().get_by_external_id(subscription_id)

            if not subscription:
                return api_error('Abonnement non trouvé', error_code='NOT_FOUND', status=404)

            if subscription.state == 'cancelled':
                return api_error('Cet abonnement est déjà annulé', error_code='INVALID_STATUS', status=400)

            subscription.action_cancel()

            # Envoyer webhook
            config = request.env['residence.config'].sudo().get_config()
            if config:
                config.send_webhook(
                    event_type='SUBSCRIPTION_CANCELLED',
                    entity_type='subscription',
                    entity_id=subscription.external_id,
                    data=subscription.to_api_dict(),
                    new_status='CANCELLED'
                )

            return api_response(
                subscription.to_api_dict(),
                message='Abonnement annulé'
            )

        except Exception as e:
            _logger.error(f"Erreur cancel_subscription: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/subscriptions/<string:subscription_id>/renew', type='http', auth='public', methods=['POST'], csrf=False)
    @validate_api_key
    def renew_subscription(self, subscription_id):
        """Renouveler un abonnement"""
        try:
            subscription = request.env['residence.member.subscription'].sudo().get_by_external_id(subscription_id)

            if not subscription:
                return api_error('Abonnement non trouvé', error_code='NOT_FOUND', status=404)

            if subscription.state not in ('active', 'expired'):
                return api_error(
                    'Seuls les abonnements actifs ou expirés peuvent être renouvelés',
                    error_code='INVALID_STATUS',
                    status=400
                )

            # Calculer la nouvelle date de début
            from odoo import fields
            from dateutil.relativedelta import relativedelta

            if subscription.state == 'expired' or not subscription.date_end:
                new_start = fields.Date.today()
            else:
                new_start = subscription.date_end

            # Créer un nouvel abonnement
            new_subscription = request.env['residence.member.subscription'].sudo().create({
                'partner_id': subscription.partner_id.id,
                'membership_type_id': subscription.membership_type_id.id,
                'date_start': new_start,
                'auto_renew': subscription.auto_renew,
                'state': 'draft'
            })

            new_subscription.action_activate()

            # Terminer l'ancien si actif
            if subscription.state == 'active':
                subscription.state = 'expired'

            # Envoyer webhook
            config = request.env['residence.config'].sudo().get_config()
            if config:
                config.send_webhook(
                    event_type='SUBSCRIPTION_RENEWED',
                    entity_type='subscription',
                    entity_id=new_subscription.external_id,
                    data=new_subscription.to_api_dict(),
                    new_status='ACTIVE'
                )

            return api_response(
                new_subscription.to_api_dict(),
                message='Abonnement renouvelé avec succès',
                status=201
            )

        except Exception as e:
            _logger.error(f"Erreur renew_subscription: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Member Current Subscription
    # ==========================================
    @http.route('/api/v1/members/<string:member_id>/subscription', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_member_subscription(self, member_id):
        """Abonnement actif d'un membre"""
        try:
            partner = request.env['res.partner'].sudo().get_by_external_id(member_id)

            if not partner:
                return api_error('Membre non trouvé', error_code='MEMBER_NOT_FOUND', status=404)

            subscription = request.env['residence.member.subscription'].sudo().search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'active')
            ], limit=1, order='date_start desc')

            if not subscription:
                return api_response(None, message='Aucun abonnement actif')

            return api_response(subscription.to_api_dict())

        except Exception as e:
            _logger.error(f"Erreur get_member_subscription: {str(e)}")
            return api_error(str(e), status=500)
