# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request
from .main import API_PREFIX, api_auth, success_response, error_response, paginated_response

_logger = logging.getLogger(__name__)


class SubscriptionsController(http.Controller):
    """Controller pour les abonnements."""

    @http.route(f'{API_PREFIX}/subscriptions', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_subscriptions')
    def list_subscriptions(self, **kwargs):
        page = int(kwargs.get('page', 0))
        size = min(int(kwargs.get('size', 20)), 100)
        
        # Utiliser is_subscription au lieu de x_tr_is_subscription
        domain = [('is_subscription', '=', True)]
        
        if kwargs.get('memberId'):
            domain.append(('partner_id.x_tr_uuid', '=', kwargs['memberId']))
        
        if kwargs.get('status'):
            # Mapper les statuts API aux statuts Odoo 19
            # Odoo 19 utilise: 1_draft, 2_renewal, 3_progress, 4_paused, 5_expired, 6_closed, 7_upsell
            status_mapping = {
                'draft': '1_draft',
                'active': '3_progress',
                'paused': '4_paused',
                'expired': '5_expired',
                'cancelled': '6_closed',
                'progress': '3_progress',
                'renewal': '2_renewal',
                'upsell': '7_upsell'
            }
            odoo_status = status_mapping.get(kwargs['status'], kwargs['status'])
            domain.append(('subscription_state', '=', odoo_status))
        
        if kwargs.get('planId'):
            # Chercher par plan_id au lieu de x_tr_plan_id
            domain.append(('plan_id.x_tr_space_uuid', '=', kwargs['planId']))
        
        total = request.env['sale.order'].sudo().search_count(domain)
        subscriptions = request.env['sale.order'].sudo().search(
            domain, 
            offset=page * size, 
            limit=size, 
            order='create_date desc'
        )
        return paginated_response([s.to_subscription_api_dict() for s in subscriptions], total, page, size)

    @http.route(f'{API_PREFIX}/subscriptions/<string:subscription_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_subscriptions')
    def get_subscription(self, subscription_id, **kwargs):
        subscription = request.env['sale.order'].sudo().search([
            ('is_subscription', '=', True),
            '|', ('x_tr_uuid', '=', subscription_id), ('id', '=', int(subscription_id) if subscription_id.isdigit() else 0)
        ], limit=1)
        if not subscription:
            return error_response('Subscription not found', 'SUBSCRIPTION_NOT_FOUND', 404)
        return success_response(subscription.to_subscription_api_dict())

    @http.route(f'{API_PREFIX}/subscriptions', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_subscriptions')
    def create_subscription(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data)
            
            # Valider les données requises
            if not data.get('memberId'):
                return error_response('memberId is required', 'MISSING_MEMBER_ID', 400)
            
            # Rechercher le membre
            member = request.env['res.partner'].sudo().search([
                ('x_tr_is_member', '=', True),
                '|', ('x_tr_uuid', '=', data['memberId']), 
                ('id', '=', int(data['memberId']) if str(data['memberId']).isdigit() else 0)
            ], limit=1)
            
            if not member:
                return error_response('Member not found', 'MEMBER_NOT_FOUND', 404)
            
            # Rechercher le produit d'abonnement
            product_domain = [('recurring_invoice', '=', True)]
            if data.get('productName'):
                product_domain.append(('name', '=', data['productName']))
            else:
                # Par défaut, utiliser "Abonnement CEO"
                product_domain.append(('name', '=', 'Abonnement CEO'))
            
            subscription_product = request.env['product.product'].sudo().search(product_domain, limit=1)
            
            if not subscription_product:
                return error_response('Subscription product not found', 'PRODUCT_NOT_FOUND', 404)
            
            # Rechercher le plan d'abonnement
            plan_domain = []
            if data.get('planId'):
                plan_domain.append(('x_tr_space_uuid', '=', data['planId']))
            else:
                # Par défaut, rechercher un plan mensuel
                plan_domain.append(('name', 'ilike', 'mensuel'))
            
            subscription_plan = request.env['sale.subscription.plan'].sudo().search(plan_domain, limit=1)
            
            if not subscription_plan:
                # Prendre le premier plan disponible
                subscription_plan = request.env['sale.subscription.plan'].sudo().search([], limit=1)
            
            if not subscription_plan:
                return error_response('No subscription plan found', 'PLAN_NOT_FOUND', 404)
            
            # Créer l'abonnement
            subscription_vals = {
                'partner_id': member.id,
                'is_subscription': True,
                'plan_id': subscription_plan.id,
                'order_line': [(0, 0, {
                    'product_id': subscription_product.id,
                    'name': subscription_product.name,
                    'product_uom_qty': data.get('quantity', 1),
                    'product_uom_id': subscription_product.uom_id.id,
                    'price_unit': data.get('price', subscription_product.list_price),
                })],
            }
            
            # Ajouter des champs optionnels si présents
            if data.get('startDate'):
                subscription_vals['start_date'] = data['startDate']
            
            subscription = request.env['sale.order'].sudo().create(subscription_vals)
            
            # Confirmer automatiquement si demandé
            if data.get('autoConfirm', True):
                subscription.action_confirm()
            
            return success_response(subscription.to_subscription_api_dict(), 201)
            
        except Exception as e:
            _logger.error(f"Error creating subscription: {str(e)}", exc_info=True)
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/subscriptions/<string:subscription_id>/pause', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_subscriptions')
    def pause_subscription(self, subscription_id, **kwargs):
        subscription = request.env['sale.order'].sudo().search([
            ('is_subscription', '=', True),
            '|', ('x_tr_uuid', '=', subscription_id), ('id', '=', int(subscription_id) if subscription_id.isdigit() else 0)
        ], limit=1)
        if not subscription:
            return error_response('Subscription not found', 'SUBSCRIPTION_NOT_FOUND', 404)
        
        try:
            # Utiliser la méthode standard Odoo 19 pour mettre en pause
            if hasattr(subscription, 'action_pause_subscription'):
                subscription.action_pause_subscription()
            else:
                # Fallback: changer directement le statut
                subscription.write({'subscription_state': '4_paused'})
            
            return success_response(subscription.to_subscription_api_dict())
        except Exception as e:
            _logger.error(f"Error pausing subscription: {str(e)}", exc_info=True)
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/subscriptions/<string:subscription_id>/resume', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_subscriptions')
    def resume_subscription(self, subscription_id, **kwargs):
        subscription = request.env['sale.order'].sudo().search([
            ('is_subscription', '=', True),
            '|', ('x_tr_uuid', '=', subscription_id), ('id', '=', int(subscription_id) if subscription_id.isdigit() else 0)
        ], limit=1)
        if not subscription:
            return error_response('Subscription not found', 'SUBSCRIPTION_NOT_FOUND', 404)
        
        try:
            # Utiliser la méthode standard Odoo 19 pour reprendre
            if hasattr(subscription, 'action_resume_subscription'):
                subscription.action_resume_subscription()
            else:
                # Fallback: changer directement le statut
                subscription.write({'subscription_state': '3_progress'})
            
            return success_response(subscription.to_subscription_api_dict())
        except Exception as e:
            _logger.error(f"Error resuming subscription: {str(e)}", exc_info=True)
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/subscriptions/<string:subscription_id>/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_subscriptions')
    def cancel_subscription(self, subscription_id, **kwargs):
        subscription = request.env['sale.order'].sudo().search([
            ('is_subscription', '=', True),
            '|', ('x_tr_uuid', '=', subscription_id), ('id', '=', int(subscription_id) if subscription_id.isdigit() else 0)
        ], limit=1)
        if not subscription:
            return error_response('Subscription not found', 'SUBSCRIPTION_NOT_FOUND', 404)
        
        try:
            # Utiliser la méthode standard Odoo 19 pour annuler
            if hasattr(subscription, 'action_cancel_subscription'):
                subscription.action_cancel_subscription()
            elif hasattr(subscription, 'set_close'):
                subscription.set_close()
            else:
                # Fallback: changer directement le statut
                subscription.write({'subscription_state': '6_closed'})
            
            return success_response(subscription.to_subscription_api_dict())
        except Exception as e:
            _logger.error(f"Error cancelling subscription: {str(e)}", exc_info=True)
            return error_response(str(e), 'INVALID_STATUS_TRANSITION', 400)

    @http.route(f'{API_PREFIX}/members/<string:member_id>/subscriptions', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_subscriptions')
    def get_member_subscriptions(self, member_id, **kwargs):
        member = request.env['res.partner'].sudo().search([
            ('x_tr_is_member', '=', True),
            '|', ('x_tr_uuid', '=', member_id), ('id', '=', int(member_id) if member_id.isdigit() else 0)
        ], limit=1)
        if not member:
            return error_response('Member not found', 'MEMBER_NOT_FOUND', 404)
        
        kwargs['memberId'] = member.x_tr_uuid
        return self.list_subscriptions(**kwargs)