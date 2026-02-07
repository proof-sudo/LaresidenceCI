from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def register_webhook_models(cr, registry):
    """Injecte dynamiquement le mixin sur tous les modèles sélectionnés dans webhook.config"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    webhook_configs = env['webhook.config'].search([])
    for config in webhook_configs:
        model_name = config.model_id.model
        model_cls = env.registry[model_name].model_class

        if "webhook.mixin" not in [cls._name for cls in model_cls.__mro__]:
            _logger.info(f"Injection dynamique de WebhookMixin sur {model_name}")
            model_cls._inherit += ('webhook.mixin',)
