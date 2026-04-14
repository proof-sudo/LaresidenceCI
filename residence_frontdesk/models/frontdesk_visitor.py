# -*- coding: utf-8 -*-
from odoo import models, fields, api


class FrontdeskVisitor(models.Model):
    _inherit = 'frontdesk.visitor'

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        ondelete='restrict',
        index=True,
        help="Sélectionnez un contact existant ou créez-en un nouveau. "
             "Le nom, le téléphone, l'email et la société seront automatiquement remplis.",
    )

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Auto-remplissage des champs visiteur depuis le contact sélectionné."""
        if not self.partner_id:
            return
        self.name = self.partner_id.name
        self.phone = self.partner_id.phone or self.partner_id.mobile or False
        self.email = self.partner_id.email or False
        # Société : nom de la société parente si contact individuel, sinon nom du partner lui-même
        if self.partner_id.parent_id:
            self.company = self.partner_id.parent_id.name
        elif self.partner_id.is_company:
            self.company = self.partner_id.name
        else:
            self.company = self.partner_id.company_name or False
