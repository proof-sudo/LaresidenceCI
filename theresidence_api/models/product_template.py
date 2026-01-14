# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ==========================================
    # Champs The Residence
    # ==========================================
    residence_external_id = fields.Char(
        string='ID Externe (UUID)',
        index=True,
        copy=False,
        help='UUID pour synchronisation avec l\'app mobile'
    )

    is_residence_space = fields.Boolean(
        string='Est une Salle',
        default=False,
        help='Ce produit est une salle/espace à louer'
    )

    is_residence_menu_item = fields.Boolean(
        string='Est un Article Menu',
        default=False,
        help='Ce produit est un article du menu restaurant'
    )

    # ==========================================
    # Champs Spécifiques Salles
    # ==========================================
    residence_location_id = fields.Many2one(
        'residence.location',
        string='Emplacement'
    )

    residence_capacity = fields.Integer(
        string='Capacité',
        default=10,
        help='Nombre maximum de personnes'
    )

    residence_space_state = fields.Selection([
        ('available', 'Disponible'),
        ('reserved', 'Réservé'),
        ('maintenance', 'Maintenance')
    ], string='État Salle', default='available')

    residence_equipment_ids = fields.Many2many(
        'residence.space.equipment',
        string='Équipements Disponibles'
    )

    # ==========================================
    # Champs Spécifiques Menu
    # ==========================================
    residence_menu_kind_id = fields.Many2one(
        'residence.menu.kind',
        string='Type de Menu'
    )

    residence_menu_category_id = fields.Many2one(
        'residence.menu.category',
        string='Catégorie Menu'
    )

    residence_is_available = fields.Boolean(
        string='Disponible à la commande',
        default=True
    )

    residence_preparation_time = fields.Integer(
        string='Temps de Préparation (min)',
        default=15
    )

    residence_allergens = fields.Char(string='Allergènes')
    residence_is_vegetarian = fields.Boolean(string='Végétarien')
    residence_is_vegan = fields.Boolean(string='Végan')
    residence_is_gluten_free = fields.Boolean(string='Sans Gluten')

    # ==========================================
    # Image URL externe
    # ==========================================
    residence_image_url = fields.Char(
        string='URL Image',
        help='URL externe de l\'image (CDN)'
    )

    # ==========================================
    # Méthodes
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (vals.get('is_residence_space') or vals.get('is_residence_menu_item')) \
                    and not vals.get('residence_external_id'):
                vals['residence_external_id'] = str(uuid.uuid4())
        return super().create(vals_list)

    def to_space_api_dict(self):
        """Convertir en format API pour une salle"""
        self.ensure_one()
        return {
            'id': self.residence_external_id,
            'name': self.name,
            'description': self.description_sale or '',
            'capacity': self.residence_capacity,
            'locationId': self.residence_location_id.external_id if self.residence_location_id else None,
            'locationName': self.residence_location_id.name if self.residence_location_id else '',
            'imageUrl': self.residence_image_url or '',
            'hourlyRate': self.list_price,
            'state': self.residence_space_state,
            'equipment': [eq.to_api_dict() for eq in self.residence_equipment_ids]
        }

    def to_menu_item_api_dict(self):
        """Convertir en format API pour un article menu"""
        self.ensure_one()
        return {
            'id': self.residence_external_id,
            'categoryId': self.residence_menu_category_id.external_id if self.residence_menu_category_id else None,
            'categoryName': self.residence_menu_category_id.name if self.residence_menu_category_id else '',
            'kindId': self.residence_menu_kind_id.external_id if self.residence_menu_kind_id else None,
            'kindName': self.residence_menu_kind_id.name if self.residence_menu_kind_id else '',
            'name': self.name,
            'description': self.description_sale or '',
            'price': self.list_price,
            'imageUrl': self.residence_image_url or '',
            'isAvailable': self.residence_is_available,
            'preparationTime': self.residence_preparation_time,
            'allergens': self.residence_allergens or '',
            'isVegetarian': self.residence_is_vegetarian,
            'isVegan': self.residence_is_vegan,
            'isGlutenFree': self.residence_is_gluten_free
        }

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver par ID externe"""
        return self.search([('residence_external_id', '=', external_id)], limit=1)


class ResidenceLocation(models.Model):
    _name = 'residence.location'
    _description = 'Emplacement / Bâtiment'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    external_id = fields.Char(
        string='ID Externe (UUID)',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False,
        index=True
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    description = fields.Text(string='Description', translate=True)
    address = fields.Text(string='Adresse')
    image_url = fields.Char(string='URL Image')

    space_ids = fields.One2many(
        'product.template',
        'residence_location_id',
        string='Salles',
        domain=[('is_residence_space', '=', True)]
    )

    space_count = fields.Integer(
        string='Nb Salles',
        compute='_compute_space_count'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        required=True
    )

    _sql_constraints = [
        ('external_id_unique', 'UNIQUE(external_id)', 'L\'ID externe doit être unique!')
    ]

    @api.depends('space_ids')
    def _compute_space_count(self):
        for rec in self:
            rec.space_count = len(rec.space_ids)

    def to_api_dict(self):
        """Convertir en format API"""
        self.ensure_one()
        return {
            'id': self.external_id,
            'name': self.name,
            'description': self.description or '',
            'address': self.address or '',
            'imageUrl': self.image_url or '',
            'spaceCount': self.space_count
        }

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver par ID externe"""
        return self.search([('external_id', '=', external_id)], limit=1)


