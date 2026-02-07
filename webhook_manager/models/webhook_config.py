from odoo import models, fields

class WebhookConfig(models.Model):
    _name = "webhook.config"
    _description = "Configuration des Webhooks"

    name = fields.Char("Nom du webhook", required=True)
    model_id = fields.Many2one(
        'ir.model',
        string="Modèle à écouter",
        required=True,
        ondelete='cascade'
    )
    url = fields.Char("URL API", required=True)
    api_key = fields.Char("Clé API (optionnel)")

    @property
    def model_name(self):
        return self.model_id.model
