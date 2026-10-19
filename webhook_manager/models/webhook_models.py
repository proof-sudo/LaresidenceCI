# -*- coding: utf-8 -*-
from odoo import models, fields

class WebhookLog(models.Model):
    _name = "webhook.log"
    _description = "Historique des Webhooks The Residence"
    _order = "create_date desc"

    name = fields.Char("ID Événement", readonly=True)
    model_name = fields.Char("Modèle Odoo", readonly=True)
    res_id = fields.Integer("ID Enregistrement", readonly=True)
    status_code = fields.Char("Code HTTP", readonly=True)
    success = fields.Boolean("Succès", readonly=True)
    request_payload = fields.Text("Payload Envoyé", readonly=True)
    response_body = fields.Text("Réponse API", readonly=True)

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'webhook.mixin']

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'webhook.mixin']

class PosCategory(models.Model):
    _name = 'pos.category'
    _inherit = ['pos.category', 'webhook.mixin']

class PosOrder(models.Model):
    _name = 'pos.order'
    _inherit = ['pos.order', 'webhook.mixin']

class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'webhook.mixin']