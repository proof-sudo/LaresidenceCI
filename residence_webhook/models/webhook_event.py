
import logging
import requests
import uuid
from datetime import datetime, timedelta

from odoo import models, fields

_logger = logging.getLogger(__name__)

API_URL = "https://api.laresidence-abidjan.com/v1/external/webhooks/odoo"

class WebhookEvent(models.Model):
    _name = "residence.webhook.event"
    _description = "Webhook Event Queue"

    event_id = fields.Char(default=lambda self: f"evt_{uuid.uuid4()}", required=True)
    event_type = fields.Char(required=True)
    entity_type = fields.Char(required=True)
    entity_id = fields.Char(required=True)
    payload = fields.Json()

    state = fields.Selection([
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ], default="pending")

    retry_count = fields.Integer(default=0)
    next_retry = fields.Datetime()
    last_error = fields.Text()

    def send_event(self):
        api_key = self.env["ir.config_parameter"].sudo().get_param("residence_webhook.api_key")

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        }

        for rec in self:
            try:
                _logger.info("Sending webhook %s", rec.event_id)

                response = requests.post(API_URL, json=rec.payload, headers=headers, timeout=5)

                if response.status_code == 202:
                    rec.state = "sent"
                    _logger.info("Webhook sent successfully %s", rec.event_id)
                else:
                    rec._handle_failure(response.text)

            except Exception as e:
                rec._handle_failure(str(e))

    def _handle_failure(self, error):
        self.retry_count += 1
        self.last_error = error
        self.state = "failed"

        delay = 2 ** self.retry_count
        self.next_retry = datetime.utcnow() + timedelta(seconds=delay)

        _logger.error("Webhook failed: %s", error)
