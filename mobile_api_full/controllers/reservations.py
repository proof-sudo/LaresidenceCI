from odoo import http
from odoo.http import request
from .auth import MobileAuth

class MobileReservations(http.Controller):

    @http.route("/api/mobile/reservations", type="json", auth="public", methods=["POST"], csrf=False)
    def create_reservation(self, **payload):
        if not MobileAuth.check():
            return {"success": False}

        order = request.env["sale.order"].sudo().create({
            "partner_id": payload["memberId"],
            "order_line": [(0, 0, {
                "product_id": payload["spaceId"],
                "product_uom_qty": 1,
                "start_date": payload["startTime"],
                "end_date": payload["endTime"]
            })]
        })
        return {
            "success": True,
            "order": order.name,
            "total": order.amount_total
        }
