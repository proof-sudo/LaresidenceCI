# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class WebhookConfig(models.Model):
    _name = "webhook.config"
    _description = "Configuration des Webhooks"
    _order = "sequence, name"

    active = fields.Boolean(
        string="Actif",
        default=True,
        help="Désactiver temporairement ce webhook sans le supprimer"
    )
    sequence = fields.Integer(
        string="Séquence",
        default=10,
        help="Ordre d'exécution des webhooks"
    )
    name = fields.Char(
        string="Nom du webhook",
        required=True,
        help="Nom descriptif du webhook"
    )
    model_id = fields.Many2one(
        'ir.model',
        string="Modèle à écouter",
        required=True,
        ondelete='cascade',
        help="Modèle Odoo qui déclenchera le webhook"
    )
    url = fields.Char(
        string="URL API",
        required=True,
        help="URL de destination du webhook (ex: https://api.exemple.com/webhook)"
    )
    api_key = fields.Char(
        string="Clé API",
        help="Clé d'authentification Bearer (optionnel)"
    )
    timeout = fields.Integer(
        string="Timeout (secondes)",
        default=5,
        help="Délai d'attente maximal pour la réponse"
    )
    
    # Events à écouter
    listen_create = fields.Boolean(
        string="Écouter CREATE",
        default=True,
        help="Envoyer un webhook lors de la création"
    )
    listen_write = fields.Boolean(
        string="Écouter WRITE",
        default=True,
        help="Envoyer un webhook lors de la modification"
    )
    listen_unlink = fields.Boolean(
        string="Écouter UNLINK",
        default=True,
        help="Envoyer un webhook lors de la suppression"
    )

    @property
    def model_name(self):
        """Retourne le nom technique du modèle"""
        return self.model_id.model if self.model_id else False

    @api.constrains('url')
    def _check_url(self):
        """Valide le format de l'URL"""
        for record in self:
            if record.url and not record.url.startswith(('http://', 'https://')):
                raise models.ValidationError("L'URL doit commencer par http:// ou https://")

    @api.constrains('timeout')
    def _check_timeout(self):
        """Valide le timeout"""
        for record in self:
            if record.timeout < 1 or record.timeout > 60:
                raise models.ValidationError("Le timeout doit être entre 1 et 60 secondes")