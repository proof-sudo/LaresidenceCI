# -*- coding: utf-8 -*-

from odoo import models, fields


class EventEvent(models.Model):
    _inherit = 'event.event'

    x_tr_external_id = fields.Char(
        string='ID Externe TR',
        index=True,
        copy=False,
        help="UUID de l'événement dans le backend The Residence.",
    )

    def to_sync_dict(self):
        """Représentation JSON retournée après création/mise à jour."""
        self.ensure_one()
        return {
            'odooId': self.id,
            'externalId': self.x_tr_external_id or '',
            'name': self.name or '',
            'dateBegin': self.date_begin.strftime('%Y-%m-%dT%H:%M:%SZ') if self.date_begin else '',
            'dateEnd': self.date_end.strftime('%Y-%m-%dT%H:%M:%SZ') if self.date_end else '',
            'capacity': self.seats_max or 0,
            'state': self.stage_id.name if self.stage_id else '',
            'active': self.active,
        }
