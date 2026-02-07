from odoo import models
import logging

_logger = logging.getLogger(__name__)
# Modèles simples – pas de conflit Many2many
class ProductProductWebhook(models.Model):
    _inherit = ["product.product", "webhook.mixin"]

class SaleOrderWebhook(models.Model):
    _inherit = ["sale.order", "webhook.mixin"]
class ProductCategoryWebhookProxy(models.Model):
    _name = "product.category.webhook.proxy"
    _inherit = "product.category"
    _description = "Proxy pour envoyer webhook Product Category"

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            _logger.info(f"[Webhook Proxy] Product Category write: {vals}")
            # Appel à _send_webhook via mixin manuel
            self.env['webhook.mixin']._send_webhook(rec, "write", rec.read()[0], changed_fields=vals)
        return res

# POS Category
class PosCategoryWebhookProxy(models.Model):
    _name = "pos.category.webhook.proxy"
    _inherit = "pos.category"
    _description = "Proxy pour envoyer webhook POS Category"

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            _logger.info(f"[Webhook Proxy] POS Category write: {vals}")
            self.env['webhook.mixin']._send_webhook(rec, "write", rec.read()[0], changed_fields=vals)
        return res