# -*- coding: utf-8 -*-

import uuid
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _planning_slot_generation(self):
        """Skip planning slot generation for The Residence reservation orders."""
        lines = self.filtered(lambda l: not l.order_id.x_tr_is_reservation)
        return super(SaleOrderLine, lines)._planning_slot_generation()


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # === Champs Réservation ===
    x_tr_uuid = fields.Char(string='UUID TR', copy=False, readonly=True, index=True)
    x_tr_is_reservation = fields.Boolean(string='Est une réservation TR', default=False)
    x_tr_reservation_status = fields.Selection([
        ('PENDING', 'En attente'),
        ('RESERVED', 'Réservé'),
        ('ARRIVED', 'Arrivé'),
        ('CANCELLED', 'Annulée'),
        ('COMPLETED', 'Terminée'),
    ], string='Statut réservation', default='PENDING')
    x_tr_space_id = fields.Many2one('product.template', string='Espace', domain=[('x_tr_is_space', '=', True)])
    x_tr_start_time = fields.Datetime(string='Début')
    x_tr_end_time = fields.Datetime(string='Fin')
    x_tr_guest_count = fields.Integer(string='Nb invités')
    x_tr_notes = fields.Text(string='Notes')
    x_tr_rejection_reason = fields.Text(string='Raison du rejet')
    x_tr_qr_token = fields.Char(string='Token QR', copy=False)
    x_tr_invitee_ids = fields.One2many('theresidence.reservation.invitee', 'reservation_id', string='Invités')
    x_tr_option_ids = fields.One2many('theresidence.reservation.option', 'reservation_id', string='Options')

    # === Champs Abonnement ===
    x_tr_is_subscription = fields.Boolean(string='Est un abonnement TR', default=False)
    x_tr_subscription_status = fields.Selection([
        ('ACTIVE', 'Actif'),
        ('PAUSED', 'En pause'),
        ('CANCELLED', 'Annulé'),
        ('EXPIRED', 'Expiré'),
    ], string='Statut abonnement', default='ACTIVE')
    x_tr_plan_id = fields.Many2one('product.template', string='Plan', domain=[('x_tr_is_subscription_plan', '=', True)])
    x_tr_billing_period = fields.Selection([
        ('MONTHLY', 'Mensuel'),
        ('QUARTERLY', 'Trimestriel'),
        ('YEARLY', 'Annuel'),
    ], string='Période facturation', default='MONTHLY')
    x_tr_auto_renew = fields.Boolean(string='Renouvellement auto', default=True)
    x_tr_sub_start_date = fields.Date(string='Début abonnement')
    x_tr_sub_end_date = fields.Date(string='Fin abonnement')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('x_tr_is_reservation') and not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())
                vals['x_tr_qr_token'] = f"res-{uuid.uuid4().hex[:12]}"
            if vals.get('x_tr_is_subscription') and not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())
        return super().create(vals_list)

    # === API Réservation ===
    def to_reservation_api_dict(self):
        self.ensure_one()
        return {
            'id': self.x_tr_uuid or str(self.id),
            'memberId': self.partner_id.x_tr_uuid or str(self.partner_id.id),
            'memberFirstName': (self.partner_id.name or '').split(' ')[0],
            'memberLastName': ' '.join((self.partner_id.name or '').split(' ')[1:]),
            'memberEmail': self.partner_id.email or '',
            'spaceId': self.x_tr_space_id.x_tr_space_uuid if self.x_tr_space_id else '',
            'spaceName': self.x_tr_space_id.name if self.x_tr_space_id else '',
            'startTime': self.x_tr_start_time.isoformat() if self.x_tr_start_time else '',
            'endTime': self.x_tr_end_time.isoformat() if self.x_tr_end_time else '',
            'guestCount': self.x_tr_guest_count or 0,
            'status': self.x_tr_reservation_status or 'PENDING',
            'totalAmount': self.amount_total or 0.0,
            'currency': self.currency_id.name if self.currency_id else 'XOF',
            'notes': self.x_tr_notes or '',
            'saleOrder': self.name,
            'qrToken': self.x_tr_qr_token or '',
            'options': [opt.to_api_dict() for opt in self.x_tr_option_ids],
            'invitees': [inv.to_api_dict() for inv in self.x_tr_invitee_ids],
            'createdAt': self.create_date.isoformat() if self.create_date else '',
            'updatedAt': self.write_date.isoformat() if self.write_date else ''
        }

    @api.model
    def get_pos_reservations(self, date_filter='today'):
        domain = [('x_tr_is_reservation', '=', True)]

        if date_filter == 'today':
            today = fields.Date.today()
            tomorrow = today + timedelta(days=1)
            domain += [
                '|',
                # Réservations du jour (PENDING ou RESERVED)
                '&', '&',
                ('x_tr_reservation_status', 'in', ['PENDING', 'RESERVED']),
                ('x_tr_start_time', '>=', fields.Datetime.to_datetime(today)),
                ('x_tr_start_time', '<', fields.Datetime.to_datetime(tomorrow)),
                # Réservations en cours (ARRIVED) quelle que soit la date
                ('x_tr_reservation_status', '=', 'ARRIVED'),
            ]

        reservations = self.search(domain, order='x_tr_start_time asc')
        return [r.to_reservation_api_dict() for r in reservations]

    @api.model
    def create_reservation_from_api(self, data):
        partner = self.env['res.partner'].search([('x_tr_uuid', '=', data.get('memberId'))], limit=1)
        if not partner:
            raise ValidationError(_("Membre non trouvé: %s") % data.get('memberId'))
        
        space = self.env['product.template'].search([
            ('x_tr_space_uuid', '=', data.get('spaceId')),
            ('x_tr_is_space', '=', True)
        ], limit=1)
        if not space:
            raise ValidationError(_("Espace non trouvé: %s") % data.get('spaceId'))
        
        if not data.get('startTime') or not data.get('endTime'):
            raise ValidationError(_("Les champs startTime et endTime sont obligatoires."))
        start_time = datetime.fromisoformat(data['startTime'].replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(data['endTime'].replace('Z', '+00:00'))
        if end_time <= start_time:
            raise ValidationError(_("endTime doit être postérieur à startTime."))

        # Vérification disponibilité (garde-fou même si le controller a déjà vérifié)
        avail = space.check_availability(start_time, end_time)
        if not avail.get('isAvailable'):
            raise ValidationError(_("L'espace '%s' n'est pas disponible pour ce créneau.") % space.name)

        order = self.create({
            'partner_id': partner.id,
            'x_tr_is_reservation': True,
            'x_tr_reservation_status': 'PENDING',
            'x_tr_space_id': space.id,
            'x_tr_start_time': start_time,
            'x_tr_end_time': end_time,
            'x_tr_guest_count': data.get('guestCount', 1),
            'x_tr_notes': data.get('notes', ''),
        })
        
        # Créer la ligne de commande
        product = space.product_variant_ids[:1]
        if product:
            self.env['sale.order.line'].sudo().create({
                'order_id': order.id,
                'product_id': product.id,
                'name': space.name,
                'product_uom_qty': 1,
                'price_unit': space.list_price or 0.0,
            })
        
        # Créer les invités
        for inv_data in data.get('invitees', []):
            self.env['theresidence.reservation.invitee'].create({
                'reservation_id': order.id,
                'name': inv_data.get('name') or inv_data.get('fullName', ''),
                'email': inv_data.get('email', ''),
                'phone': inv_data.get('phone', ''),
            })
        
        # Créer les options
        for opt_id in data.get('optionIds', []):
            opt_def = self.env['theresidence.reservation.option.def'].search([('x_uuid', '=', opt_id)], limit=1)
            if opt_def:
                self.env['theresidence.reservation.option'].create({
                    'reservation_id': order.id,
                    'option_def_id': opt_def.id,
                    'name': opt_def.name,
                    'quantity': 1,
                    'unit_price': opt_def.price,
                })
        
        self.env['theresidence.webhook'].trigger_event(
            'RESERVATION_CREATED', 'reservation', order.x_tr_uuid,
            order.to_reservation_api_dict(), None, 'PENDING'
        )
        return order

    @api.constrains('x_tr_reservation_status', 'x_tr_space_id', 'x_tr_start_time', 'x_tr_end_time')
    def _check_no_double_booking(self):
        for order in self:
            if not order.x_tr_is_reservation:
                continue
            if order.x_tr_reservation_status not in ('PENDING', 'RESERVED', 'ARRIVED'):
                continue
            if not order.x_tr_space_id or not order.x_tr_start_time or not order.x_tr_end_time:
                continue
            conflicting = self.env['sale.order'].sudo().search_count([
                ('id', '!=', order.id),
                ('x_tr_is_reservation', '=', True),
                ('x_tr_reservation_status', 'in', ['PENDING', 'RESERVED', 'ARRIVED']),
                ('x_tr_space_id', '=', order.x_tr_space_id.id),
                ('x_tr_start_time', '<', order.x_tr_end_time),
                ('x_tr_end_time', '>', order.x_tr_start_time),
            ])
            if conflicting:
                raise ValidationError(_(
                    "L'espace '%s' n'est pas disponible pour ce créneau."
                ) % order.x_tr_space_id.name)

    def action_reserve_reservation(self):
        for order in self:
            if order.x_tr_reservation_status != 'PENDING':
                raise ValidationError(_("Seules les réservations en attente peuvent être réservées."))
            old = order.x_tr_reservation_status
            order.write({'x_tr_reservation_status': 'RESERVED'})
            if order.x_tr_space_id:
                order.x_tr_space_id.write({'x_tr_is_occupied': True})
            self.env['theresidence.webhook'].trigger_event(
                'RESERVATION_STATUS_CHANGED', 'reservation', order.x_tr_uuid,
                order.to_reservation_api_dict(), old, 'RESERVED'
            )

    def action_arrive_reservation(self):
        for order in self:
            if order.x_tr_reservation_status != 'RESERVED':
                raise ValidationError(_("Seules les réservations réservées peuvent être marquées arrivées."))
            old = order.x_tr_reservation_status
            order.write({'x_tr_reservation_status': 'ARRIVED'})
            self.env['theresidence.webhook'].trigger_event(
                'RESERVATION_STATUS_CHANGED', 'reservation', order.x_tr_uuid,
                order.to_reservation_api_dict(), old, 'ARRIVED'
            )

    def action_release_reservation(self):
        for order in self:
            if order.x_tr_reservation_status not in ('RESERVED', 'ARRIVED'):
                raise ValidationError(_("Seules les réservations réservées ou arrivées peuvent être libérées."))
            old = order.x_tr_reservation_status
            order.write({'x_tr_reservation_status': 'COMPLETED'})
            if order.x_tr_space_id:
                order.x_tr_space_id.write({'x_tr_is_occupied': False})
            self.env['theresidence.webhook'].trigger_event(
                'RESERVATION_STATUS_CHANGED', 'reservation', order.x_tr_uuid,
                order.to_reservation_api_dict(), old, 'COMPLETED'
            )

    def action_cancel_reservation(self):
        for order in self:
            if order.x_tr_reservation_status in ('COMPLETED', 'CANCELLED'):
                raise ValidationError(_("Cette réservation ne peut plus être annulée."))
            old = order.x_tr_reservation_status
            if order.x_tr_space_id and old in ('RESERVED', 'ARRIVED'):
                order.x_tr_space_id.write({'x_tr_is_occupied': False})
            order.write({'x_tr_reservation_status': 'CANCELLED'})
            self.env['theresidence.webhook'].trigger_event(
                'RESERVATION_CANCELLED', 'reservation', order.x_tr_uuid,
                order.to_reservation_api_dict(), old, 'CANCELLED'
            )

    # === Alias API (compatibilité endpoints /approve /reject /check-in) ===

    def action_approve_reservation(self):
        """Alias : PENDING → RESERVED (approuver = réserver l'espace)."""
        return self.action_reserve_reservation()

    def action_reject_reservation(self, reason=''):
        """PENDING → CANCELLED avec raison de rejet."""
        for order in self:
            if order.x_tr_reservation_status != 'PENDING':
                raise ValidationError(_("Seules les réservations en attente peuvent être rejetées."))
            old = order.x_tr_reservation_status
            order.write({
                'x_tr_reservation_status': 'CANCELLED',
                'x_tr_rejection_reason': reason or '',
            })
            self.env['theresidence.webhook'].trigger_event(
                'RESERVATION_STATUS_CHANGED', 'reservation', order.x_tr_uuid,
                order.to_reservation_api_dict(), old, 'CANCELLED'
            )

    def action_checkin_reservation(self):
        """Alias : RESERVED → ARRIVED (check-in = arrivée du membre)."""
        return self.action_arrive_reservation()

    # === Actions POS (appelées par UUID depuis le frontend) ===

    @api.model
    def pos_reserve_reservation(self, uuid):
        order = self.search([('x_tr_uuid', '=', uuid), ('x_tr_is_reservation', '=', True)], limit=1)
        if not order:
            raise ValidationError(_("Réservation introuvable: %s") % uuid)
        order.action_reserve_reservation()
        return order.to_reservation_api_dict()

    @api.model
    def pos_arrive_reservation(self, uuid):
        order = self.search([('x_tr_uuid', '=', uuid), ('x_tr_is_reservation', '=', True)], limit=1)
        if not order:
            raise ValidationError(_("Réservation introuvable: %s") % uuid)
        order.action_arrive_reservation()
        return order.to_reservation_api_dict()

    @api.model
    def pos_release_reservation(self, uuid):
        order = self.search([('x_tr_uuid', '=', uuid), ('x_tr_is_reservation', '=', True)], limit=1)
        if not order:
            raise ValidationError(_("Réservation introuvable: %s") % uuid)
        order.action_release_reservation()
        return order.to_reservation_api_dict()

    @api.model
    def pos_cancel_reservation(self, uuid):
        order = self.search([('x_tr_uuid', '=', uuid), ('x_tr_is_reservation', '=', True)], limit=1)
        if not order:
            raise ValidationError(_("Réservation introuvable: %s") % uuid)
        order.action_cancel_reservation()
        return order.to_reservation_api_dict()

    # === API Abonnement ===
    def to_subscription_api_dict(self):
        self.ensure_one()
        return {
            'id': self.x_tr_uuid or str(self.id),
            'memberId': self.partner_id.x_tr_uuid if self.partner_id else '',
            'memberFirstName': (self.partner_id.name or '').split(' ')[0] if self.partner_id else '',
            'memberLastName': ' '.join((self.partner_id.name or '').split(' ')[1:]) if self.partner_id else '',
            'memberEmail': self.partner_id.email if self.partner_id else '',
            'planId': self.x_tr_plan_id.x_tr_space_uuid if self.x_tr_plan_id else '',
            'planName': self.x_tr_plan_id.name if self.x_tr_plan_id else '',
            'status': self.x_tr_subscription_status or 'ACTIVE',
            'billingPeriod': self.x_tr_billing_period or 'MONTHLY',
            'autoRenew': self.x_tr_auto_renew,
            'amount': self.amount_total or 0.0,
            'currency': self.currency_id.name if self.currency_id else 'XOF',
            'startDate': self.x_tr_sub_start_date.isoformat() if self.x_tr_sub_start_date else '',
            'endDate': self.x_tr_sub_end_date.isoformat() if self.x_tr_sub_end_date else '',
            'createdAt': self.create_date.isoformat() if self.create_date else '',
            'updatedAt': self.write_date.isoformat() if self.write_date else ''
        }

    @api.model
    def create_subscription_from_api(self, data):
        partner = self.env['res.partner'].search([('x_tr_uuid', '=', data.get('memberId'))], limit=1)
        if not partner:
            raise ValidationError(_("Membre non trouvé: %s") % data.get('memberId'))
        
        plan = self.env['product.template'].search([
            ('x_tr_space_uuid', '=', data.get('planId')),
            ('x_tr_is_subscription_plan', '=', True)
        ], limit=1)
        
        sub = self.create({
            'partner_id': partner.id,
            'x_tr_is_subscription': True,
            'x_tr_subscription_status': 'ACTIVE',
            'x_tr_plan_id': plan.id if plan else False,
            'x_tr_billing_period': data.get('billingPeriod', 'MONTHLY'),
            'x_tr_auto_renew': data.get('autoRenew', True),
            'x_tr_sub_start_date': data.get('startDate') or fields.Date.today(),
        })
        
        if plan:
            self.env['sale.order.line'].create({
                'order_id': sub.id,
                'product_id': plan.product_variant_id.id,
                'product_uom_qty': 1,
            })
        
        self.env['theresidence.webhook'].trigger_event(
            'SUBSCRIPTION_CREATED', 'subscription', sub.x_tr_uuid,
            sub.to_subscription_api_dict(), None, 'ACTIVE'
        )
        return sub

    def action_pause_subscription(self):
        for sub in self:
            if sub.x_tr_subscription_status != 'ACTIVE':
                raise ValidationError(_("Seuls les abonnements actifs peuvent être mis en pause."))
            old = sub.x_tr_subscription_status
            sub.x_tr_subscription_status = 'PAUSED'
            self.env['theresidence.webhook'].trigger_event(
                'SUBSCRIPTION_STATUS_CHANGED', 'subscription', sub.x_tr_uuid,
                sub.to_subscription_api_dict(), old, 'PAUSED'
            )

    def action_resume_subscription(self):
        for sub in self:
            if sub.x_tr_subscription_status != 'PAUSED':
                raise ValidationError(_("Seuls les abonnements en pause peuvent être repris."))
            old = sub.x_tr_subscription_status
            sub.x_tr_subscription_status = 'ACTIVE'
            self.env['theresidence.webhook'].trigger_event(
                'SUBSCRIPTION_STATUS_CHANGED', 'subscription', sub.x_tr_uuid,
                sub.to_subscription_api_dict(), old, 'ACTIVE'
            )

    def action_cancel_subscription(self):
        for sub in self:
            if sub.x_tr_subscription_status in ('CANCELLED', 'EXPIRED'):
                raise ValidationError(_("Cet abonnement ne peut plus être annulé."))
            old = sub.x_tr_subscription_status
            sub.x_tr_subscription_status = 'CANCELLED'
            self.env['theresidence.webhook'].trigger_event(
                'SUBSCRIPTION_CANCELLED', 'subscription', sub.x_tr_uuid,
                sub.to_subscription_api_dict(), old, 'CANCELLED'
            )


class TheResidenceReservationInvitee(models.Model):
    _name = 'theresidence.reservation.invitee'
    _description = 'Invité de réservation'

    reservation_id = fields.Many2one('sale.order', string='Réservation', required=True, ondelete='cascade')
    x_uuid = fields.Char(string='UUID', default=lambda self: str(uuid.uuid4()))
    name = fields.Char(string='Nom', required=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Téléphone')

    def to_api_dict(self):
        return {
            'id': self.x_uuid or str(self.id),
            'fullName': self.name or '',
            'email': self.email or '',
            'phone': self.phone or ''
        }


class TheResidenceReservationOption(models.Model):
    _name = 'theresidence.reservation.option'
    _description = 'Option de réservation'

    reservation_id = fields.Many2one('sale.order', string='Réservation', required=True, ondelete='cascade')
    option_def_id = fields.Many2one('theresidence.reservation.option.def', string='Option')
    name = fields.Char(string='Nom')
    quantity = fields.Integer(string='Quantité', default=1)
    unit_price = fields.Float(string='Prix unitaire')
    amount = fields.Float(string='Montant', compute='_compute_amount', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for opt in self:
            opt.amount = opt.quantity * opt.unit_price

    @api.onchange('option_def_id')
    def _onchange_option_def_id(self):
        if self.option_def_id:
            self.name = self.option_def_id.name
            self.unit_price = self.option_def_id.price

    def to_api_dict(self):
        return {
            'id': str(self.id),
            'optionId': self.option_def_id.x_uuid if self.option_def_id else '',
            'optionCode': self.option_def_id.code if self.option_def_id else '',
            'optionLabel': self.name or '',
            'quantity': self.quantity or 0,
            'unitPrice': self.unit_price or 0.0,
            'amount': self.amount or 0.0
        }
