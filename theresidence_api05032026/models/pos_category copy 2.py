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
        
        records = super().create(vals_list)
        
        # WEBHOOK: Création de catégorie POS
        for record in records:
            if record.x_tr_uuid:
                self.env['theresidence.webhook.service'].trigger_event(
                    internal_event='POS_CATEGORY_CREATED',
                    entity_type='pos_category',
                    entity_id=record.x_tr_uuid,
                    data=record.to_category_api_dict(),
                )
        
        return records

    def write(self, vals):
        # Capturer les anciennes valeurs
        old_values = {}
        for record in self:
            if record.x_tr_uuid:
                old_values[record.id] = {
                    'name': record.name,
                    'parent_id': record.parent_id.id if record.parent_id else None,
                    'sequence': record.sequence,
                }
        
        result = super().write(vals)
        
        # WEBHOOK: Modification de catégorie POS
        for record in self:
            if record.x_tr_uuid:
                old_val = old_values.get(record.id, {})
                
                changed_fields = []
                if 'name' in vals and old_val.get('name') != record.name:
                    changed_fields.append('name')
                if 'parent_id' in vals:
                    changed_fields.append('parent')
                if 'sequence' in vals and old_val.get('sequence') != record.sequence:
                    changed_fields.append('sequence')
                if 'image_128' in vals or 'image_1920' in vals:
                    changed_fields.append('image')
                
                if changed_fields:
                    self.env['theresidence.webhook.service'].trigger_event(
                        internal_event='POS_CATEGORY_UPDATED',
                        entity_type='pos_category',
                        entity_id=record.x_tr_uuid,
                        data={**record.to_category_api_dict(), 'changedFields': changed_fields},
                    )
        
        return result

    def unlink(self):
        # Capturer les infos avant suppression
        category_data = []
        for record in self:
            if record.x_tr_uuid:
                category_data.append({
                    'uuid': record.x_tr_uuid,
                    'name': record.name,
                })
        
        result = super().unlink()
        
        # WEBHOOK: Suppression de catégorie POS
        for data in category_data:
            self.env['theresidence.webhook.service'].trigger_event(
                internal_event='POS_CATEGORY_DELETED',
                entity_type='pos_category',
                entity_id=data['uuid'],
                data={'id': data['uuid'], 'name': data['name']},
            )
        
        return result

    def to_category_api_dict(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        image_url = (
            f"{base_url}/web/image/pos.category/{self.id}/image_128"
            if self.image_128 else ''
        )

        # Trouver la catégorie racine
        root = self
        while root.parent_id:
            root = root.parent_id

        return {
            'id': self.x_tr_uuid or str(self.id),
            # si racine → elle-même
            'kindId': root.x_tr_uuid or str(root.id),
            'kindName': root.name or '',
            'name': self.name or '',
            'imageUrl': image_url,
            'sortOrder': self.sequence or 0
        }