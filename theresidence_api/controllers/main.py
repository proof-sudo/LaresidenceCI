# -*- coding: utf-8 -*-

import json
import logging
from functools import wraps
from datetime import datetime

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def api_response(data=None, message=None, success=True, status=200):
    """Générer une réponse API standardisée"""
    response_data = {
        'success': success,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }

    if message:
        response_data['message'] = message

    if data is not None:
        if isinstance(data, list):
            response_data['data'] = data
            response_data['count'] = len(data)
        elif isinstance(data, dict) and 'content' in data:
            # Réponse paginée
            response_data.update(data)
        else:
            response_data['data'] = data

    return Response(
        json.dumps(response_data, default=str),
        status=status,
        headers=[('Content-Type', 'application/json')]
    )


def api_error(message, error_code=None, status=400):
    """Générer une réponse d'erreur API"""
    response_data = {
        'success': False,
        'message': message,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }

    if error_code:
        response_data['errorCode'] = error_code

    return Response(
        json.dumps(response_data),
        status=status,
        headers=[('Content-Type', 'application/json')]
    )


def validate_api_key(func):
    """Décorateur pour valider la clé API"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Récupérer la clé API depuis les headers
        api_key = request.httprequest.headers.get('X-API-Key')

        if not api_key:
            return api_error(
                'Clé API manquante',
                error_code='UNAUTHORIZED',
                status=401
            )

        # Valider la clé API
        config = request.env['residence.config'].sudo().validate_api_key(api_key)
        if not config:
            return api_error(
                'Clé API invalide',
                error_code='UNAUTHORIZED',
                status=401
            )

        # Stocker la config dans le contexte
        request.residence_config = config

        return func(*args, **kwargs)

    return wrapper


def paginate(records, page=0, size=20):
    """Paginer les résultats"""
    total_count = len(records)
    page_count = (total_count + size - 1) // size if size > 0 else 1

    # Limiter la page
    if page < 0:
        page = 0
    if page >= page_count and page_count > 0:
        page = page_count - 1

    # Extraire la page
    start = page * size
    end = start + size
    paginated_records = records[start:end]

    return {
        'content': paginated_records,
        'totalCount': total_count,
        'pagingInfo': {
            'size': size,
            'pageCount': page_count,
            'currentPage': page,
            'hasPrevious': page > 0,
            'hasNext': page < page_count - 1
        }
    }


def get_pagination_params():
    """Extraire les paramètres de pagination de la requête"""
    try:
        page = int(request.params.get('page', 0))
        size = int(request.params.get('size', 20))

        # Limites
        if page < 0:
            page = 0
        if size < 1:
            size = 1
        if size > 100:
            size = 100

        return page, size
    except (ValueError, TypeError):
        return 0, 20


def get_locale():
    """Extraire la locale de la requête"""
    return request.httprequest.headers.get('Accept-Language', 'fr')


def parse_json_body():
    """Parser le corps JSON de la requête"""
    try:
        if request.httprequest.data:
            return json.loads(request.httprequest.data)
        return {}
    except json.JSONDecodeError:
        return None


class ResidenceAPIBase(http.Controller):
    """Controller de base pour les APIs The Residence"""

    def _get_config(self):
        """Récupérer la configuration API"""
        if hasattr(request, 'residence_config'):
            return request.residence_config
        return request.env['residence.config'].sudo().get_config()

    def _log_request(self, endpoint, method='GET'):
        """Logger une requête API"""
        _logger.info(f"API Request: {method} {endpoint}")

    @http.route('/api/v1/health', type='http', auth='public', methods=['GET'], csrf=False)
    def health_check(self):
        """Endpoint de santé - pas d'authentification requise"""
        return api_response({
            'status': 'healthy',
            'version': '1.0.0',
            'odoo_version': '19.0'
        })

    @http.route('/api/v1/info', type='http', auth='public', methods=['GET'], csrf=False)
    @validate_api_key
    def api_info(self):
        """Informations sur l'API"""
        return api_response({
            'name': 'The Residence API',
            'version': '1.0.0',
            'endpoints': {
                'reference': [
                    'GET /api/v1/spaces',
                    'GET /api/v1/spaces/{id}',
                    'GET /api/v1/spaces/{id}/availability',
                    'GET /api/v1/menu-kinds',
                    'GET /api/v1/menu-categories',
                    'GET /api/v1/menu-items',
                    'GET /api/v1/members',
                    'GET /api/v1/members/{id}',
                ],
                'reservations': [
                    'GET /api/v1/reservations',
                    'GET /api/v1/reservations/{id}',
                    'POST /api/v1/reservations',
                    'PUT /api/v1/reservations/{id}',
                    'DELETE /api/v1/reservations/{id}',
                    'POST /api/v1/reservations/{id}/approve',
                    'POST /api/v1/reservations/{id}/reject',
                    'POST /api/v1/reservations/{id}/check-in',
                ],
                'orders': [
                    'GET /api/v1/orders',
                    'GET /api/v1/orders/{id}',
                    'POST /api/v1/orders',
                    'POST /api/v1/orders/{id}/confirm',
                    'POST /api/v1/orders/{id}/ready',
                    'POST /api/v1/orders/{id}/complete',
                    'POST /api/v1/orders/{id}/cancel',
                ],
                'members': [
                    'POST /api/v1/members',
                    'PUT /api/v1/members/{id}',
                ],
                'subscriptions': [
                    'GET /api/v1/membership-types',
                    'GET /api/v1/subscriptions',
                    'POST /api/v1/subscriptions',
                ],
                'webhook': [
                    'POST /api/v1/webhook',
                ]
            }
        })
