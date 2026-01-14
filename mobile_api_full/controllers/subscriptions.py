from odoo import http
from odoo.http import request
from .auth import MobileAuth

class MobileSubscriptions(http.Controller):

    @http.route("/api/mobile/subscriptions", type="json", auth="public", methods=["GET"], csrf=False)
    def list_subscriptions(self):
        if not MobileAuth.check():
            return {"success": False}

        subs = request.env["sale.subscription.template"].sudo().search([])
        return {"success": True, "data": [
            {
                "id": s.id,
                "name": s.name,
                "price": s.recurring_total
            } for s in subs
        ]}

    @http.route("/api/mobile/subscriptions/subscribe", type="json", auth="public", methods=["POST"], csrf=False)
    def subscribe(self, **payload):
        if not MobileAuth.check():
            return {"success": False}

        sub = request.env["sale.subscription"].sudo().create({
            "partner_id": payload["memberId"],
            "template_id": payload["subscriptionId"],
        })
        return {"success": True, "subscriptionId": sub.id}
