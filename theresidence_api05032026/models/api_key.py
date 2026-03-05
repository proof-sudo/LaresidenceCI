# -*- coding: utf-8 -*-

import secrets
from odoo import models, fields, api


class TheResidenceApiKey(models.Model):
    """Clés API pour l'authentification externe."""
    _name = 'theresidence.api.key'
    _description = 'Clé API The Residence'
    _order = 'name'

    name = fields.Char(string='Nom', required=True)
    key = fields.Char(string='Clé API', readonly=True, copy=False)
    description = fields.Text(string='Description')
    is_active = fields.Boolean(string='Active', default=True)
    
    # Permissions
    can_read_members = fields.Boolean(string='Lecture membres', default=True)
    can_write_members = fields.Boolean(string='Écriture membres', default=False)
    can_read_spaces = fields.Boolean(string='Lecture espaces', default=True)
    can_read_menu = fields.Boolean(string='Lecture menu', default=True)
    can_read_reservations = fields.Boolean(string='Lecture réservations', default=True)
    can_write_reservations = fields.Boolean(string='Écriture réservations', default=False)
    can_read_orders = fields.Boolean(string='Lecture commandes', default=True)
    can_write_orders = fields.Boolean(string='Écriture commandes', default=False)
    can_read_subscriptions = fields.Boolean(string='Lecture abonnements', default=True)
    can_write_subscriptions = fields.Boolean(string='Écriture abonnements', default=False)
    can_manage_webhooks = fields.Boolean(string='Gestion webhooks', default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('key'):
                vals['key'] = self._generate_api_key()
        return super().create(vals_list)

    @staticmethod
    def _generate_api_key():
        return f"tr_{secrets.token_urlsafe(32)}"

    def regenerate_key(self):
        for record in self:
            record.key = self._generate_api_key()

    def has_permission(self, permission):
        self.ensure_one()
        perm_map = {
            'read_members': self.can_read_members,
            'write_members': self.can_write_members,
            'read_spaces': self.can_read_spaces,
            'read_menu': self.can_read_menu,
            'read_reservations': self.can_read_reservations,
            'write_reservations': self.can_write_reservations,
            'read_orders': self.can_read_orders,
            'write_orders': self.can_write_orders,
            'read_subscriptions': self.can_read_subscriptions,
            'write_subscriptions': self.can_write_subscriptions,
            'manage_webhooks': self.can_manage_webhooks,
        }
        return perm_map.get(permission, False)

    @api.model
    def validate_key(self, key):
        if not key:
            return False
        api_key = self.search([('key', '=', key), ('is_active', '=', True)], limit=1)
        return api_key if api_key else False
