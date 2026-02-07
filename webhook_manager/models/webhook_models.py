# -*- coding: utf-8 -*-
from odoo import models,fields

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'webhook.mixin']

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'webhook.mixin']

class ProductProduct(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'webhook.mixin']

class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'webhook.mixin']

class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'webhook.mixin']

class PosCategory(models.Model):
    _name = 'pos.category'
    _inherit = ['pos.category', 'webhook.mixin']

# class SaleSubscription(models.Model):
#     _name = 'sale.subscription'
#     _inherit = ['sale.subscription', 'webhook.mixin']

class WebhookLog(models.Model):
    _name = "webhook.log"
    _description = "Historique des Webhooks"
    _order = "create_date desc"

    name = fields.Char("ID Événement")
    model_name = fields.Char("Modèle Odoo")
    res_id = fields.Integer("ID Enregistrement")
    status_code = fields.Char("Code HTTP")
    success = fields.Boolean("Succès")
    request_payload = fields.Text("Payload Envoyé")
    response_body = fields.Text("Réponse API")