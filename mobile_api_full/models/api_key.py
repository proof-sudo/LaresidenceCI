from odoo import models, fields
import secrets

class MobileApiKey(models.Model):
    _name = "mobile.api.key"
    _description = "Mobile API Key"

    name = fields.Char(required=True)
    key = fields.Char(default=lambda self: secrets.token_hex(32), readonly=True)
    active = fields.Boolean(default=True)
