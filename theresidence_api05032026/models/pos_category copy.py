# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api


class PosCategory(models.Model):
    _inherit = 'pos.category'

    x_tr_uuid = fields.Char(string='UUID', readonly=True, copy=False, default=lambda self: str(uuid.uuid4()))
    x_tr_menu_kind_id = fields.Many2one('theresidence.menu.kind', string='Type de menu')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())
        return super().create(vals_list)

    # def to_category_api_dict(self):
    #     self.ensure_one()
    #     base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
    #     image_url = f"{base_url}/web/image/pos.category/{self.id}/image_128" if self.image_128 else ''
        
    #     return {
    #         'id': self.x_tr_uuid or str(self.id),
    #         'kindId': self.x_tr_menu_kind_id.x_uuid if self.x_tr_menu_kind_id else '',
    #         'kindName': self.x_tr_menu_kind_id.name if self.x_tr_menu_kind_id else '',
    #         'name': self.name or '',
    #         'imageUrl': image_url,
    #         'sortOrder': self.sequence or 0
    #     }
    def to_category_api_dict(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        image_url = (
            f"{base_url}/web/image/pos.category/{self.id}/image_128"
            if self.image_128 else ''
        )

        # 🔥 Trouver la catégorie racine
        root = self
        while root.parent_id:
            root = root.parent_id

        return {
            'id': self.x_tr_uuid or str(self.id),

            # ✅ si racine → elle-même
            'kindId': root.x_tr_uuid or str(root.id),
            'kindName': root.name or '',

            'name': self.name or '',
            'imageUrl': image_url,
            'sortOrder': self.sequence or 0
        }