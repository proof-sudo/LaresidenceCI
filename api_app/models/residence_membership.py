# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class ResidenceMembershipType(models.Model):
    _name = 'residence.membership.type'
    _description = 'Type d\'Abonnement Membre'
    _order = 'sequence, name'

    name = fields.Char(
        string='Nom du Type',
        required=True,
        translate=True
    )
    external_id = fields.Char(
        string='ID Externe (UUID)',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False,
        index=True
    )
    code = fields.Char(
        string='Code',
        required=True,
        help='Code unique pour ce type (ex: PREMIUM, GOLD, STANDARD)'
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    description = fields.Text(string='Description', translate=True)

    # Tarification
    price = fields.Monetary(
        string='Prix',
        currency_field='currency_id',
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # Durée
    duration_type = fields.Selection([
        ('monthly', 'Mensuel'),
        ('quarterly', 'Trimestriel'),
        ('biannual', 'Semestriel'),
        ('yearly', 'Annuel'),
        ('lifetime', 'À vie')
    ], string='Type de Durée', default='monthly', required=True)

    duration_months = fields.Integer(
        string='Durée (mois)',
        compute='_compute_duration_months',
        store=True
    )

    # Avantages
    discount_percentage = fields.Float(
        string='Réduction (%)',
        default=0,
        help='Pourcentage de réduction sur les locations et commandes'
    )
    free_reservation_hours = fields.Integer(
        string='Heures gratuites/mois',
        default=0,
        help='Nombre d\'heures de location gratuites par mois'
    )
    priority_booking = fields.Boolean(
        string='Réservation prioritaire',
        default=False
    )

    # Produit associé pour facturation
    product_id = fields.Many2one(
        'product.product',
        string='Produit Associé',
        help='Produit utilisé pour facturer l\'abonnement'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        required=True
    )

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code, company_id)', 'Le code doit être unique par société!'),
        ('external_id_unique', 'UNIQUE(external_id)', 'L\'ID externe doit être unique!')
    ]

    @api.depends('duration_type')
    def _compute_duration_months(self):
        mapping = {
            'monthly': 1,
            'quarterly': 3,
            'biannual': 6,
            'yearly': 12,
            'lifetime': 0
        }
        for rec in self:
            rec.duration_months = mapping.get(rec.duration_type, 1)

    @api.model_create_multi
    def create(self, vals_list):
        """Créer le produit associé automatiquement"""
        records = super().create(vals_list)
        Product = self.env['product.product']

        for rec in records:
            if not rec.product_id:
                product = Product.create({
                    'name': f"[ABO] {rec.name}",
                    'type': 'service',
                    'list_price': rec.price,
                    'sale_ok': True,
                    'purchase_ok': False,
                    'invoice_policy': 'order',
                })
                rec.product_id = product.id

        return records

    def to_api_dict(self):
        """Convertir en format API"""
        self.ensure_one()
        return {
            'id': self.external_id,
            'code': self.code,
            'name': self.name,
            'description': self.description or '',
            'price': self.price,
            'durationType': self.duration_type,
            'durationMonths': self.duration_months,
            'discountPercentage': self.discount_percentage,
            'freeReservationHours': self.free_reservation_hours,
            'priorityBooking': self.priority_booking
        }

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver par ID externe"""
        return self.search([('external_id', '=', external_id)], limit=1)

    @api.model
    def get_by_code(self, code):
        """Trouver par code"""
        return self.search([('code', '=', code)], limit=1)


class ResidenceMemberSubscription(models.Model):
    _name = 'residence.member.subscription'
    _description = 'Abonnement Membre'
    _order = 'date_start desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='/'
    )
    external_id = fields.Char(
        string='ID Externe (UUID)',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False,
        index=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Membre',
        required=True,
        tracking=True,
        domain=[('is_residence_member', '=', True)]
    )
    membership_type_id = fields.Many2one(
        'residence.membership.type',
        string='Type d\'Abonnement',
        required=True,
        tracking=True
    )

    # Dates
    date_start = fields.Date(
        string='Date de début',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    date_end = fields.Date(
        string='Date de fin',
        compute='_compute_date_end',
        store=True,
        tracking=True
    )

    # État
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('active', 'Actif'),
        ('expired', 'Expiré'),
        ('cancelled', 'Annulé')
    ], string='État', default='draft', tracking=True)

    # Facturation
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Devis/Commande',
        readonly=True
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Facture',
        readonly=True
    )
    amount = fields.Monetary(
        string='Montant',
        related='membership_type_id.price',
        currency_field='currency_id',
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='membership_type_id.currency_id'
    )

    # Auto-renouvellement
    auto_renew = fields.Boolean(
        string='Renouvellement Auto',
        default=False
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

    @api.depends('date_start', 'membership_type_id', 'membership_type_id.duration_months')
    def _compute_date_end(self):
        for rec in self:
            if rec.date_start and rec.membership_type_id:
                if rec.membership_type_id.duration_type == 'lifetime':
                    rec.date_end = False
                else:
                    rec.date_end = rec.date_start + relativedelta(
                        months=rec.membership_type_id.duration_months
                    )
            else:
                rec.date_end = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'residence.member.subscription'
                ) or '/'
        return super().create(vals_list)

    def action_activate(self):
        """Activer l'abonnement"""
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'active'
                # Mettre à jour le partenaire
                rec.partner_id.write({
                    'residence_membership_type_id': rec.membership_type_id.id,
                    'residence_membership_status': 'active'
                })

    def action_cancel(self):
        """Annuler l'abonnement"""
        for rec in self:
            rec.state = 'cancelled'

    def action_create_sale_order(self):
        """Créer un devis pour cet abonnement"""
        self.ensure_one()
        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.sale_order_id.id,
                'view_mode': 'form',
            }

        SaleOrder = self.env['sale.order']
        order = SaleOrder.create({
            'partner_id': self.partner_id.id,
            'order_line': [(0, 0, {
                'product_id': self.membership_type_id.product_id.id,
                'product_uom_qty': 1,
                'price_unit': self.membership_type_id.price,
                'name': f"Abonnement {self.membership_type_id.name} - {self.name}",
            })]
        })
        self.sale_order_id = order.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
        }

    @api.model
    def _cron_check_expired_subscriptions(self):
        """Cron pour vérifier et expirer les abonnements"""
        today = fields.Date.today()
        expired = self.search([
            ('state', '=', 'active'),
            ('date_end', '!=', False),
            ('date_end', '<', today)
        ])
        for sub in expired:
            sub.state = 'expired'
            sub.partner_id.write({
                'residence_membership_status': 'expired'
            })

    def to_api_dict(self):
        """Convertir en format API"""
        self.ensure_one()
        return {
            'id': self.external_id,
            'reference': self.name,
            'memberId': self.partner_id.residence_external_id,
            'membershipTypeId': self.membership_type_id.external_id,
            'membershipTypeName': self.membership_type_id.name,
            'dateStart': self.date_start.isoformat() if self.date_start else None,
            'dateEnd': self.date_end.isoformat() if self.date_end else None,
            'state': self.state,
            'amount': self.amount,
            'autoRenew': self.auto_renew
        }

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver par ID externe"""
        return self.search([('external_id', '=', external_id)], limit=1)
