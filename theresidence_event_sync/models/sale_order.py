# -*- coding: utf-8 -*-
import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_tr_event_id = fields.Many2one(
        'event.event',
        string='Événement Odoo',
        copy=False,
        ondelete='set null',
        help="Événement Odoo généré automatiquement lors de la confirmation de réservation.",
    )

    def action_reserve_reservation(self):
        super().action_reserve_reservation()
        for order in self:
            if order.x_tr_is_reservation:
                try:
                    order._create_odoo_event_if_needed()
                except Exception:
                    _logger.exception(
                        "[TR EVENT SYNC] Échec création event.event pour %s",
                        order.x_tr_uuid,
                    )

    def write(self, vals):
        res = super().write(vals)
        if vals.get('x_tr_reservation_status') == 'RESERVED':
            for order in self:
                if order.x_tr_is_reservation:
                    try:
                        order._create_odoo_event_if_needed()
                    except Exception:
                        _logger.exception(
                            "[TR EVENT SYNC] Échec création event.event (write) pour %s",
                            order.x_tr_uuid,
                        )
        return res

    def _create_odoo_event_if_needed(self):
        """Crée l'événement Odoo lié à la réservation si aucun n'existe encore."""
        self.ensure_one()

        # Vérification via x_tr_external_id = UUID de la réservation
        existing = self.env['event.event'].search(
            [('x_tr_external_id', '=', self.x_tr_uuid)], limit=1
        )
        if existing:
            _logger.info(
                '[TR EVENT SYNC] Événement déjà existant pour la réservation %s (event.id=%s)',
                self.x_tr_uuid, existing.id,
            )
            if not self.x_tr_event_id:
                self.x_tr_event_id = existing
            return

        space_name = self.x_tr_space_id.name if self.x_tr_space_id else 'Espace'
        date_str = (
            self.x_tr_start_time.strftime('%d/%m/%Y %H:%M')
            if self.x_tr_start_time else ''
        )
        event_name = f"{space_name} – {date_str}" if date_str else space_name

        event = self.env['event.event'].sudo().create({
            'name': event_name,
            'date_begin': self.x_tr_start_time,
            'date_end': self.x_tr_end_time,
            'date_tz': 'Africa/Abidjan',
            'seats_limited': bool(self.x_tr_guest_count),
            'seats_max': self.x_tr_guest_count or 0,
            'x_tr_external_id': self.x_tr_uuid,
            'organizer_id': self.partner_id.id if self.partner_id else False,
            'user_id': self.user_id.id if self.user_id else False,
            'company_id': self.company_id.id if self.company_id else False,
        })
        self.x_tr_event_id = event
        _logger.info(
            '[TR EVENT SYNC] Événement créé : id=%s name="%s" pour la réservation %s',
            event.id, event.name, self.x_tr_uuid,
        )

    def action_cancel_reservation(self):
        super().action_cancel_reservation()
        for order in self:
            if order.x_tr_is_reservation and order.x_tr_event_id:
                order.x_tr_event_id.sudo().write({'active': False})
                _logger.info(
                    '[TR EVENT SYNC] Événement archivé (annulation réservation %s, event.id=%s)',
                    order.x_tr_uuid, order.x_tr_event_id.id,
                )

    def action_view_tr_event(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'event.event',
            'res_id': self.x_tr_event_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
