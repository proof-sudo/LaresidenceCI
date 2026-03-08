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

    x_tr_appointment_resource_id = fields.Many2one(
        'appointment.resource',
        string='Ressource Appointment',
        copy=False,
        help="appointment.resource lié à cet espace (créé automatiquement).",
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
        if vals.get('x_tr_is_space'):
            for rec in self:
                if not rec.x_tr_appointment_type_id:
                    rec._ensure_appointment_type()
        if 'name' in vals:
            for rec in self:
                if rec.x_tr_appointment_type_id:
                    rec.x_tr_appointment_type_id.sudo().write({'name': rec.name})
                if rec.x_tr_appointment_resource_id:
                    rec.x_tr_appointment_resource_id.sudo().write({'name': rec.name})
        return res

    def _ensure_appointment_type(self):
        """Crée (ou retrouve) un appointment.type pour cet espace."""
        self.ensure_one()

        existing = self.env['appointment.type'].search(
            [('name', '=', self.name)], limit=1
        )
        if existing:
            self.x_tr_appointment_type_id = existing
            self._link_apt_type_to_pos(existing)
            # appointment.resource créé séparément (évite le conflit public user)
            self._try_ensure_appointment_resource()
            return existing

        create_vals = {'name': self.name}

        apt_fields = self.env['appointment.type']._fields

        # Catégorie : 'custom' pour éviter le filtre "réserver une table" du POS.
        if 'category' in apt_fields:
            create_vals['category'] = 'custom'

        # staff_user_ids DOIT contenir au moins un utilisateur valide.
        # Odoo crée automatiquement des appointment.booking.line lors de la création
        # d'un calendar.event lié à ce type. La contrainte
        # _check_user_or_resource_match_appointment_type exige que le staff_user
        # soit dans cette liste — sinon la création du calendar.event échoue avec
        # "Public user cannot be used for X".
        # → On ajoute l'utilisateur admin comme staff par défaut.
        if 'staff_user_ids' in apt_fields:
            admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
            if admin_user:
                create_vals['staff_user_ids'] = [(4, admin_user.id)]

        # Capacité max = capacité de l'espace si disponible
        if 'max_capacity' in apt_fields and getattr(self, 'x_tr_space_capacity', 0):
            create_vals['max_capacity'] = self.x_tr_space_capacity

        apt_type = self.env['appointment.type'].sudo().create(create_vals)
        self.x_tr_appointment_type_id = apt_type
        self._link_apt_type_to_pos(apt_type)
        # appointment.resource créé séparément (évite le conflit public user)
        self._try_ensure_appointment_resource()

        _logger.info(
            "[TR BRIDGE] appointment.type '%s' (ID %s) créé pour l'espace ID %s",
            apt_type.name, apt_type.id, self.id
        )
        return apt_type

    def _try_ensure_appointment_resource(self):
        """Wrapper sécurisé : ne bloque jamais même si appointment.resource échoue."""
        try:
            self._ensure_appointment_resource()
        except Exception as e:
            _logger.warning(
                "[TR BRIDGE] Impossible de créer appointment.resource pour '%s' : %s",
                self.name, str(e)
            )

    def _ensure_appointment_resource(self):
        """Crée (ou retrouve) un appointment.resource pour cet espace et le lie à l'appointment.type."""
        self.ensure_one()

        if 'appointment.resource' not in self.env:
            return False

        if self.x_tr_appointment_resource_id:
            return self.x_tr_appointment_resource_id

        existing = self.env['appointment.resource'].search(
            [('name', '=', self.name)], limit=1
        )
        if existing:
            self.x_tr_appointment_resource_id = existing
            self._link_resource_to_apt_type(existing)
            return existing

        res_vals = {'name': self.name}
        res_fields = self.env['appointment.resource']._fields
        if 'capacity' in res_fields and getattr(self, 'x_tr_space_capacity', 0):
            res_vals['capacity'] = self.x_tr_space_capacity

        apt_resource = self.env['appointment.resource'].sudo().create(res_vals)
        self.x_tr_appointment_resource_id = apt_resource
        self._link_resource_to_apt_type(apt_resource)

        _logger.info(
            "[TR BRIDGE] appointment.resource '%s' (ID %s) créé pour l'espace ID %s",
            apt_resource.name, apt_resource.id, self.id
        )
        return apt_resource

    def _link_resource_to_apt_type(self, apt_resource):
        """Lie l'appointment.resource à l'appointment.type de cet espace."""
        self.ensure_one()
        apt_type = self.x_tr_appointment_type_id
        if not apt_type:
            return

        apt_fields = self.env['appointment.type']._fields
        res_field = next(
            (f for f in ['resource_ids', 'appointment_resource_ids'] if f in apt_fields),
            None,
        )
        if res_field:
            apt_type.sudo().write({res_field: [(4, apt_resource.id)]})
            _logger.info("[TR BRIDGE] appointment.resource lié à appointment.type '%s'", apt_type.name)

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