class ResidenceSpaceEquipment(models.Model):
    _name = 'residence.space.equipment'
    _description = 'Équipement de Salle'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    external_id = fields.Char(
        string='ID Externe (UUID)',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False,
        index=True
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    description = fields.Text(string='Description')
    price = fields.Monetary(
        string='Prix Unitaire',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    product_id = fields.Many2one(
        'product.product',
        string='Produit Associé'
    )

    _sql_constraints = [
        ('external_id_unique', 'UNIQUE(external_id)', 'L\'ID externe doit être unique!')
    ]

    def to_api_dict(self):
        """Convertir en format API"""
        self.ensure_one()
        return {
            'id': self.external_id,
            'name': self.name,
            'description': self.description or '',
            'unitPrice': self.price
        }

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver par ID externe"""
        return self.search([('external_id', '=', external_id)], limit=1)


class ResidenceMenuKind(models.Model):
    _name = 'residence.menu.kind'
    _description = 'Type de Menu (Restaurant, Bar, etc.)'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    external_id = fields.Char(
        string='ID Externe (UUID)',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False,
        index=True
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    description = fields.Text(string='Description', translate=True)
    image_url = fields.Char(string='URL Image')

    category_ids = fields.One2many(
        'residence.menu.category',
        'kind_id',
        string='Catégories'
    )

    category_count = fields.Integer(
        string='Nb Catégories',
        compute='_compute_category_count'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        required=True
    )

    _sql_constraints = [
        ('external_id_unique', 'UNIQUE(external_id)', 'L\'ID externe doit être unique!')
    ]

    @api.depends('category_ids')
    def _compute_category_count(self):
        for rec in self:
            rec.category_count = len(rec.category_ids)

    def to_api_dict(self):
        """Convertir en format API"""
        self.ensure_one()
        return {
            'id': self.external_id,
            'name': self.name,
            'description': self.description or ''
        }

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver par ID externe"""
        return self.search([('external_id', '=', external_id)], limit=1)


class ResidenceMenuCategory(models.Model):
    _name = 'residence.menu.category'
    _description = 'Catégorie de Menu'
    _order = 'kind_id, sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    external_id = fields.Char(
        string='ID Externe (UUID)',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False,
        index=True
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    description = fields.Text(string='Description', translate=True)
    image_url = fields.Char(string='URL Image')

    kind_id = fields.Many2one(
        'residence.menu.kind',
        string='Type de Menu',
        required=True,
        ondelete='cascade'
    )

    item_ids = fields.One2many(
        'product.template',
        'residence_menu_category_id',
        string='Articles',
        domain=[('is_residence_menu_item', '=', True)]
    )

    item_count = fields.Integer(
        string='Nb Articles',
        compute='_compute_item_count'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        required=True
    )

    _sql_constraints = [
        ('external_id_unique', 'UNIQUE(external_id)', 'L\'ID externe doit être unique!')
    ]

    @api.depends('item_ids')
    def _compute_item_count(self):
        for rec in self:
            rec.item_count = len(rec.item_ids)

    def to_api_dict(self):
        """Convertir en format API"""
        self.ensure_one()
        return {
            'id': self.external_id,
            'kindId': self.kind_id.external_id,
            'name': self.name,
            'description': self.description or '',
            'imageUrl': self.image_url or ''
        }

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver par ID externe"""
        return self.search([('external_id', '=', external_id)], limit=1)
