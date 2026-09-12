# -*- coding: utf-8 -*-
"""Point d'entrée appelé par le front POS pour déposer ses événements.

L'appel est volontairement tolérant : une erreur d'audit ne doit jamais
empêcher un serveur d'encaisser. Le front n'attend d'ailleurs pas la réponse
sauf au moment de la validation.
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_EVENTS_PER_CALL = 200


class PosAuditController(http.Controller):

    @http.route('/laresidence/pos_audit/log', type='jsonrpc', auth='user')
    def log(self, events=None):
        if not events:
            return {'success': True, 'written': 0}

        if len(events) > MAX_EVENTS_PER_CALL:
            events = events[:MAX_EVENTS_PER_CALL]

        try:
            written = request.env['laresidence.pos.audit'].sudo().log_events(
                events,
                ip_address=request.httprequest.remote_addr,
                user_id=request.env.user.id,
                user_agent=str(request.httprequest.user_agent or ''),
                origin_path=request.httprequest.path,
            )
        except Exception:
            _logger.exception("laresidence_pos_audit : échec d'enregistrement d'un lot d'événements")
            return {'success': False, 'written': 0}

        return {'success': True, 'written': written}
