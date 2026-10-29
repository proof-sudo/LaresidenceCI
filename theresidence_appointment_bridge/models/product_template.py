# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

# Nom de secours si aucun type catégorie 'table' n'existe.
_TR_SHARED_APT_TYPE_NAME = "Réservation de table"


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_tr_appointment_type_id = fields.Many2one(
        'appointment.type',
        string='Type de RDV (Appointment)',
        copy=False,
        help="Lien vers le appointment.type Odoo partagé par tous les espaces TR.",
    )

    # ─────────────────────────────────────────────────────────────
    # Création : si l'espace est marqué x_tr_is_space, on attache
    # le type RDV partagé.
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
        # Le type RDV est partagé : on ne renomme plus quand l'espace est renommé.
        return res

    def _ensure_appointment_type(self):
        """
        Retrouve ou crée le appointment.type PARTAGÉ par tous les espaces TR.
        Catégorie 'table' → visible dans le menu natif POS Appointments.
        """
        self.ensure_one()

        apt_fields = self.env['appointment.type']._fields

        # Vérifie si 'table' est une valeur valide pour category dans cette version
        _has_table_category = (
            'category' in apt_fields
            and 'table' in dict(apt_fields['category'].selection or [])
        )

        # 1. Priorité : type catégorie 'table' existant (pos_restaurant_appointment)
        #    C'est le "Réserver une table" natif Odoo, visible dans le menu POS.
        shared = False
        if _has_table_category:
            shared = self.env['appointment.type'].search(
                [('category', '=', 'table')], limit=1
            )

        # 2. Sinon, chercher par nom de secours
        if not shared:
            shared = self.env['appointment.type'].search(
                [('name', '=', _TR_SHARED_APT_TYPE_NAME)], limit=1
            )

        # 3. Créer si introuvable
        if not shared:
            create_vals = {'name': _TR_SHARED_APT_TYPE_NAME}

            if _has_table_category:
                create_vals['category'] = 'table'

            if 'staff_user_ids' in apt_fields:
                admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
                if admin_user:
                    create_vals['staff_user_ids'] = [(4, admin_user.id)]

            shared = self.env['appointment.type'].sudo().create(create_vals)
            _logger.info(
                "[TR BRIDGE] appointment.type partagé '%s' (ID %s) créé",
                shared.name, shared.id,
            )

        self.x_tr_appointment_type_id = shared
        self._link_apt_type_to_pos(shared)

        _logger.info(
            "[TR BRIDGE] Espace '%s' (ID %s) lié au type RDV partagé '%s' (ID %s)",
            self.name, self.id, shared.name, shared.id,
        )
        return shared

    def _link_apt_type_to_pos(self, apt_type):
        """
        Lie le appointment.type à toutes les configs POS actives.
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
            "[TR BRIDGE] Impossible de lier '%s' au POS — "
            "faites-le manuellement dans POS > Configuration > Types de RDV",
            apt_type.name
        )
