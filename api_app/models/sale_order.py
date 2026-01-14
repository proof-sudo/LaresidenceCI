# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ==========================================
    # Champs The Residence
    # ==========================================
    residence_external_id = fields.Char(
        string='ID Externe (UUID)',
        index=True,
        copy=False,
        help='UUID pour synchronisation avec l\'app mobile'
    )

    is_residence_reservation = fields.Boolean(
        string='Est une Réservation Salle',
        compute='_compute_is_residence_reservation',
        store=True
    )

    residence_reservation_status = fields.Selection([
        ('pending', 'En attente'),
        ('approved', 'Approuvée'),
        ('rejected', 'Rejetée'),
        ('checked_in', 'Check-in'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée')
    ], string='Statut Réservation', default='pending')

    residence_space_id = fields.Many2one(
        'product.template',
        string='Salle Réservée',
        domain=[('is_residence_space', '=', True)],
        compute='_compute_residence_space',
        store=True
    )

    residence_start_time = fields.Datetime(
        string='Début',
        compute='_compute_residence_times',
        store=True
    )

    residence_end_time = fields.Datetime(
        string='Fin',
        compute='_compute_residence_times',
        store=True
    )

    residence_guest_count = fields.Integer(
        string='Nombre d\'invités',
        default=1
    )

    residence_notes = fields.Text(
        string='Notes de Réservation'
    )

    residence_rejection_reason = fields.Text(
        string='Motif de Rejet'
    )

    # Invités
    residence_invitee_ids = fields.One2many(
        'residence.reservation.invitee',
        'order_id',
        string='Invités'
    )

    # Lien vers calendar.event
    residence_calendar_event_id = fields.Many2one(
        'calendar.event',
        string='Événement Calendrier',
        readonly=True
    )

    @api.depends('is_rental_order')
    def _compute_is_residence_reservation(self):
        for order in self:
            order.is_residence_reservation = order.is_rental_order

    @api.depends('order_line.product_id')
    def _compute_residence_space(self):
        for order in self:
            space_line = order.order_line.filtered(
                lambda l: l.product_id.product_tmpl_id.is_residence_space
            )
            order.residence_space_id = space_line[0].product_id.product_tmpl_id.id if space_line else False

    @api.depends('order_line.start_date', 'order_line.return_date')
    def _compute_residence_times(self):
        for order in self:
            rental_lines = order.order_line.filtered(lambda l: l.is_rental)
            if rental_lines:
                order.residence_start_time = rental_lines[0].start_date
                order.residence_end_time = rental_lines[0].return_date
            else:
                order.residence_start_time = False
                order.residence_end_time = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('residence_external_id') and vals.get('is_rental_order'):
                vals['residence_external_id'] = str(uuid.uuid4())
        return super().create(vals_list)

    # ==========================================
    # Actions de statut réservation
    # ==========================================
    def action_approve_reservation(self):
        """Approuver la réservation"""
        for order in self:
            if order.residence_reservation_status != 'pending':
                raise UserError(_('Seules les réservations en attente peuvent être approuvées'))

            order.residence_reservation_status = 'approved'
            order._update_space_state('reserved')
            order._create_or_update_calendar_event()
            order._send_reservation_webhook('RESERVATION_STATUS_CHANGED', 'pending', 'approved')

    def action_reject_reservation(self, reason=None):
        """Rejeter la réservation"""
        for order in self:
            if order.residence_reservation_status != 'pending':
                raise UserError(_('Seules les réservations en attente peuvent être rejetées'))

            order.residence_reservation_status = 'rejected'
            if reason:
                order.residence_rejection_reason = reason
            order._update_space_state('available')
            order._send_reservation_webhook('RESERVATION_STATUS_CHANGED', 'pending', 'rejected')

    def action_checkin_reservation(self):
        """Check-in de la réservation"""
        for order in self:
            if order.residence_reservation_status != 'approved':
                raise UserError(_('Seules les réservations approuvées peuvent faire le check-in'))

            order.residence_reservation_status = 'checked_in'
            order._send_reservation_webhook('RESERVATION_STATUS_CHANGED', 'approved', 'checked_in')

    def action_complete_reservation(self):
        """Terminer la réservation"""
        for order in self:
            if order.residence_reservation_status not in ('approved', 'checked_in'):
                raise UserError(_('Cette réservation ne peut pas être terminée'))

            order.residence_reservation_status = 'completed'
            order._update_space_state('available')
            order._send_reservation_webhook('RESERVATION_STATUS_CHANGED', order.residence_reservation_status, 'completed')

    def action_cancel_reservation(self):
        """Annuler la réservation"""
        for order in self:
            prev_status = order.residence_reservation_status
            order.residence_reservation_status = 'cancelled'
            order._update_space_state('available')
            order._delete_calendar_event()
            order._send_reservation_webhook('RESERVATION_CANCELLED', prev_status, 'cancelled')

    # ==========================================
    # Méthodes utilitaires
    # ==========================================
    def _update_space_state(self, state):
        """Mettre à jour l'état de la salle"""
        self.ensure_one()
        if self.residence_space_id:
            self.residence_space_id.residence_space_state = state

    def _create_or_update_calendar_event(self):
        """Créer ou mettre à jour l'événement calendrier"""
        self.ensure_one()
        CalendarEvent = self.env['calendar.event']

        vals = {
            'name': f"Réservation: {self.residence_space_id.name if self.residence_space_id else ''} - {self.partner_id.name}",
            'start': self.residence_start_time,
            'stop': self.residence_end_time,
            'partner_ids': [(4, self.partner_id.id)],
            'description': self.residence_notes or '',
            'location': self.residence_space_id.residence_location_id.name if self.residence_space_id and self.residence_space_id.residence_location_id else '',
        }

        if self.residence_calendar_event_id:
            self.residence_calendar_event_id.write(vals)
        else:
            event = CalendarEvent.create(vals)
            self.residence_calendar_event_id = event.id

    def _delete_calendar_event(self):
        """Supprimer l'événement calendrier"""
        self.ensure_one()
        if self.residence_calendar_event_id:
            self.residence_calendar_event_id.unlink()
            self.residence_calendar_event_id = False

    def _send_reservation_webhook(self, event_type, prev_status, new_status):
        """Envoyer un webhook pour la réservation"""
        self.ensure_one()
        config = self.env['residence.config'].get_config()
        if config:
            config.send_webhook(
                event_type=event_type,
                entity_type='reservation',
                entity_id=self.residence_external_id,
                data=self.to_reservation_api_dict(),
                previous_status=prev_status.upper() if prev_status else None,
                new_status=new_status.upper() if new_status else None
            )

    # ==========================================
    # API Methods
    # ==========================================
    def to_reservation_api_dict(self):
        """Convertir en format API pour une réservation"""
        self.ensure_one()

        # Récupérer les options (équipements)
        options = []
        for line in self.order_line:
            if line.product_id.product_tmpl_id.id != self.residence_space_id.id:
                options.append({
                    'id': line.product_id.residence_external_id or str(line.id),
                    'name': line.product_id.name,
                    'quantity': line.product_uom_qty,
                    'unitPrice': line.price_unit,
                    'amount': line.price_subtotal
                })

        # Récupérer les invités
        invitees = []
        for invitee in self.residence_invitee_ids:
            invitees.append(invitee.to_api_dict())

        return {
            'id': self.residence_external_id,
            'orderReference': self.name,
            'memberId': self.partner_id.residence_external_id,
            'memberFirstName': self.partner_id.name.split()[0] if self.partner_id.name else '',
            'memberLastName': ' '.join(self.partner_id.name.split()[1:]) if self.partner_id.name else '',
            'memberEmail': self.partner_id.email or '',
            'spaceId': self.residence_space_id.residence_external_id if self.residence_space_id else None,
            'spaceName': self.residence_space_id.name if self.residence_space_id else '',
            'startTime': self.residence_start_time.isoformat() if self.residence_start_time else None,
            'endTime': self.residence_end_time.isoformat() if self.residence_end_time else None,
            'guestCount': self.residence_guest_count,
            'status': self.residence_reservation_status.upper() if self.residence_reservation_status else 'PENDING',
            'totalAmount': self.amount_total,
            'notes': self.residence_notes or '',
            'rejectionReason': self.residence_rejection_reason or '',
            'options': options,
            'invitees': invitees,
            'createdAt': self.create_date.isoformat() if self.create_date else None,
            'updatedAt': self.write_date.isoformat() if self.write_date else None
        }

    @api.model
    def get_by_external_id(self, external_id):
        """Trouver par ID externe"""
        return self.search([('residence_external_id', '=', external_id)], limit=1)

    @api.model
    def create_reservation_from_api(self, data):
        """Créer une réservation depuis les données API"""
        # Trouver le membre
        partner = self.env['res.partner'].get_by_external_id(data.get('memberId'))
        if not partner:
            raise ValidationError(_('Membre non trouvé: %s') % data.get('memberId'))

        # Trouver la salle
        space = self.env['product.template'].get_by_external_id(data.get('spaceId'))
        if not space:
            raise ValidationError(_('Salle non trouvée: %s') % data.get('spaceId'))

        # Vérifier que le produit est louable
        product = space.product_variant_id
        if not product.rent_ok:
            raise ValidationError(_('Ce produit n\'est pas disponible à la location'))

        # Préparer les lignes de commande
        order_lines = [(0, 0, {
            'product_id': product.id,
            'product_uom_qty': 1,
            'start_date': data.get('startTime'),
            'return_date': data.get('endTime'),
            'is_rental': True,
        })]

        # Ajouter les options/équipements
        for option_id in data.get('optionIds', []):
            equipment = self.env['residence.space.equipment'].get_by_external_id(option_id)
            if equipment and equipment.product_id:
                order_lines.append((0, 0, {
                    'product_id': equipment.product_id.id,
                    'product_uom_qty': 1,
                    'price_unit': equipment.price,
                }))

        # Créer la commande
        order = self.create({
            'partner_id': partner.id,
            'is_rental_order': True,
            'residence_external_id': data.get('id') or str(uuid.uuid4()),
            'residence_reservation_status': 'pending',
            'residence_guest_count': data.get('guestCount', 1),
            'residence_notes': data.get('notes'),
            'order_line': order_lines,
        })

        # Créer les invités
        for invitee_data in data.get('invitees', []):
            self.env['residence.reservation.invitee'].create({
                'order_id': order.id,
                'name': invitee_data.get('name'),
                'email': invitee_data.get('email'),
                'phone': invitee_data.get('phone'),
            })

        # Auto-confirmer si configuré
        config = self.env['residence.config'].get_config()
        if config and config.auto_confirm_reservation:
            order.action_approve_reservation()

        return order


class ResidenceReservationInvitee(models.Model):
    _name = 'residence.reservation.invitee'
    _description = 'Invité de Réservation'

    order_id = fields.Many2one(
        'sale.order',
        string='Réservation',
        required=True,
        ondelete='cascade'
    )

    external_id = fields.Char(
        string='ID Externe (UUID)',
        default=lambda self: str(uuid.uuid4()),
        readonly=True,
        copy=False
    )

    name = fields.Char(string='Nom', required=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Téléphone')

    def to_api_dict(self):
        """Convertir en format API"""
        self.ensure_one()
        return {
            'id': self.external_id,
            'name': self.name,
            'email': self.email or '',
            'phone': self.phone or ''
        }
