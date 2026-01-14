# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ==========================================
    # Champs The Residence
    # ==========================================
    is_residence_member = fields.Boolean(
        string='Est un Membre',
        default=False,
        help='Indique si ce partenaire est un membre The Residence'
    )

    residence_external_id = fields.Char(
        string='ID Externe (UUID)',
        index=True,
        copy=False,
        help='UUID unique pour synchronisation avec l\'app mobile'
    )

    residence_qr_token = fields.Char(
        string='Token QR Code',
        copy=False,
        help='Token unique pour le QR Code du membre'
    )

    residence_membership_type_id = fields.Many2one(
        'residence.membership.type',
        string='Type d\'Abonnement'
    )

    residence_membership_status = fields.Selection([
        ('pending', 'En attente'),
        ('active', 'Actif'),
        ('expired', 'Expiré'),
        ('suspended', 'Suspendu'),
        ('cancelled', 'Annulé')
    ], string='Statut Membre', default='pending')

    residence_joined_date = fields.Date(
        string='Date d\'Adhésion'
    )

    # ==========================================
    # Abonnements
    # ==========================================
    residence_subscription_ids = fields.One2many(
        'residence.member.subscription',
        'partner_id',
        string='Abonnements'
    )

    residence_subscription_count = fields.Integer(
        string='Nb Abonnements',
        compute='_compute_residence_counts'
    )

    # ==========================================
    # Réservations
    # ==========================================
    residence_reservation_ids = fields.One2many(
        'sale.order',
        'partner_id',
        string='Réservations',
        domain=[('is_rental_order', '=', True)]
    )

    residence_reservation_count = fields.Integer(
        string='Nb Réservations',
        compute='_compute_residence_counts'
    )

    # ==========================================
    # Commandes
    # ==========================================
    residence_order_ids = fields.One2many(
        'residence.order',
        'partner_id',
        string='Commandes Restaurant'
    )

    residence_order_count = fields.Integer(
        string='Nb Commandes',
        compute='_compute_residence_counts'
    )

    @api.depends('residence_subscription_ids', 'residence_reservation_ids', 'residence_order_ids')
    def _compute_residence_counts(self):
        for partner in self:
            partner.residence_subscription_count = len(partner.residence_subscription_ids)
            partner.residence_reservation_count = self.env['sale.order'].search_count([
                ('partner_id', '=', partner.id),
                ('is_rental_order', '=', True)
            ])
            partner.residence_order_count = len(partner.residence_order_ids)

    # ==========================================
    # Méthodes
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_residence_member') and not vals.get('residence_external_id'):
                vals['residence_external_id'] = str(uuid.uuid4())
            if vals.get('is_residence_member') and not vals.get('residence_qr_token'):
                vals['residence_qr_token'] = f"member-{uuid.uuid4().hex[:12]}"
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('is_residence_member'):
            for partner in self:
                if not partner.residence_external_id:
                    vals['residence_external_id'] = str(uuid.uuid4())
                if not partner.residence_qr_token:
                    vals['residence_qr_token'] = f"member-{uuid.uuid4().hex[:12]}"
        return super().write(vals)

    def action_view_subscriptions(self):
        """Voir les abonnements du membre"""
        self.ensure_one()
        return {
            'name': _('Abonnements'),
            'type': 'ir.actions.act_window',
            'res_model': 'residence.member.subscription',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id}
        }

    def action_view_reservations(self):
        """Voir les réservations du membre"""
        self.ensure_one()
        return {
            'name': _('Réservations'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('is_rental_order', '=', True)
            ],
            'context': {'default_partner_id': self.id}
        }

    def action_view_orders(self):
        """Voir les commandes restaurant du membre"""
        self.ensure_one()
        return {
            'name': _('Commandes Restaurant'),
            'type': 'ir.actions.act_window',
            'res_model': 'residence.order',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id}
        }

    def generate_new_qr_token(self):
        """Générer un nouveau token QR"""
        for partner in self:
            partner.residence_qr_token = f"member-{uuid.uuid4().hex[:12]}"

    # ==========================================
    # API Methods
    # ==========================================
    def to_api_dict(self, include_details=False):
        """Convertir en format API"""
        self.ensure_one()
        data = {
            'id': self.residence_external_id,
            'firstName': self.name.split()[0] if self.name else '',
            'lastName': ' '.join(self.name.split()[1:]) if self.name and len(self.name.split()) > 1 else '',
            'email': self.email or '',
            'phone': self.phone or self.mobile or '',
            'companyName': self.parent_id.name if self.parent_id else (self.company_name or ''),
            'jobTitle': self.function or '',
            'membershipTypeName': self.residence_membership_type_id.name if self.residence_membership_type_id else '',
            'membershipTypeCode': self.residence_membership_type_id.code if self.residence_membership_type_id else '',
            'status': self.residence_membership_status or 'pending',
            'joinedAt': self.residence_joined_date.isoformat() if self.residence_joined_date else None,
            'qrToken': self.residence_qr_token or ''
        }

        if include_details:
            data.update({
                'address': {
                    'street': self.street or '',
                    'street2': self.street2 or '',
                    'city': self.city or '',
                    'zip': self.zip or '',
                    'country': self.country_id.name if self.country_id else ''
                },
                'membershipType': self.residence_membership_type_id.to_api_dict() if self.residence_membership_type_id else None,
                'reservationCount': self.residence_reservation_count,
                'orderCount': self.residence_order_count
            })

        return data

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver un partenaire par son ID externe"""
        return self.search([('residence_external_id', '=', external_id)], limit=1)

    @api.model
    def get_by_qr_token(self, qr_token):
        """Trouver un partenaire par son token QR"""
        return self.search([('residence_qr_token', '=', qr_token)], limit=1)

    @api.model
    def create_from_api(self, data):
        """Créer un membre depuis les données API"""
        # Construire le nom complet
        first_name = data.get('firstName', '')
        last_name = data.get('lastName', '')
        name = f"{first_name} {last_name}".strip() or data.get('email', 'Nouveau Membre')

        # Chercher le type d'abonnement
        membership_type = None
        if data.get('membershipTypeId'):
            membership_type = self.env['residence.membership.type'].get_by_external_id(
                data.get('membershipTypeId')
            )
        elif data.get('membershipTypeCode'):
            membership_type = self.env['residence.membership.type'].get_by_code(
                data.get('membershipTypeCode')
            )

        vals = {
            'name': name,
            'email': data.get('email'),
            'phone': data.get('phone'),
            'mobile': data.get('mobile'),
            'function': data.get('jobTitle'),
            'company_name': data.get('companyName'),
            'is_residence_member': True,
            'residence_external_id': data.get('id') or str(uuid.uuid4()),
            'residence_qr_token': data.get('qrToken') or f"member-{uuid.uuid4().hex[:12]}",
            'residence_membership_type_id': membership_type.id if membership_type else False,
            'residence_membership_status': data.get('status', 'pending'),
            'residence_joined_date': data.get('joinedAt') or fields.Date.today(),
        }

        # Adresse si fournie
        address = data.get('address', {})
        if address:
            vals.update({
                'street': address.get('street'),
                'street2': address.get('street2'),
                'city': address.get('city'),
                'zip': address.get('zip'),
            })
            if address.get('country'):
                country = self.env['res.country'].search([
                    ('name', 'ilike', address.get('country'))
                ], limit=1)
                if country:
                    vals['country_id'] = country.id

        return self.create(vals)

    def update_from_api(self, data):
        """Mettre à jour un membre depuis les données API"""
        self.ensure_one()

        vals = {}

        if data.get('firstName') or data.get('lastName'):
            first_name = data.get('firstName', self.name.split()[0] if self.name else '')
            last_name = data.get('lastName', ' '.join(self.name.split()[1:]) if self.name else '')
            vals['name'] = f"{first_name} {last_name}".strip()

        if 'email' in data:
            vals['email'] = data['email']
        if 'phone' in data:
            vals['phone'] = data['phone']
        if 'mobile' in data:
            vals['mobile'] = data['mobile']
        if 'jobTitle' in data:
            vals['function'] = data['jobTitle']
        if 'companyName' in data:
            vals['company_name'] = data['companyName']
        if 'status' in data:
            vals['residence_membership_status'] = data['status']
        if 'qrToken' in data:
            vals['residence_qr_token'] = data['qrToken']

        if data.get('membershipTypeId'):
            membership_type = self.env['residence.membership.type'].get_by_external_id(
                data['membershipTypeId']
            )
            if membership_type:
                vals['residence_membership_type_id'] = membership_type.id

        if vals:
            self.write(vals)

        return self
