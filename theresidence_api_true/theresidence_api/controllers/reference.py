# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request
from .main import API_PREFIX, api_auth, success_response, error_response, paginated_response
import base64

_logger = logging.getLogger(__name__)


class SpaceImageController(http.Controller):

    @http.route(
        '/api/v1/spaces/<string:space_id>/image',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False
    )
    def get_space_image(self, space_id, **kwargs):
        domain = [
            ('x_tr_is_space', '=', True),
            '|',
            ('x_tr_space_uuid', '=', space_id),
            ('id', '=', int(space_id) if space_id.isdigit() else 0)
        ]

        space = request.env['product.template'].sudo().search(domain, limit=1)
        if not space or not space.image_1920:
            return request.not_found()

        image = base64.b64decode(space.image_1920)

        return request.make_response(
            image,
            headers=[
                ('Content-Type', 'image/png'),
                ('Cache-Control', 'public, max-age=86400'),
            ]
        )


class ReferenceController(http.Controller):
    """Controller pour les données de référence."""

    def _fresh_env(self):
        """
        Rafraîchit l'environnement Odoo pour éviter les problèmes de cache.
        Critique pour garantir que les données retournées sont à jour.
        """
        env = request.env
        env.cr.commit()          # Rend visibles les écritures en attente
        env.invalidate_all()     # Purge le cache ORM
        env.clear()              # Reset l'environnement
        return env

    # === MEMBERSHIP TYPES ===
    
    @http.route(f'{API_PREFIX}/membership-types', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_members')
    def list_membership_types(self, **kwargs):
        """Liste tous les types de membership actifs."""
        types = request.env['theresidence.membership.type'].sudo().search([('active', '=', True)], order='sort_order')
        return success_response([t.to_api_dict() for t in types])

    @http.route(f'{API_PREFIX}/membership-types/<string:type_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_members')
    def get_membership_type(self, type_id, **kwargs):
        """Récupère un type de membership spécifique."""
        mtype = request.env['theresidence.membership.type'].sudo().search([
            '|', ('x_uuid', '=', type_id), ('code', '=', type_id)
        ], limit=1)
        if not mtype:
            return error_response('Membership type not found', 'NOT_FOUND', 404)
        return success_response(mtype.to_api_dict())

    # === SPACES ===
    
    @http.route(f'{API_PREFIX}/reference/spaces', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_spaces')
    def list_spaces(self, **kwargs):
        """Liste tous les espaces actifs."""
        domain = [('x_tr_is_space', '=', True), ('active', '=', True)]
        if kwargs.get('type'):
            domain.append(('x_tr_space_type_id.code', '=', kwargs['type']))
        spaces = request.env['product.template'].sudo().search(domain)
        return success_response([s.to_space_api_dict() for s in spaces])

    @http.route(f'{API_PREFIX}/reference/spaces/<string:space_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_spaces')
    def get_space(self, space_id, **kwargs):
        """Récupère un espace spécifique."""
        space = request.env['product.template'].sudo().search([
            ('x_tr_is_space', '=', True),
            '|', ('x_tr_space_uuid', '=', space_id), ('id', '=', int(space_id) if space_id.isdigit() else 0)
        ], limit=1)
        if not space:
            return error_response('Space not found', 'SPACE_NOT_FOUND', 404)
        return success_response(space.to_space_api_dict())

    @http.route(f'{API_PREFIX}/reference/spaces/<string:space_id>/availability', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_spaces')
    def check_space_availability(self, space_id, **kwargs):
        """Vérifie la disponibilité d'un espace."""
        space = request.env['product.template'].sudo().search([
            ('x_tr_is_space', '=', True),
            '|', ('x_tr_space_uuid', '=', space_id), ('id', '=', int(space_id) if space_id.isdigit() else 0)
        ], limit=1)
        if not space:
            return error_response('Space not found', 'SPACE_NOT_FOUND', 404)
        
        start_time = kwargs.get('startTime')
        end_time = kwargs.get('endTime')
        if not start_time or not end_time:
            return error_response('startTime and endTime are required', 'INVALID_REQUEST', 400)
        
        return success_response(space.check_availability(start_time, end_time))

    # === RESERVATION OPTIONS ===
    
    @http.route(f'{API_PREFIX}/reservation-options', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_reservations')
    def list_reservation_options(self, **kwargs):
        """Liste les options de réservation."""
        domain = [('active', '=', True)]
        if kwargs.get('scope'):
            domain.append(('scope', '=', kwargs['scope']))
        options = request.env['theresidence.reservation.option.def'].sudo().search(domain, order='sequence')
        return success_response([o.to_api_dict() for o in options])

    @http.route(f'{API_PREFIX}/reservation-options/<string:option_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_reservations')
    def get_reservation_option(self, option_id, **kwargs):
        """Récupère une option de réservation."""
        opt = request.env['theresidence.reservation.option.def'].sudo().search([
            '|', ('x_uuid', '=', option_id), ('code', '=', option_id)
        ], limit=1)
        if not opt:
            return error_response('Option not found', 'NOT_FOUND', 404)
        return success_response(opt.to_api_dict())

    # ========================================================================
    # === MENU / CATEGORIES POS ===
    # ========================================================================
    
    @http.route(f'{API_PREFIX}/reference/menu-kinds', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_menu')
    def list_menu_kinds(self, **kwargs):
        """
        Liste toutes les catégories racines (menu kinds).
        
        GET /api/v1/reference/menu-kinds
        
        Retourne les catégories POS de niveau 1 (sans parent).
        Utilisé pour afficher les grands types de menu (Boissons, Plats, Desserts, etc.)
        """
        env = self._fresh_env()
        
        kinds = env['pos.category'].sudo().search([
            ('parent_id', '=', False)
        ], order='sequence')

        return success_response([k.to_category_api_dict() for k in kinds])

    @http.route(f'{API_PREFIX}/reference/menu-kinds/<string:kind_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_menu')
    def get_menu_kind(self, kind_id, **kwargs):
        """
        Récupère une catégorie racine spécifique.
        
        GET /api/v1/reference/menu-kinds/{kind_id}
        
        Paramètres:
            kind_id: UUID ou ID numérique de la catégorie racine
        """
        env = self._fresh_env()
        
        kind = env['pos.category'].sudo().search([
            '|',
            ('x_tr_uuid', '=', kind_id),
            ('id', '=', int(kind_id) if kind_id.isdigit() else 0),
            ('parent_id', '=', False)
        ], limit=1)

        if not kind:
            return error_response('Menu kind not found', 'NOT_FOUND', 404)

        return success_response(kind.to_category_api_dict())

    @http.route(f'{API_PREFIX}/reference/menu-kinds/<string:kind_id>/categories', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_menu')
    def list_categories_by_kind(self, kind_id, **kwargs):
        """
        Liste les sous-catégories d'un menu kind.
        
        GET /api/v1/reference/menu-kinds/{kind_id}/categories
        
        Retourne toutes les catégories enfants directes d'une catégorie racine.
        Par exemple: pour "Boissons", retourne ["Boissons chaudes", "Boissons froides", etc.]
        
        Paramètres:
            kind_id: UUID ou ID numérique de la catégorie racine
        """
        env = self._fresh_env()

        kind = env['pos.category'].sudo().search([
            '|',
            ('x_tr_uuid', '=', kind_id),
            ('id', '=', int(kind_id) if kind_id.isdigit() else 0),
            ('parent_id', '=', False)
        ], limit=1)

        if not kind:
            return error_response('Menu kind not found', 'NOT_FOUND', 404)

        categories = env['pos.category'].sudo().search(
            [('parent_id', '=', kind.id)],
            order='sequence'
        )

        return success_response([
                    d for d in (c.to_category_api_dict() for c in categories) if d
                ])

    @http.route(f'{API_PREFIX}/reference/menu-categories', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_menu')
    def list_menu_categories(self, **kwargs):

        env = self._fresh_env()

        categories = env['pos.category'].sudo().search([], order='sequence, id')

        # 🔥 LOG COMPLET DB
        _logger.info("===== POS CATEGORIES RAW FROM DB =====")
        for c in categories:
            _logger.info(
                "ID=%s | UUID=%s | NAME=%s | PARENT_ID=%s | PARENT_NAME=%s | SEQUENCE=%s",
                c.id,
                c.x_tr_uuid,
                c.name,
                c.parent_id.id if c.parent_id else None,
                c.parent_id.name if c.parent_id else None,
                c.sequence
            )

        # 🔥 LOG APRES MAPPING API
        result = []
        _logger.info("===== POS CATEGORIES AFTER API MAPPING =====")
        for c in categories:
            try:
                data = c.to_category_api_dict()
                _logger.info("API_CATEGORY=%s", data)
                if data:
                    result.append(data)
            except Exception as e:
                _logger.error("ERROR MAPPING CATEGORY ID %s : %s", c.id, str(e))

        return success_response(result)

    # === MENU ITEMS (PRODUCTS) ===

    @http.route(f'{API_PREFIX}/reference/menu-items', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_menu')
    def list_menu_items(self, **kwargs):
        """
        Liste tous les produits disponibles en POS.
        
        GET /api/v1/reference/menu-items
        
        Retourne tous les produits actifs et disponibles dans le point de vente.
        """
        env = self._fresh_env()
        env['product.product'].flush_model()

        products = env['product.product'].sudo().search([
            ('available_in_pos', '=', True),
            ('active', '=', True)
        ], order='sequence')

        return success_response([p.to_menu_item_api_dict() for p in products])

    @http.route(f'{API_PREFIX}/reference/menu-items/<string:item_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_menu')
    def get_menu_item(self, item_id, **kwargs):
        """
        Récupère un produit spécifique.
        
        GET /api/v1/reference/menu-items/{item_id}
        
        Paramètres:
            item_id: ID numérique du produit
        """
        product = request.env['product.product'].sudo().browse(int(item_id) if item_id.isdigit() else 0)
        if not product.exists():
            return error_response('Menu item not found', 'NOT_FOUND', 404)
        return success_response(product.to_menu_item_api_dict())

    # === MEMBERS ===
    
    @http.route(f'{API_PREFIX}/reference/members', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_members')
    def list_members(self, **kwargs):
        """Liste les membres avec pagination et recherche."""
        page = int(kwargs.get('page', 0))
        size = min(int(kwargs.get('size', 20)), 100)
        
        domain = [('x_tr_is_member', '=', True)]
        if kwargs.get('query'):
            q = kwargs['query']
            domain.append('|')
            domain.append('|')
            domain.append(('name', 'ilike', q))
            domain.append(('email', 'ilike', q))
            domain.append(('company_name', 'ilike', q))
        
        total = request.env['res.partner'].sudo().search_count(domain)
        members = request.env['res.partner'].sudo().search(domain, offset=page * size, limit=size)
        return paginated_response([m.to_member_api_dict() for m in members], total, page, size)

    @http.route(f'{API_PREFIX}/reference/members/<string:member_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_members')
    def get_member(self, member_id, **kwargs):
        """Récupère un membre spécifique."""
        member = request.env['res.partner'].sudo().search([
            ('x_tr_is_member', '=', True),
            '|', ('x_tr_uuid', '=', member_id), ('id', '=', int(member_id) if member_id.isdigit() else 0)
        ], limit=1)
        if not member:
            return error_response('Member not found', 'MEMBER_NOT_FOUND', 404)
        return success_response(member.to_member_api_dict())

    @http.route(f'{API_PREFIX}/reference/members', type='http', auth='public', methods=['POST'], csrf=False)
    @api_auth('write_members')
    def create_member(self, **kwargs):
        """Crée un nouveau membre."""
        try:
            data = json.loads(request.httprequest.data)
            member = request.env['res.partner'].sudo().create_member_from_api(data)
            return success_response(member.to_member_api_dict(), 201)
        except Exception as e:
            _logger.error(f"Error creating member: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    @http.route(f'{API_PREFIX}/reference/members/<string:member_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    @api_auth('write_members')
    def update_member(self, member_id, **kwargs):
        """Met à jour un membre existant."""
        member = request.env['res.partner'].sudo().search([
            ('x_tr_is_member', '=', True),
            '|', ('x_tr_uuid', '=', member_id), ('id', '=', int(member_id) if member_id.isdigit() else 0)
        ], limit=1)
        if not member:
            return error_response('Member not found', 'MEMBER_NOT_FOUND', 404)
        
        try:
            data = json.loads(request.httprequest.data)
            vals = {}
            if 'firstName' in data or 'lastName' in data:
                fn = data.get('firstName', (member.name or '').split(' ')[0])
                ln = data.get('lastName', ' '.join((member.name or '').split(' ')[1:]))
                vals['name'] = f"{fn} {ln}".strip()
            if 'email' in data:
                vals['email'] = data['email']
            if 'phone' in data:
                vals['phone'] = data['phone']
                vals['mobile'] = data['phone']
            if 'companyName' in data:
                vals['company_name'] = data['companyName']
            if 'jobTitle' in data:
                vals['function'] = data['jobTitle']
            if 'membershipTypeCode' in data:
                mtype = request.env['theresidence.membership.type'].sudo().search([('code', '=', data['membershipTypeCode'])], limit=1)
                if mtype:
                    vals['x_tr_membership_type_id'] = mtype.id
            
            if vals:
                member.write(vals)
            return success_response(member.to_member_api_dict())
        except Exception as e:
            _logger.error(f"Error updating member: {str(e)}")
            return error_response(str(e), 'INVALID_REQUEST', 400)

    # === SUBSCRIPTION PLANS ===
    
    @http.route(f'{API_PREFIX}/subscription-plans', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_subscriptions')
    def list_subscription_plans(self, **kwargs):
        """Liste les plans d'abonnement."""
        plans = request.env['product.template'].sudo().search([
            ('x_tr_is_subscription_plan', '=', True),
            ('active', '=', True)
        ])
        return success_response([p.to_subscription_plan_api_dict() for p in plans])

    @http.route(f'{API_PREFIX}/subscription-plans/<string:plan_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth('read_subscriptions')
    def get_subscription_plan(self, plan_id, **kwargs):
        """Récupère un plan d'abonnement spécifique."""
        plan = request.env['product.template'].sudo().search([
            ('x_tr_is_subscription_plan', '=', True),
            '|', ('x_tr_space_uuid', '=', plan_id), ('id', '=', int(plan_id) if plan_id.isdigit() else 0)
        ], limit=1)
        if not plan:
            return error_response('Plan not found', 'NOT_FOUND', 404)
        return success_response(plan.to_subscription_plan_api_dict())