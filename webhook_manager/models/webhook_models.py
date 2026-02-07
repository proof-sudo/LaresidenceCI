# -*- coding: utf-8 -*-
from odoo import models

class SaleOrder(models.Model):
    _inherit = "sale.order"
    _inherit = ["sale.order", "webhook.mixin"]

class ResPartner(models.Model):
    _inherit = "res.partner"
    _inherit = ["res.partner", "webhook.mixin"]

class SaleSubscription(models.Model):
    _inherit = "sale.subscription"
    _inherit = ["sale.subscription", "webhook.mixin"]

# Pour les modèles de votre version initiale :
class ProductProduct(models.Model):
    _inherit = "product.product"
    _inherit = ["product.product", "webhook.mixin"]

class StockPicking(models.Model):
    _inherit = "stock.picking"
    _inherit = ["stock.picking", "webhook.mixin"]

class AccountMove(models.Model):
    _inherit = "account.move"
    _inherit = ["account.move", "webhook.mixin"]