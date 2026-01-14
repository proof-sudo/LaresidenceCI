# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.http import request

from .main import (
    api_response, api_error, validate_api_key,
    paginate, get_pagination_params, get_locale
)

_logger = logging.getLogger(__name__)


class ResidenceAPIMenu(http.Controller):
    """APIs pour les menus restaurant"""

    # ==========================================
    # Menu Kinds (Types de menu)
    # ==========================================
    @http.route('/api/v1/menu-kinds', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_menu_kinds(self):
        """Liste des types de menu"""
        try:
            kinds = request.env['residence.menu.kind'].sudo().search([])
            data = [kind.to_api_dict() for kind in kinds]
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_menu_kinds: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/menu-kinds/<string:kind_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_menu_kind(self, kind_id):
        """Détail d'un type de menu"""
        try:
            kind = request.env['residence.menu.kind'].sudo().get_by_external_id(kind_id)
            if not kind:
                return api_error('Type de menu non trouvé', error_code='NOT_FOUND', status=404)

            data = kind.to_api_dict()
            # Ajouter les catégories
            data['categories'] = [cat.to_api_dict() for cat in kind.category_ids]

            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_menu_kind: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/menu-kinds/<string:kind_id>/categories', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_menu_kind_categories(self, kind_id):
        """Catégories d'un type de menu"""
        try:
            kind = request.env['residence.menu.kind'].sudo().get_by_external_id(kind_id)
            if not kind:
                return api_error('Type de menu non trouvé', error_code='NOT_FOUND', status=404)

            data = [cat.to_api_dict() for cat in kind.category_ids]
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_menu_kind_categories: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Menu Categories (Catégories)
    # ==========================================
    @http.route('/api/v1/menu-categories', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_menu_categories(self):
        """Liste des catégories de menu"""
        try:
            page, size = get_pagination_params()

            # Filtres
            domain = []

            kind_id = request.params.get('kindId')
            if kind_id:
                kind = request.env['residence.menu.kind'].sudo().get_by_external_id(kind_id)
                if kind:
                    domain.append(('kind_id', '=', kind.id))

            categories = request.env['residence.menu.category'].sudo().search(domain, order='sequence, name')

            data = [cat.to_api_dict() for cat in categories]
            result = paginate(data, page, size)

            return api_response(result)

        except Exception as e:
            _logger.error(f"Erreur get_menu_categories: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/menu-categories/<string:category_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_menu_category(self, category_id):
        """Détail d'une catégorie de menu"""
        try:
            category = request.env['residence.menu.category'].sudo().get_by_external_id(category_id)
            if not category:
                return api_error('Catégorie non trouvée', error_code='NOT_FOUND', status=404)

            data = category.to_api_dict()

            # Ajouter les articles
            items = request.env['product.template'].sudo().search([
                ('is_residence_menu_item', '=', True),
                ('residence_menu_category_id', '=', category.id)
            ])
            data['items'] = [item.to_menu_item_api_dict() for item in items]

            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_menu_category: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/menu-categories/<string:category_id>/items', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_menu_category_items(self, category_id):
        """Articles d'une catégorie de menu"""
        try:
            category = request.env['residence.menu.category'].sudo().get_by_external_id(category_id)
            if not category:
                return api_error('Catégorie non trouvée', error_code='NOT_FOUND', status=404)

            items = request.env['product.template'].sudo().search([
                ('is_residence_menu_item', '=', True),
                ('residence_menu_category_id', '=', category.id)
            ], order='sequence, name')

            data = [item.to_menu_item_api_dict() for item in items]
            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_menu_category_items: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Menu Items (Articles)
    # ==========================================
    @http.route('/api/v1/menu-items', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_menu_items(self):
        """Liste des articles du menu"""
        try:
            page, size = get_pagination_params()

            # Filtres
            domain = [('is_residence_menu_item', '=', True)]

            category_id = request.params.get('categoryId')
            if category_id:
                category = request.env['residence.menu.category'].sudo().get_by_external_id(category_id)
                if category:
                    domain.append(('residence_menu_category_id', '=', category.id))

            kind_id = request.params.get('kindId')
            if kind_id:
                kind = request.env['residence.menu.kind'].sudo().get_by_external_id(kind_id)
                if kind:
                    domain.append(('residence_menu_kind_id', '=', kind.id))

            # Filtre disponibilité
            available_only = request.params.get('availableOnly', 'false').lower() == 'true'
            if available_only:
                domain.append(('residence_is_available', '=', True))

            # Filtres diététiques
            if request.params.get('vegetarian', 'false').lower() == 'true':
                domain.append(('residence_is_vegetarian', '=', True))
            if request.params.get('vegan', 'false').lower() == 'true':
                domain.append(('residence_is_vegan', '=', True))
            if request.params.get('glutenFree', 'false').lower() == 'true':
                domain.append(('residence_is_gluten_free', '=', True))

            # Recherche par nom
            search_query = request.params.get('query')
            if search_query:
                domain.append(('name', 'ilike', search_query))

            items = request.env['product.template'].sudo().search(domain, order='sequence, name')

            data = [item.to_menu_item_api_dict() for item in items]
            result = paginate(data, page, size)

            return api_response(result)

        except Exception as e:
            _logger.error(f"Erreur get_menu_items: {str(e)}")
            return api_error(str(e), status=500)

    @http.route('/api/v1/menu-items/<string:item_id>', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_menu_item(self, item_id):
        """Détail d'un article du menu"""
        try:
            item = request.env['product.template'].sudo().get_by_external_id(item_id)

            if not item or not item.is_residence_menu_item:
                return api_error('Article non trouvé', error_code='NOT_FOUND', status=404)

            data = item.to_menu_item_api_dict()

            # Ajouter des détails supplémentaires
            data['fullDescription'] = item.description or ''
            data['nutritionalInfo'] = item.description_purchase or ''

            return api_response(data)

        except Exception as e:
            _logger.error(f"Erreur get_menu_item: {str(e)}")
            return api_error(str(e), status=500)

    # ==========================================
    # Full Menu (Menu complet)
    # ==========================================
    @http.route('/api/v1/full-menu', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def get_full_menu(self):
        """Menu complet structuré par types et catégories"""
        try:
            kinds = request.env['residence.menu.kind'].sudo().search([], order='sequence, name')

            menu_data = []
            for kind in kinds:
                kind_data = kind.to_api_dict()
                kind_data['categories'] = []

                for category in kind.category_ids:
                    cat_data = category.to_api_dict()

                    # Récupérer les articles de cette catégorie
                    items = request.env['product.template'].sudo().search([
                        ('is_residence_menu_item', '=', True),
                        ('residence_menu_category_id', '=', category.id)
                    ], order='sequence, name')

                    cat_data['items'] = [item.to_menu_item_api_dict() for item in items]
                    kind_data['categories'].append(cat_data)

                menu_data.append(kind_data)

            return api_response(menu_data)

        except Exception as e:
            _logger.error(f"Erreur get_full_menu: {str(e)}")
            return api_error(str(e), status=500)
