
import logging
from odoo import models
from datetime import datetime

_logger = logging.getLogger(__name__)

class WebhookMixin(models.AbstractModel):
    _name = "webhook.mixin"
    _description = "Webhook Mixin"

    def _build_payload(self, event_type, entity_type):
        return {
            "event_type": event_type,
            "event_id": f"evt_{self._name}_{self.id}_{datetime.utcnow().timestamp()}",
            "timestamp": datetime.utcnow().isoformat(),
            "entity_type": entity_type,
            "entity_id": str(self.id),
            "data": self._prepare_data()
        }

    def _prepare_data(self):
        return {}

    def _queue_webhook(self, event_type, entity_type):
        payload = self._build_payload(event_type, entity_type)

        self.env["residence.webhook.event"].create({
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": self.id,
            "payload": payload
        })
