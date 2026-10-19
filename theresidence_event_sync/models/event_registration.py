# -*- coding: utf-8 -*-

from odoo import models, fields


class EventRegistration(models.Model):
    _inherit = 'event.registration'

    x_tr_external_id = fields.Char(
        string='ID Externe TR',
        index=True,
        copy=False,
        help="UUID de l'inscription ou de l'invité dans le backend The Residence.",
    )
    x_tr_member_uuid = fields.Char(
        string='UUID Membre TR',
        copy=False,
        help="UUID du membre The Residence lié à cette inscription.",
    )
    x_tr_guests_count = fields.Integer(
        string='Nb invités déclarés',
        default=0,
        help="Nombre d'invités déclarés par le membre lors de l'inscription (hors attendees nominatifs).",
    )
    # Lien parent pour les invités nominatifs (EventAttendee)
    x_tr_is_attendee = fields.Boolean(
        string='Est un invité',
        default=False,
        help="True si cette registration représente un invité (EventAttendee) et non un membre inscrit.",
    )
    x_tr_parent_registration_id = fields.Many2one(
        'event.registration',
        string='Inscription parente',
        ondelete='cascade',
        copy=False,
        help="Inscription du membre qui a ajouté cet invité.",
    )
    x_tr_attendee_ids = fields.One2many(
        'event.registration',
        'x_tr_parent_registration_id',
        string='Invités nominatifs',
    )

    def to_sync_dict(self):
        """Représentation JSON retournée après création/mise à jour."""
        self.ensure_one()
        return {
            'odooId': self.id,
            'externalId': self.x_tr_external_id or '',
            'eventOdooId': self.event_id.id if self.event_id else None,
            'eventExternalId': self.event_id.x_tr_external_id or '',
            'partnerOdooId': self.partner_id.id if self.partner_id else None,
            'memberUuid': self.x_tr_member_uuid or '',
            'name': self.name or '',
            'email': self.email or '',
            'phone': self.phone or '',
            'guestsCount': self.x_tr_guests_count or 0,
            'state': self.state or '',
            'isAttendee': self.x_tr_is_attendee,
            'parentRegistrationOdooId': self.x_tr_parent_registration_id.id if self.x_tr_parent_registration_id else None,
            'attendees': [a.to_sync_dict() for a in self.x_tr_attendee_ids],
        }
