# -*- coding: utf-8 -*-
from odoo import models, logging

_logger = logging.getLogger(__name__)

class SaleOrderWebhook(models.Model):
    """
    Entité: order
    Événements: order.confirmed, order.completed, order.cancelled
    """
    _inherit = ["sale.order", "webhook.mixin"]


class ResPartnerWebhook(models.Model):
    """
    Entité: member
    Événements: member.updated
    """
    _inherit = ["res.partner", "webhook.mixin"]


class SaleSubscriptionWebhook(models.Model):
    """
    Entité: subscription
    Événements: subscription.activated, subscription.paused, subscription.cancelled, etc.
    Note: Nécessite le module Odoo Subscriptions (sale_subscription)
    """
    _inherit = ["sale.subscription", "webhook.mixin"]


# class HotelReservationWebhook(models.Model):
#     """
#     Entité: reservation
#     Événements: reservation.approved, reservation.rejected, reservation.cancelled, reservation.checked_in
#     """
#     # Note: Remplacez 'hotel.reservation' par le nom technique exact de votre module de réservation
#     _inherit = ["hotel.reservation", "webhook.mixin"]


class ProductProductWebhook(models.Model):
    """Héritage conservé de votre version initiale"""
    _inherit = ["product.product", "webhook.mixin"]


class ProductCategoryWebhook(models.Model):
    """Héritage conservé de votre version initiale"""
    _inherit = ["product.category", "webhook.mixin"]


class PosCategoryWebhook(models.Model):
    """Héritage conservé de votre version initiale"""
    _inherit = ["pos.category", "webhook.mixin"]


class StockPickingWebhook(models.Model):
    """Héritage conservé de votre version initiale (Livraisons)"""
    _inherit = ["stock.picking", "webhook.mixin"]


class AccountMoveWebhook(models.Model):
    """Héritage conservé de votre version initiale (Factures)"""
    _inherit = ["account.move", "webhook.mixin"]


class SaleOrderLineWebhook(models.Model):
    """Héritage conservé de votre version initiale"""
    _inherit = ["sale.order.line", "webhook.mixin"]