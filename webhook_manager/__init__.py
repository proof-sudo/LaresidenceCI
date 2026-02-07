from . import models

def post_init_hook(cr, registry):
    from .models import webhook_registry
    webhook_registry.register_webhook_models(cr, registry)
