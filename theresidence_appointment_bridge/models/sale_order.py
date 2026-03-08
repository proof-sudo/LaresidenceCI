# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

# Mapping statuts TR → show_as du calendar.event
STATUS_TO_SHOW = {
    'PENDING':    'free',
    'APPROVED':   'busy',
    'CHECKED_IN': 'busy',
    'COMPLETED':  'free',
    'REJECTED':   'free',
    'CANCELLED':  'free',
}

# Mapping statuts TR → active du calendar.event
STATUS_TO_ACTIVE = {
    'PENDING':    True,
    'APPROVED':   True,
    'CHECKED_IN': True,
    'COMPLETED':  True,
    'REJECTED':   False,
    'CANCELLED':  False,
}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_tr_calendar_event_id = fields.Many2one(
        'calendar.event',
        string='Événement Agenda',
        copy=False,
        readonly=True,
        help="calendar.event miroir créé pour pos_appointment.",
    )

    # ─────────────────────────────────────────────────────────────
    # Création : on crée le calendar.event miroir si c'est une réservation
    # ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.x_tr_is_reservation and rec.x_tr_start_time and rec.x_tr_end_time:
                rec._sync_create_calendar_event()
        return records

    def write(self, vals):
        res = super().write(vals)

        sync_fields = {
            'x_tr_reservation_status',
            'x_tr_start_time',
            'x_tr_end_time',
            'x_tr_notes',
            'x_tr_guest_count',
        }
        if sync_fields & set(vals.keys()):
            for rec in self:
                if not rec.x_tr_is_reservation:
                    continue
                if rec.x_tr_calendar_event_id:
                    rec._sync_update_calendar_event()
                elif rec.x_tr_start_time and rec.x_tr_end_time:
                    # Création tardive si l'event n'existe pas encore
                    rec._sync_create_calendar_event()
        return res

    # ─────────────────────────────────────────────────────────────
    # Création du calendar.event miroir
    # ─────────────────────────────────────────────────────────────
    def _sync_create_calendar_event(self):
        self.ensure_one()

        apt_type = self.x_tr_space_id.x_tr_appointment_type_id if self.x_tr_space_id else False

        # S'il n'y a pas encore de type, on le crée à la volée
        if self.x_tr_space_id and not apt_type:
            apt_type = self.x_tr_space_id._ensure_appointment_type()

        partner_ids = [(4, self.partner_id.id)] if self.partner_id else []

        event_vals = {
            'name': self._build_event_name(),
            'start': self.x_tr_start_time,
            'stop': self.x_tr_end_time,
            'show_as': STATUS_TO_SHOW.get(self.x_tr_reservation_status, 'free'),
            'active': STATUS_TO_ACTIVE.get(self.x_tr_reservation_status, True),
            'partner_ids': partner_ids,
            'description': self._build_event_description(),
            'privacy': 'confidential',
        }
        if apt_type:
            event_vals['appointment_type_id'] = apt_type.id

        event = self.env['calendar.event'].sudo().create(event_vals)
        self.sudo().write({'x_tr_calendar_event_id': event.id})

        _logger.info(
            "[TR BRIDGE] calendar.event %s créé pour réservation %s (%s)",
            event.id, self.x_tr_uuid, self.name
        )

    # ─────────────────────────────────────────────────────────────
    # Mise à jour du calendar.event existant
    # ─────────────────────────────────────────────────────────────
    def _sync_update_calendar_event(self):
        self.ensure_one()
        event = self.x_tr_calendar_event_id
        if not event:
            return

        event.sudo().write({
            'name': self._build_event_name(),
            'start': self.x_tr_start_time,
            'stop': self.x_tr_end_time,
            'show_as': STATUS_TO_SHOW.get(self.x_tr_reservation_status, 'free'),
            'active': STATUS_TO_ACTIVE.get(self.x_tr_reservation_status, True),
            'description': self._build_event_description(),
        })

        _logger.info(
            "[TR BRIDGE] calendar.event %s mis à jour → statut %s",
            event.id, self.x_tr_reservation_status
        )

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────
    def _build_event_name(self):
        self.ensure_one()
        space = self.x_tr_space_id.name if self.x_tr_space_id else 'Espace'
        member = self.partner_id.name if self.partner_id else 'Membre'
        status_labels = {
            'PENDING':    'En attente',
            'APPROVED':   'Approuvée',
            'CHECKED_IN': 'Check-in',
            'COMPLETED':  'Terminée',
            'REJECTED':   'Rejetée',
            'CANCELLED':  'Annulée',
        }
        status = status_labels.get(self.x_tr_reservation_status, '')
        return f"[{status}] {space} — {member}"

    def _build_event_description(self):
        self.ensure_one()
        lines = []
        if self.x_tr_guest_count:
            lines.append(f"Invités : {self.x_tr_guest_count}")
        if self.x_tr_notes:
            lines.append(f"Notes : {self.x_tr_notes}")
        if self.x_tr_uuid:
            lines.append(f"UUID : {self.x_tr_uuid}")
        if self.x_tr_qr_token:
            lines.append(f"QR Token : {self.x_tr_qr_token}")
        return "\n".join(lines)
