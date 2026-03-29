# -*- coding: utf-8 -*-

from odoo import models, fields


class EventRegistration(models.Model):
    _inherit = 'event.registration'

    x_tr_external_id = fields.Char(
        string='ID Externe TR',
        index=True,
        copy=False,
        help="UUID de l'inscription dans le backend The Residence.",
    )
    x_tr_member_uuid = fields.Char(
        string='UUID Membre TR',
        copy=False,
        help="UUID du membre The Residence lié à cette inscription.",
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
            'phone': self.mobile or '',
            'state': self.state or '',
        }
