# -*- coding: utf-8 -*-

import uuid
import secrets
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Champs The Residence
    x_tr_uuid = fields.Char(string='UUID TR', copy=False, readonly=True, index=True)
    x_tr_qr_token = fields.Char(string='Token QR', copy=False, readonly=True)
    x_tr_is_member = fields.Boolean(string='Est membre TR', default=False)
    x_tr_member_status = fields.Selection([
        ('PENDING', 'En attente'),
        ('ACTIVE', 'Actif'),
        ('SUSPENDED', 'Suspendu'),
        ('INACTIVE', 'Inactif'),
    ], string='Statut membre', default='PENDING')
    x_tr_membership_type_id = fields.Many2one('theresidence.membership.type', string='Type d\'adhésion')
    x_tr_joined_at = fields.Date(string='Date d\'adhésion')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('x_tr_is_member') and not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())
                vals['x_tr_qr_token'] = f"member-{secrets.token_urlsafe(16)}"
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('x_tr_is_member'):
            for partner in self:
                if not partner.x_tr_uuid:
                    vals.setdefault('x_tr_uuid', str(uuid.uuid4()))
                if not partner.x_tr_qr_token:
                    vals.setdefault('x_tr_qr_token', f"member-{secrets.token_urlsafe(16)}")
        return super().write(vals)

    def to_member_api_dict(self):
        self.ensure_one()
        name_parts = (self.name or '').split(' ', 1)
        return {
            'id': self.x_tr_uuid or str(self.id),
            'firstName': name_parts[0] if name_parts else '',
            'lastName': name_parts[1] if len(name_parts) > 1 else '',
            'email': self.email or '',
            'phone': self.phone or self.mobile or '',
            'companyName': self.parent_id.name if self.parent_id else (self.company_name or ''),
            'jobTitle': self.function or '',
            'membershipTypeId': self.x_tr_membership_type_id.x_uuid if self.x_tr_membership_type_id else None,
            'membershipTypeCode': self.x_tr_membership_type_id.code if self.x_tr_membership_type_id else '',
            'membershipTypeName': self.x_tr_membership_type_id.name if self.x_tr_membership_type_id else '',
            'status': self.x_tr_member_status or 'ACTIVE',
            'joinedAt': self.x_tr_joined_at.isoformat() if self.x_tr_joined_at else '',
            'qrToken': self.x_tr_qr_token or ''
        }

    @api.model
    def create_member_from_api(self, data):
        first_name = data.get('firstName', '')
        last_name = data.get('lastName', '')
        name = f"{first_name} {last_name}".strip() or data.get('email', 'Unknown')
        
        vals = {
            'name': name,
            'email': data.get('email'),
            'phone': data.get('phone'),
            'function': data.get('jobTitle'),
            'company_name': data.get('companyName'),
            'x_tr_is_member': True,
            'x_tr_member_status': data.get('status', 'ACTIVE'),
            'x_tr_joined_at': data.get('joinedAt') or fields.Date.today(),
        }
        
        if data.get('membershipTypeCode'):
            mtype = self.env['theresidence.membership.type'].search([('code', '=', data['membershipTypeCode'])], limit=1)
            if mtype:
                vals['x_tr_membership_type_id'] = mtype.id
        
        if data.get('email'):
            existing = self.search([('email', '=', data['email'])], limit=1)
            if existing:
                existing.write(vals)
                return existing
        
        return self.create(vals)
