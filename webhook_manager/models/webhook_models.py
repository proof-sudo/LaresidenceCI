# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class ProductProductWebhook(models.Model):
    """Ajoute le webhook mixin au modèle product.product"""
    _inherit = ["product.product", "webhook.mixin"]


class SaleOrderWebhook(models.Model):
    """Ajoute le webhook mixin au modèle sale.order"""
    _inherit = ["sale.order", "webhook.mixin"]


class ProductCategoryWebhook(models.Model):
    """Ajoute le webhook mixin au modèle product.category"""
    _inherit = ["product.category", "webhook.mixin"]


class PosCategoryWebhook(models.Model):
    """Ajoute le webhook mixin au modèle pos.category"""
    _inherit = ["pos.category", "webhook.mixin"]


class ResPartnerWebhook(models.Model):
    """Ajoute le webhook mixin au modèle res.partner"""
    _inherit = ["res.partner", "webhook.mixin"]


class StockPickingWebhook(models.Model):
    """Ajoute le webhook mixin au modèle stock.picking"""
    _inherit = ["stock.picking", "webhook.mixin"]


class AccountMoveWebhook(models.Model):
    """Ajoute le webhook mixin au modèle account.move (factures)"""
    _inherit = ["account.move", "webhook.mixin"]


class SaleOrderLineWebhook(models.Model):
    """Ajoute le webhook mixin au modèle sale.order.line"""
    _inherit = ["sale.order.line", "webhook.mixin"]


# Si vous avez besoin d'ajouter d'autres modèles, suivez le même pattern :
# class VotreModeleWebhook(models.Model):
#     _inherit = ["votre.modele", "webhook.mixin"]