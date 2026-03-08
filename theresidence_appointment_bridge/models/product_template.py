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
            self._link_apt_type_to_pos(existing)
            return existing

        apt_type = self.env['appointment.type'].sudo().create({'name': self.name})
        self.x_tr_appointment_type_id = apt_type
        self._link_apt_type_to_pos(apt_type)
        _logger.info(
            "[TR BRIDGE] appointment.type '%s' (ID %s) créé pour l'espace ID %s",
            apt_type.name, apt_type.id, self.id
        )
        return apt_type

    def _link_apt_type_to_pos(self, apt_type):
        """
        Lie le appointment.type à toutes les configs POS actives.
        La relation peut être portée par pos.config ou appointment.type selon la version.
        On essaie les deux sens, on log si aucun ne fonctionne.
        """
        pos_configs = self.env['pos.config'].sudo().search([('active', '=', True)])
        if not pos_configs:
            return

        # Tentative 1 : relation depuis pos.config (Odoo 17+)
        pos_apt_field = next(
            (f for f in ['appointment_type_ids', 'appointment_ids'] if f in self.env['pos.config']._fields),
            None
        )
        if pos_apt_field:
            pos_configs.sudo().write({pos_apt_field: [(4, apt_type.id)]})
            _logger.info("[TR BRIDGE] Lien POS via pos.config.%s OK", pos_apt_field)
            return

        # Tentative 2 : relation depuis appointment.type
        apt_pos_field = next(
            (f for f in ['pos_config_ids', 'pos_config_id'] if f in self.env['appointment.type']._fields),
            None
        )
        if apt_pos_field:
            apt_type.sudo().write({apt_pos_field: [(6, 0, pos_configs.ids)]})
            _logger.info("[TR BRIDGE] Lien POS via appointment.type.%s OK", apt_pos_field)
            return

        _logger.warning(
            "[TR BRIDGE] Impossible de lier '%s' au POS automatiquement — "
            "faites-le manuellement dans POS > Configuration > Types de RDV",
            apt_type.name
        )
