# -*- coding: utf-8 -*-
"""
Endpoints appelés par l'agent Python tournant sur le PC local (pos_print_relay_agent.py).

Authentification par jeton partagé (pas de session utilisateur : l'agent tourne
en tâche de fond, sans navigateur). Le jeton est stocké dans un paramètre système
et doit être copié dans la config de l'agent.
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PARAM_TOKEN = 'pos_epos_direct.relay_token'


class PosPrintRelayController(http.Controller):

    def _check_token(self, token):
        expected = request.env['ir.config_parameter'].sudo().get_param(PARAM_TOKEN)
        return bool(expected) and token == expected

    @http.route('/pos_print_relay/pending', type='jsonrpc', auth='public', csrf=False)
    def pending(self, token=None, limit=10):
        if not self._check_token(token):
            return {'success': False, 'error': 'invalid_token'}

        jobs = request.env['pos.print.job'].sudo().search(
            [('status', '=', 'pending')], order='create_date asc', limit=int(limit)
        )
        return {
            'success': True,
            'jobs': [
                {'id': j.id, 'ip': j.ip, 'xml': j.xml, 'job_type': j.job_type}
                for j in jobs
            ],
        }

    @http.route('/pos_print_relay/ack', type='jsonrpc', auth='public', csrf=False)
    def ack(self, token=None, job_id=None, status='sent', error_message='', duration_ms=0):
        if not self._check_token(token):
            return {'success': False, 'error': 'invalid_token'}

        job = request.env['pos.print.job'].sudo().browse(int(job_id))
        if not job.exists():
            return {'success': False, 'error': 'job_not_found'}

        from odoo import fields as _fields
        vals = {
            'status': status if status in ('sent', 'error') else 'error',
            'sent_date': _fields.Datetime.now(),
            'duration_ms': int(duration_ms or 0),
        }
        if status == 'error':
            vals['error_message'] = error_message or 'Erreur inconnue (agent)'

        job.write(vals)
        return {'success': True}
