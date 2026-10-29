# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api


class TheResidenceMembershipType(models.Model):
    """Types d'adhésion pour les membres."""
    _name = 'theresidence.membership.type'
    _description = 'Type d\'adhésion The Residence'
    _order = 'sort_order, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    description = fields.Text(string='Description', translate=True)
    sort_order = fields.Integer(string='Ordre', default=10)
    active = fields.Boolean(default=True)
    x_uuid = fields.Char(string='UUID', readonly=True, copy=False, default=lambda self: str(uuid.uuid4()))

    _sql_constraints = [('code_unique', 'unique(code)', 'Le code doit être unique.')]

    def to_api_dict(self):
        self.ensure_one()
        return {
            'id': self.x_uuid,
            'code': self.code,
            'name': self.name,
            'description': self.description or '',
            'sortOrder': self.sort_order
        }


class TheResidenceSpaceType(models.Model):
    """Types d'espaces."""
    _name = 'theresidence.space.type'
    _description = 'Type d\'espace'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(string='Séquence', default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_unique', 'unique(code)', 'Le code doit être unique.')]


class TheResidenceReservationOptionDef(models.Model):
    """Définition des options disponibles pour les réservations."""
    _name = 'theresidence.reservation.option.def'
    _description = 'Définition d\'option de réservation'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', required=True, index=True)
    description = fields.Text(string='Description', translate=True)
    scope = fields.Selection([
        ('SPACE', 'Espace'),
        ('EVENT', 'Événement'),
        ('GLOBAL', 'Global'),
    ], string='Portée', default='SPACE', required=True)
    price = fields.Float(string='Prix unitaire', digits='Product Price')
    currency_id = fields.Many2one('res.currency', string='Devise', default=lambda self: self.env.company.currency_id)
    sequence = fields.Integer(string='Séquence', default=10)
    active = fields.Boolean(default=True)
    x_uuid = fields.Char(string='UUID', readonly=True, copy=False, default=lambda self: str(uuid.uuid4()))

    _sql_constraints = [('code_unique', 'unique(code)', 'Le code doit être unique.')]

    def to_api_dict(self):
        self.ensure_one()
        return {
            'id': self.x_uuid,
            'code': self.code,
            'scope': self.scope,
            'label': self.name,
            'description': self.description or '',
            'price': self.price,
            'currency': self.currency_id.name if self.currency_id else 'XOF'
        }


class TheResidenceMenuKind(models.Model):
    """Types de menu (petit-déjeuner, déjeuner, etc.)."""
    _name = 'theresidence.menu.kind'
    _description = 'Type de menu'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', index=True)
    description = fields.Text(string='Description', translate=True)
    sequence = fields.Integer(string='Séquence', default=10)
    active = fields.Boolean(default=True)
    x_uuid = fields.Char(string='UUID', readonly=True, copy=False, default=lambda self: str(uuid.uuid4()))

    def to_api_dict(self):
        self.ensure_one()
        return {
            'id': self.x_uuid,
            'code': self.code or '',
            'name': self.name,
            'sortOrder': self.sequence
        }
