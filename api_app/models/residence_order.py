# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResidenceOrder(models.Model):
    _name = 'residence.order'
    _description = 'Commande Restaurant'
    _order = 'create_date desc'
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

    # Client
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True
    )

    # Mode de livraison
    mode = fields.Selection([
        ('pickup', 'À emporter'),
        ('delivery', 'Livraison'),
        ('onsite', 'Sur place')
    ], string='Mode', default='pickup', required=True, tracking=True)

    delivery_address = fields.Text(string='Adresse de Livraison')

    # État
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('preparing', 'En préparation'),
        ('ready', 'Prête'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='État', default='draft', tracking=True)

    # QR Code pour récupération
    qr_token = fields.Char(
        string='Token QR',
        default=lambda self: f"order-{uuid.uuid4().hex[:12]}",
        readonly=True,
        copy=False
    )

    # Lignes de commande
    line_ids = fields.One2many(
        'residence.order.line',
        'order_id',
        string='Articles'
    )

    # Montants
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    amount_untaxed = fields.Monetary(
        string='Sous-total',
        compute='_compute_amounts',
        store=True
    )

    amount_tax = fields.Monetary(
        string='Taxes',
        compute='_compute_amounts',
        store=True
    )

    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amounts',
        store=True
    )

    # Notes
    notes = fields.Text(string='Notes')
    cancellation_reason = fields.Text(string='Motif d\'Annulation')

    # Dates
    ordered_date = fields.Datetime(
        string='Date de Commande',
        default=fields.Datetime.now
    )

    confirmed_date = fields.Datetime(string='Date de Confirmation')
    ready_date = fields.Datetime(string='Date Prêt')
    completed_date = fields.Datetime(string='Date de Fin')

    # Temps de préparation estimé
    estimated_prep_time = fields.Integer(
        string='Temps de Préparation Estimé (min)',
        compute='_compute_estimated_prep_time',
        store=True
    )

    # Lien vers sale.order
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Devis/Commande',
        readonly=True
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

    @api.depends('line_ids.subtotal')
    def _compute_amounts(self):
        for order in self:
            amount_untaxed = sum(order.line_ids.mapped('subtotal'))
            # Simplification: pas de calcul de taxes ici
            order.amount_untaxed = amount_untaxed
            order.amount_tax = 0
            order.amount_total = amount_untaxed

    @api.depends('line_ids.product_id')
    def _compute_estimated_prep_time(self):
        for order in self:
            max_time = 0
            for line in order.line_ids:
                if line.product_id and line.product_id.product_tmpl_id.residence_preparation_time:
                    prep_time = line.product_id.product_tmpl_id.residence_preparation_time
                    if prep_time > max_time:
                        max_time = prep_time
            order.estimated_prep_time = max_time or 15

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('residence.order') or '/'
        return super().create(vals_list)

    # ==========================================
    # Actions de workflow
    # ==========================================
    def action_submit(self):
        """Soumettre la commande"""
        for order in self:
            if order.state != 'draft':
                raise UserError(_('Seules les commandes en brouillon peuvent être soumises'))
            if not order.line_ids:
                raise UserError(_('La commande doit avoir au moins un article'))

            order.state = 'pending'
            order.ordered_date = fields.Datetime.now()
            order._send_order_webhook('ORDER_CREATED', None, 'PENDING')

    def action_confirm(self):
        """Confirmer la commande"""
        for order in self:
            if order.state != 'pending':
                raise UserError(_('Seules les commandes en attente peuvent être confirmées'))

            prev_state = order.state
            order.state = 'confirmed'
            order.confirmed_date = fields.Datetime.now()
            order._create_sale_order()
            order._send_order_webhook('ORDER_STATUS_CHANGED', prev_state.upper(), 'CONFIRMED')

    def action_start_preparation(self):
        """Commencer la préparation"""
        for order in self:
            if order.state != 'confirmed':
                raise UserError(_('Seules les commandes confirmées peuvent être préparées'))

            prev_state = order.state
            order.state = 'preparing'
            order._send_order_webhook('ORDER_STATUS_CHANGED', prev_state.upper(), 'PREPARING')

    def action_mark_ready(self):
        """Marquer comme prête"""
        for order in self:
            if order.state not in ('confirmed', 'preparing'):
                raise UserError(_('Cette commande ne peut pas être marquée comme prête'))

            prev_state = order.state
            order.state = 'ready'
            order.ready_date = fields.Datetime.now()
            order._send_order_webhook('ORDER_STATUS_CHANGED', prev_state.upper(), 'READY')

    def action_complete(self):
        """Terminer la commande"""
        for order in self:
            if order.state != 'ready':
                raise UserError(_('Seules les commandes prêtes peuvent être terminées'))

            prev_state = order.state
            order.state = 'completed'
            order.completed_date = fields.Datetime.now()
            order._send_order_webhook('ORDER_STATUS_CHANGED', prev_state.upper(), 'COMPLETED')

    def action_cancel(self, reason=None):
        """Annuler la commande"""
        for order in self:
            if order.state in ('completed', 'cancelled'):
                raise UserError(_('Cette commande ne peut pas être annulée'))

            prev_state = order.state
            order.state = 'cancelled'
            if reason:
                order.cancellation_reason = reason
            order._send_order_webhook('ORDER_CANCELLED', prev_state.upper(), 'CANCELLED')

    def action_reset_to_draft(self):
        """Remettre en brouillon"""
        for order in self:
            if order.state == 'cancelled':
                order.state = 'draft'

    # ==========================================
    # Méthodes utilitaires
    # ==========================================
    def _create_sale_order(self):
        """Créer un devis depuis la commande"""
        self.ensure_one()
        if self.sale_order_id:
            return

        order_lines = []
        for line in self.line_ids:
            order_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'price_unit': line.unit_price,
                'name': line.product_id.name,
            }))

        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'order_line': order_lines,
            'note': f"Commande Restaurant: {self.name}\n{self.notes or ''}"
        })

        self.sale_order_id = sale_order.id

        # Auto-confirmer si configuré
        config = self.env['residence.config'].get_config()
        if config and config.auto_confirm_order:
            sale_order.action_confirm()

    def _send_order_webhook(self, event_type, prev_status, new_status):
        """Envoyer un webhook pour la commande"""
        self.ensure_one()
        config = self.env['residence.config'].get_config()
        if config:
            config.send_webhook(
                event_type=event_type,
                entity_type='order',
                entity_id=self.external_id,
                data=self.to_api_dict(),
                previous_status=prev_status,
                new_status=new_status
            )

    # ==========================================
    # API Methods
    # ==========================================
    def to_api_dict(self):
        """Convertir en format API"""
        self.ensure_one()

        items = []
        for line in self.line_ids:
            items.append(line.to_api_dict())

        return {
            'id': self.external_id,
            'reference': self.name,
            'memberId': self.partner_id.residence_external_id,
            'memberFirstName': self.partner_id.name.split()[0] if self.partner_id.name else '',
            'memberLastName': ' '.join(self.partner_id.name.split()[1:]) if self.partner_id.name else '',
            'memberEmail': self.partner_id.email or '',
            'mode': self.mode.upper() if self.mode else 'PICKUP',
            'status': self.state.upper() if self.state else 'DRAFT',
            'totalAmount': self.amount_total,
            'qrToken': self.qr_token,
            'deliveryAddress': self.delivery_address or '',
            'notes': self.notes or '',
            'cancellationReason': self.cancellation_reason or '',
            'estimatedPrepTime': self.estimated_prep_time,
            'items': items,
            'orderedAt': self.ordered_date.isoformat() if self.ordered_date else None,
            'confirmedAt': self.confirmed_date.isoformat() if self.confirmed_date else None,
            'readyAt': self.ready_date.isoformat() if self.ready_date else None,
            'completedAt': self.completed_date.isoformat() if self.completed_date else None,
            'createdAt': self.create_date.isoformat() if self.create_date else None,
            'updatedAt': self.write_date.isoformat() if self.write_date else None
        }

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver par ID externe"""
        return self.search([('external_id', '=', external_id)], limit=1)

    @api.model
    def create_from_api(self, data):
        """Créer une commande depuis les données API"""
        # Trouver le membre
        partner = self.env['res.partner'].get_by_external_id(data.get('memberId'))
        if not partner:
            raise ValidationError(_('Membre non trouvé: %s') % data.get('memberId'))

        # Préparer les lignes
        order_lines = []
        for item_data in data.get('items', []):
            product_tmpl = self.env['product.template'].get_by_external_id(item_data.get('menuItemId'))
            if not product_tmpl:
                raise ValidationError(_('Article menu non trouvé: %s') % item_data.get('menuItemId'))

            product = product_tmpl.product_variant_id
            order_lines.append((0, 0, {
                'product_id': product.id,
                'quantity': item_data.get('quantity', 1),
                'unit_price': item_data.get('unitPrice') or product.list_price,
                'notes': item_data.get('notes', ''),
            }))

        if not order_lines:
            raise ValidationError(_('La commande doit contenir au moins un article'))

        # Créer la commande
        order = self.create({
            'partner_id': partner.id,
            'external_id': data.get('id') or str(uuid.uuid4()),
            'mode': data.get('mode', 'pickup').lower(),
            'delivery_address': data.get('deliveryAddress'),
            'notes': data.get('notes'),
            'line_ids': order_lines,
            'state': 'draft'
        })

        # Soumettre automatiquement
        order.action_submit()

        # Auto-confirmer si configuré
        config = self.env['residence.config'].get_config()
        if config and config.auto_confirm_order:
            order.action_confirm()

        return order


class ResidenceOrderLine(models.Model):
    _name = 'residence.order.line'
    _description = 'Ligne de Commande Restaurant'

    order_id = fields.Many2one(
        'residence.order',
        string='Commande',
        required=True,
        ondelete='cascade'
    )

    external_id = fields.Char(
        string='ID Externe (UUID)',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False
    )

    product_id = fields.Many2one(
        'product.product',
        string='Article',
        required=True,
        domain=[('product_tmpl_id.is_residence_menu_item', '=', True)]
    )

    quantity = fields.Integer(
        string='Quantité',
        default=1,
        required=True
    )

    unit_price = fields.Monetary(
        string='Prix Unitaire',
        currency_field='currency_id',
        required=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='order_id.currency_id'
    )

    subtotal = fields.Monetary(
        string='Sous-total',
        compute='_compute_subtotal',
        store=True
    )

    notes = fields.Text(string='Notes')

    # État de préparation
    preparation_state = fields.Selection([
        ('pending', 'En attente'),
        ('preparing', 'En préparation'),
        ('ready', 'Prêt')
    ], string='État Préparation', default='pending')

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.list_price

    def to_api_dict(self):
        """Convertir en format API"""
        self.ensure_one()
        return {
            'id': self.external_id,
            'menuItemId': self.product_id.product_tmpl_id.residence_external_id if self.product_id else None,
            'menuItemName': self.product_id.name if self.product_id else '',
            'quantity': self.quantity,
            'unitPrice': self.unit_price,
            'amount': self.subtotal,
            'notes': self.notes or '',
            'preparationState': self.preparation_state.upper() if self.preparation_state else 'PENDING'
        }
