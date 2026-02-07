# -*- coding: utf-8 -*-
from odoo import models

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'webhook.mixin']

class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'webhook.mixin']

class ProductProduct(models.Model):
    _name = 'product.product'
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