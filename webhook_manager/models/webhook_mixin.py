from odoo import models, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class WebhookMixin(models.AbstractModel):
    _name = "webhook.mixin"
    _description = "Mixin pour déclencher des webhooks sur CRUD avec suivi des champs modifiés"

    def _send_webhook(self, event_type, payload, changed_fields=None):
        model_name = self._name
        configs = self.env['webhook.config'].search([('model_id.model', '=', model_name)])
        if not configs:
            _logger.info(f"Aucun webhook configuré pour le modèle {model_name}")
            return

        for config in configs:
            url = config.url
            headers = {'Content-Type': 'application/json'}
            if config.api_key:
                headers['Authorization'] = f'Bearer {config.api_key}'

            data = {
                "event": event_type,
                "model": model_name,
                "data": payload
            }
            if changed_fields:
                data["changed_fields"] = changed_fields

            _logger.info(f"Envoi webhook {event_type} pour {model_name} à {url} avec data: {changed_fields}")

            try:
                response = requests.post(url, headers=headers, data=json.dumps(data), timeout=5)
                _logger.info(f"Webhook envoyé avec succès, statut HTTP: {response.status_code}")
            except Exception as e:
                _logger.error(f"Erreur envoi webhook {model_name}: {e}")

    @api.model
    def create(self, vals):
        record = super().create(vals)
        _logger.debug(f"Create sur {self._name} avec vals: {vals}")
        record._send_webhook("create", record.read()[0])
        return record

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            changed_data = {field: vals[field] for field in vals if field in rec._fields}
            _logger.debug(f"Write sur {rec._name} (ID: {rec.id}) avec changed_fields: {changed_data}")
            rec._send_webhook("write", rec.read()[0], changed_fields=changed_data)
        return res

    def unlink(self):
        for rec in self:
            _logger.debug(f"Unlink sur {rec._name} (ID: {rec.id})")
            rec._send_webhook("unlink", rec.read()[0])
        return super().unlink()


from odoo import models

class ProductProductWebhook(models.Model):
    _inherit = ["product.product", "webhook.mixin"]

class ProductCategoryWebhook(models.Model):
    _inherit = ["product.category", "webhook.mixin"]

class PosCategoryWebhook(models.Model):
    _inherit = ["pos.category", "webhook.mixin"]

class SaleOrderWebhook(models.Model):
    _inherit = ["sale.order", "webhook.mixin"]

class SaleSubscriptionWebhook(models.Model):
    _inherit = ["sale.subscription", "webhook.mixin"]

class ResidenceReservationWebhook(models.Model):
    _inherit = ["residence.reservation", "webhook.mixin"]
