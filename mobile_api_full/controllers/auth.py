from odoo import http
from odoo.http import request

class MobileAuth:
    @staticmethod
    def check():
        api_key = request.httprequest.headers.get("X-API-Key")
        if not api_key:
            return False
        return bool(request.env["mobile.api.key"].sudo().search([
            ("key", "=", api_key),
            ("active", "=", True)
        ], limit=1))
