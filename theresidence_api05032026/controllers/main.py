# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from functools import wraps
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

API_PREFIX = '/v1/external'


def json_response(data, status=200):
    """Retourne une réponse JSON standardisée."""
    body = json.dumps(data, default=str, ensure_ascii=False)
    return Response(body, status=status, content_type='application/json; charset=utf-8')


def error_response(message, error_code, status=400):
    """Retourne une réponse d'erreur JSON."""
    return json_response({
        'success': False,
        'message': message,
        'errorCode': error_code,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }, status=status)

def success_response(data, status=200, headers=None):
    payload = {
        'success': True,
        'data': data,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }

    response = Response(
        json.dumps(payload, ensure_ascii=False),
        status=status,
        content_type='application/json; charset=utf-8'
    )

    # 🔥 Headers ANTI-CACHE (critiques pour mobile & Postman)
    response.headers.update({
        'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
        'Pragma': 'no-cache',
        'Expires': '0'
    })

    # Headers custom si besoin
    if headers:
        response.headers.update(headers)

    return response
# def success_response(data, status=200):
#     """Retourne une réponse de succès JSON."""
#     return json_response({
#         'success': True,
#         'data': data,
#         'timestamp': datetime.utcnow().isoformat() + 'Z'
#     }, status=status)


def paginated_response(items, total, page, size):
    """Retourne une réponse paginée."""
    page_count = (total + size - 1) // size if size > 0 else 0
    return json_response({
        'success': True,
        'content': items,
        'totalCount': total,
        'pagingInfo': {
            'size': size,
            'pageCount': page_count,
            'currentPage': page,
            'hasPrevious': page > 0,
            'hasNext': page < page_count - 1
        },
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    })


def api_auth(permission=None):
    """Décorateur pour l'authentification API."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            api_key = request.httprequest.headers.get('X-API-Key')
            if not api_key:
                return error_response('API key required', 'UNAUTHORIZED', 401)
            
            key_record = request.env['theresidence.api.key'].sudo().validate_key(api_key)
            if not key_record:
                return error_response('Invalid API key', 'UNAUTHORIZED', 401)
            
            if permission and not key_record.has_permission(permission):
                return error_response(f'Permission denied: {permission}', 'FORBIDDEN', 403)
            
            request.api_key = key_record
            return func(*args, **kwargs)
        return wrapper
    return decorator


class MainController(http.Controller):
    """Controller principal avec health check et info."""

    @http.route(f'{API_PREFIX}/health', type='http', auth='public', methods=['GET'], csrf=False)
    def health_check(self, **kwargs):
        """Endpoint de vérification de l'état de l'API."""
        return success_response({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'version': '19.0.1.0.0'
        })

    @http.route(f'{API_PREFIX}/info', type='http', auth='public', methods=['GET'], csrf=False)
    @api_auth()
    def api_info(self, **kwargs):
        """Retourne les informations sur la clé API."""
        key = request.api_key
        return success_response({
            'keyName': key.name,
            'permissions': {
                'members': {'read': key.can_read_members, 'write': key.can_write_members},
                'spaces': {'read': key.can_read_spaces},
                'menu': {'read': key.can_read_menu},
                'reservations': {'read': key.can_read_reservations, 'write': key.can_write_reservations},
                'orders': {'read': key.can_read_orders, 'write': key.can_write_orders},
                'subscriptions': {'read': key.can_read_subscriptions, 'write': key.can_write_subscriptions},
                'webhooks': {'manage': key.can_manage_webhooks}
            }
        })
