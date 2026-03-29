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
    # Ciblage audience : types d'adhésion autorisés (vide = ouvert à tous)
    x_tr_audience_ids = fields.Many2many(
        'product.template',
        'event_tr_audience_rel',
        'event_id',
        'product_id',
        string='Audience (types membres)',
        domain=[('x_tr_is_subscription_plan', '=', True)],
        help="Laisser vide = ouvert à tous les membres. Sinon restreint aux types listés.",
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
            'seatsAvailable': self.seats_available if self.seats_availability == 'limited' else None,
            'active': self.active,
            'audience': [
                {'odooId': p.id, 'name': p.name, 'uuid': p.x_tr_space_uuid or ''}
                for p in self.x_tr_audience_ids
            ],
        }
