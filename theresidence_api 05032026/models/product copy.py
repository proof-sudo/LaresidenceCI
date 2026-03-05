# -*- coding: utf-8 -*-

import uuid
from datetime import datetime
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Champs pour les espaces
    x_tr_is_space = fields.Boolean(string='Est un espace TR')
    x_tr_space_uuid = fields.Char(string='UUID Espace', copy=False, readonly=True, index=True)
    x_tr_space_capacity = fields.Integer(string='Capacité')
    x_tr_space_type_id = fields.Many2one('theresidence.space.type', string='Type d\'espace')
    x_tr_space_description = fields.Text(string='Description espace')
    
    # Champs pour les plans d'abonnement
    x_tr_is_subscription_plan = fields.Boolean(string='Est un plan d\'abonnement')
    x_tr_membership_type_id = fields.Many2one('theresidence.membership.type', string='Type d\'adhésion lié')
    x_tr_duration_months = fields.Integer(string='Durée (mois)', default=1)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('x_tr_is_space') and not vals.get('x_tr_space_uuid'):
                vals['x_tr_space_uuid'] = str(uuid.uuid4())
                vals['rent_ok'] = True
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('x_tr_is_space'):
            for product in self:
                if not product.x_tr_space_uuid:
                    vals.setdefault('x_tr_space_uuid', str(uuid.uuid4()))
            vals.setdefault('rent_ok', True)
        return super().write(vals)

    def check_availability(self, start_time, end_time):
        self.ensure_one()
        if not self.x_tr_is_space:
            return {'isAvailable': False, 'reason': 'Not a space'}
        
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # Rechercher les réservations conflictuelles
        conflicting = self.env['sale.order'].sudo().search_count([
            ('x_tr_is_reservation', '=', True),
            ('x_tr_reservation_status', 'in', ['PENDING', 'APPROVED', 'CHECKED_IN']),
            ('x_tr_space_id', '=', self.id),
            ('x_tr_start_time', '<', end_time),
            ('x_tr_end_time', '>', start_time),
        ])
        
        return {
            'spaceId': self.x_tr_space_uuid,
            'spaceName': self.name,
            'startTime': start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time),
            'endTime': end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time),
            'isAvailable': conflicting == 0,
            'conflictingReservations': conflicting
        }


    
    def to_space_api_dict(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        image_url = (
            f"{base_url}/api/v1/spaces/{self.x_tr_space_uuid or self.id}/image"
            if self.image_1920 else ''
        )

        return {
            'id': self.x_tr_space_uuid or str(self.id),
            'name': self.name or '',
            'description': self.x_tr_space_description or self.description_sale or '',
            'type': self.x_tr_space_type_id.code if self.x_tr_space_type_id else 'GENERAL',
            'typeName': self.x_tr_space_type_id.name if self.x_tr_space_type_id else '',
            'capacity': self.x_tr_space_capacity or 0,
            'pricePerHour': self.list_price or 0.0,
            'currency': self.currency_id.name if self.currency_id else 'XOF',
            'imageUrl': image_url,
            'isAvailable': self.active
        }


    def to_subscription_plan_api_dict(self):
        self.ensure_one()
        return {
            'id': self.x_tr_space_uuid or str(self.id),
            'name': self.name or '',
            'description': self.description_sale or '',
            'price': self.list_price or 0.0,
            'durationMonths': self.x_tr_duration_months or 1,
            'membershipTypeCode': self.x_tr_membership_type_id.code if self.x_tr_membership_type_id else '',
            'membershipTypeName': self.x_tr_membership_type_id.name if self.x_tr_membership_type_id else '',
            'currency': self.currency_id.name if self.currency_id else 'XOF'
        }


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def to_menu_item_api_dict(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        image_url = f"{base_url}/web/image/product.product/{self.id}/image_128" if self.image_128 else ''
        
        category = self.pos_categ_ids[0] if self.pos_categ_ids else None
        kind = category.x_tr_menu_kind_id if category else None
        
        return {
            'id': str(self.id),
            'categoryId': category.x_tr_uuid if category else '',
            'categoryName': category.name if category else '',
            'kindId': kind.x_uuid if kind else '',
            'kindName': kind.name if kind else '',
            'name': self.name or '',
            'description': self.description_sale or '',
            'price': self.lst_price or 0.0,
            'currency': self.currency_id.name if self.currency_id else 'XOF',
            'imageUrl': image_url,
            'isAvailable': self.active and self.available_in_pos,
            'sortOrder': self.sequence or 0
        }
