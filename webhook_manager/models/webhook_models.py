from odoo import models,api
import logging

_logger = logging.getLogger(__name__)
# Modèles simples – pas de conflit Many2many
class ProductProductWebhook(models.Model):
    _inherit = ["product.product", "webhook.mixin"]

class SaleOrderWebhookProxy(models.Model):
    _name = "sale.order.webhook.proxy"
    _inherit = "sale.order"
    _description = "Proxy pour webhooks Sale Order"

    @api.model
    def create(self, vals):
        record = super().create(vals)
        _logger.info(f"[Webhook Proxy] Sale Order create: {vals}")
        self.env['webhook.mixin']._send_webhook(record, "create", record.read()[0])
        return record

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            _logger.info(f"[Webhook Proxy] Sale Order write: {vals}")
            self.env['webhook.mixin']._send_webhook(rec, "write", rec.read()[0], changed_fields=vals)
        return res

    def unlink(self):
        for rec in self:
            _logger.info(f"[Webhook Proxy] Sale Order unlink")
            self.env['webhook.mixin']._send_webhook(rec, "unlink", rec.read()[0])
        return super().unlink()

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