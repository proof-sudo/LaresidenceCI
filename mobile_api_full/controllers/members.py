from odoo import http
from odoo.http import request
from .auth import MobileAuth

class MobileMembers(http.Controller):

    @http.route("/api/mobile/members", type="json", auth="public", methods=["POST"], csrf=False)
    def create_member(self, **payload):
        if not MobileAuth.check():
            return {"success": False, "message": "Unauthorized"}

        partner = request.env["res.partner"].sudo().create({
            "name": f"{payload.get('firstName')} {payload.get('lastName')}",
            "email": payload.get("email"),
            "phone": payload.get("phone"),
        })
        return {"success": True, "id": partner.id}
