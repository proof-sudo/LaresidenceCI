from odoo import http
from odoo.http import request
from .auth import MobileAuth

class MobileSpaces(http.Controller):

    @http.route("/api/mobile/spaces", type="json", auth="public", methods=["GET"], csrf=False)
    def list_spaces(self):
        if not MobileAuth.check():
            return {"success": False, "message": "Unauthorized"}

        spaces = request.env["product.product"].sudo().search([("rent_ok", "=", True)])
        return {"success": True, "data": [
            {
                "id": s.id,
                "name": s.name,
                "pricePerHour": s.lst_price,
                "isAvailable": True
            } for s in spaces
        ]}
