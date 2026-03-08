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
                # sudo() obligatoire : le contexte API (auth='public') garde l'env
                # public user même quand create_reservation_from_api est appelé en sudo.
                # appointment.type et appointment.resource refusent le public user.
                try:
                    rec.sudo()._sync_create_calendar_event()
                except Exception:
                    _logger.exception(
                        "[TR BRIDGE] Échec création calendar.event pour réservation %s",
                        rec.x_tr_uuid,
                    )
                try:
                    rec.sudo()._notify_pos_new_reservation()
                except Exception:
                    _logger.exception("[TR BRIDGE] Échec notification bus pour %s", rec.x_tr_uuid)
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
                try:
                    if rec.x_tr_calendar_event_id:
                        rec.sudo()._sync_update_calendar_event()
                    elif rec.x_tr_start_time and rec.x_tr_end_time:
                        rec.sudo()._sync_create_calendar_event()
                except Exception as e:
                    _logger.warning(
                        "[TR BRIDGE] Échec sync calendar.event pour %s : %s",
                        rec.x_tr_uuid, str(e)
                    )
        return res

    # ─────────────────────────────────────────────────────────────
    # Override tri : plus récent en premier (pour ReservationPanel POS)
    # ─────────────────────────────────────────────────────────────
    @api.model
    def get_pos_reservations(self, date_filter='today'):
        result = super().get_pos_reservations(date_filter)
        # Tri newest-first par createdAt (ISO string, lexicographique)
        return sorted(result, key=lambda r: r.get('createdAt', ''), reverse=True)

    # ─────────────────────────────────────────────────────────────
    # Notification bus → POS (toast + son côté caissière)
    # ─────────────────────────────────────────────────────────────
    def _notify_pos_new_reservation(self):
        self.ensure_one()
        try:
            # On envoie sur le canal partenaire de chaque utilisateur interne.
            # Ce canal est automatiquement souscrit par le bus_service Odoo (POS inclus),
            # ce qui garantit la réception sans avoir besoin d'addChannel côté JS.
            internal_users = self.env['res.users'].sudo().search([
                ('share', '=', False),
                ('active', '=', True),
            ])
            msg = {
                'member': self.partner_id.name or '',
                'space': self.x_tr_space_id.name or '',
                'start': self.x_tr_start_time.strftime('%H:%M') if self.x_tr_start_time else '',
                'uuid': self.x_tr_uuid or '',
                'status': self.x_tr_reservation_status or 'PENDING',
            }
            for user in internal_users:
                self.env['bus.bus']._sendone(user.partner_id, 'tr_new_reservation', msg)
            _logger.info(
                "[TR BRIDGE] Notification bus envoyée à %s utilisateur(s) pour réservation %s",
                len(internal_users), self.x_tr_uuid,
            )
        except Exception as e:
            _logger.warning("[TR BRIDGE] Échec notification bus : %s", str(e))

    # ─────────────────────────────────────────────────────────────
    # Création du calendar.event miroir
    # ─────────────────────────────────────────────────────────────
    def _sync_create_calendar_event(self):
        self.ensure_one()

        apt_type = self.x_tr_space_id.x_tr_appointment_type_id if self.x_tr_space_id else False

        if self.x_tr_space_id and not apt_type:
            try:
                apt_type = self.x_tr_space_id.sudo()._ensure_appointment_type()
            except Exception:
                _logger.exception(
                    "[TR BRIDGE] Impossible de créer appointment.type pour l'espace '%s'",
                    self.x_tr_space_id.name,
                )
                # On continue sans appointment_type_id — le calendar.event sera créé quand même

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

        # waiting_list_capacity : capacité ou nb invités selon le champ disponible
        if self.x_tr_guest_count:
            ce_fields = self.env['calendar.event']._fields
            if 'waiting_list_capacity' in ce_fields:
                event_vals['waiting_list_capacity'] = self.x_tr_guest_count

        event = self.env['calendar.event'].sudo().create(event_vals)
        self.sudo().write({'x_tr_calendar_event_id': event.id})

        # Si waiting_list_capacity est sur appointment.type plutôt que calendar.event
        if apt_type and self.x_tr_guest_count:
            apt_fields = self.env['appointment.type']._fields
            if 'waiting_list_capacity' in apt_fields:
                apt_type.sudo().write({'waiting_list_capacity': self.x_tr_guest_count})

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

        update_vals = {
            'name': self._build_event_name(),
            'start': self.x_tr_start_time,
            'stop': self.x_tr_end_time,
            'show_as': STATUS_TO_SHOW.get(self.x_tr_reservation_status, 'free'),
            'active': STATUS_TO_ACTIVE.get(self.x_tr_reservation_status, True),
            'description': self._build_event_description(),
        }

        if self.x_tr_guest_count:
            ce_fields = self.env['calendar.event']._fields
            if 'waiting_list_capacity' in ce_fields:
                update_vals['waiting_list_capacity'] = self.x_tr_guest_count

        event.sudo().write(update_vals)

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
        return f"{space} — {member}"

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
