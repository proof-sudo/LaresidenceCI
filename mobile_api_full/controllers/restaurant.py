from odoo import http
from odoo.http import request
from .auth import MobileAuth

class MobileRestaurant(http.Controller):

    @http.route("/api/mobile/menu/items", type="json", auth="public", methods=["GET"], csrf=False)
    def menu_items(self):
        if not MobileAuth.check():
            return {"success": False}

        products = request.env["product.product"].sudo().search([("available_in_pos", "=", True)])
        return {"success": True, "data": [
            {
                "id": p.id,
                "name": p.name,
                "price": p.lst_price
            } for p in products
        ]}
