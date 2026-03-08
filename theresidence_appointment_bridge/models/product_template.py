# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_tr_appointment_type_id = fields.Many2one(
        'appointment.type',
        string='Type de RDV (Appointment)',
        copy=False,
        help="Lien vers le appointment.type Odoo généré automatiquement pour cet espace.",
    )

    # ─────────────────────────────────────────────────────────────
    # Création : si l'espace est marqué x_tr_is_space, on génère
    # automatiquement un appointment.type correspondant.
    # ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.x_tr_is_space and not rec.x_tr_appointment_type_id:
                rec._ensure_appointment_type()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Si on vient de cocher "Est un espace TR", on crée le type
        if vals.get('x_tr_is_space'):
            for rec in self:
                if not rec.x_tr_appointment_type_id:
                    rec._ensure_appointment_type()
        # Si le nom de l'espace change, on met à jour le appointment.type
        if 'name' in vals:
            for rec in self:
                if rec.x_tr_appointment_type_id:
                    rec.x_tr_appointment_type_id.sudo().write({'name': rec.name})
        return res

    def _ensure_appointment_type(self):
        """Crée (ou retrouve) un appointment.type pour cet espace."""
        self.ensure_one()

        # Cherche un type existant portant le même nom pour éviter les doublons
        existing = self.env['appointment.type'].search(
            [('name', '=', self.name)], limit=1
        )
        if existing:
            self.x_tr_appointment_type_id = existing
            return existing

        apt_type = self.env['appointment.type'].sudo().create({
            'name': self.name,
            'appointment_duration': 60,       # durée par défaut 1h
            'min_schedule_hours': 0,
            'max_schedule_days': 90,
            'schedule_based_on': 'users',
            'assign_method': 'resource_time',
        })
        self.x_tr_appointment_type_id = apt_type
        _logger.info(
            "[TR BRIDGE] appointment.type créé : '%s' (ID %s) pour l'espace ID %s",
            apt_type.name, apt_type.id, self.id
        )
        return apt_type
