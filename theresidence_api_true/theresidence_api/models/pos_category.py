# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api


class PosCategory(models.Model):
    _inherit = 'pos.category'

    x_tr_uuid = fields.Char(
        string='UUID',
        readonly=True,
        copy=False,
        default=lambda self: str(uuid.uuid4())
    )

    x_tr_menu_kind_id = fields.Many2one(
        'theresidence.menu.kind',
        string='Type de menu'
    )

    # =========================================================
    # SAFE WEBHOOK ACCESSOR
    # =========================================================

    def _get_webhook_service(self):
        """
        Récupère le service webhook de manière SAFE.
        Évite tout crash si module non chargé.
        """
        service = self.env.get('theresidence.webhook.service')
        if not service:
            return None

        service = service.sudo()

        # sécurisation des méthodes
        if not hasattr(service, 'is_event_enabled'):
            return None
        if not hasattr(service, 'trigger_event'):
            return None

        return service

    # =========================================================
    # REGISTER HOOK (SYNC INITIALE SAFE)
    # =========================================================

    def _register_hook(self):
        """
        Synchronisation initiale des catégories POS au démarrage.
        SAFE : ne crash jamais si webhook indisponible.
        """
        super()._register_hook()

        webhook_service = self._get_webhook_service()
        if not webhook_service:
            return

        if not webhook_service.is_event_enabled('POS_CATEGORY_CREATED'):
            return

        categories = self.search([])

        for category in categories:
            # garantir UUID
            if not category.x_tr_uuid:
                category.with_context(skip_webhook=True).write({
                    'x_tr_uuid': str(uuid.uuid4())
                })

            try:
                webhook_service.trigger_event(
                    internal_event='POS_CATEGORY_CREATED',
                    entity_type='pos_category',
                    entity_id=category.x_tr_uuid,
                    data=category.to_category_api_dict(),
                )
            except Exception:
                # ne jamais casser le boot Odoo
                pass

    # =========================================================
    # CREATE
    # =========================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())

        records = super().create(vals_list)

        if self.env.context.get('skip_webhook'):
            return records

        webhook_service = self._get_webhook_service()
        if not webhook_service:
            return records

        if webhook_service.is_event_enabled('POS_CATEGORY_CREATED'):
            for record in records:
                try:
                    webhook_service.trigger_event(
                        internal_event='POS_CATEGORY_CREATED',
                        entity_type='pos_category',
                        entity_id=record.x_tr_uuid,
                        data=record.to_category_api_dict(),
                    )
                except Exception:
                    pass

        return records

    # =========================================================
    # WRITE
    # =========================================================

    def write(self, vals):

        if self.env.context.get('skip_webhook'):
            return super().write(vals)

        old_values = {}
        for record in self:
            old_values[record.id] = {
                'name': record.name,
                'parent_id': record.parent_id.id if record.parent_id else None,
                'sequence': record.sequence,
            }

        result = super().write(vals)

        webhook_service = self._get_webhook_service()
        if not webhook_service:
            return result

        if webhook_service.is_event_enabled('POS_CATEGORY_UPDATED'):
            for record in self:
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

                if not changed_fields:
                    continue

                try:
                    webhook_service.trigger_event(
                        internal_event='POS_CATEGORY_UPDATED',
                        entity_type='pos_category',
                        entity_id=record.x_tr_uuid,
                        data={
                            **record.to_category_api_dict(),
                            'changedFields': changed_fields
                        },
                    )
                except Exception:
                    pass

        return result

    # =========================================================
    # DELETE
    # =========================================================

    def unlink(self):

        if self.env.context.get('skip_webhook'):
            return super().unlink()

        webhook_service = self._get_webhook_service()
        send_webhook = webhook_service and webhook_service.is_event_enabled('POS_CATEGORY_DELETED')

        category_data = []
        if send_webhook:
            for record in self:
                category_data.append({
                    'uuid': record.x_tr_uuid,
                    'name': record.name,
                })

        result = super().unlink()

        if send_webhook:
            for data in category_data:
                try:
                    webhook_service.trigger_event(
                        internal_event='POS_CATEGORY_DELETED',
                        entity_type='pos_category',
                        entity_id=data['uuid'],
                        data={'id': data['uuid'], 'name': data['name']},
                    )
                except Exception:
                    pass

        return result

    # =========================================================
    # API MAPPING
    # =========================================================

    def to_category_api_dict(self):
        self.ensure_one()

        # force cohérence ORM
        self.flush_recordset(['name', 'parent_id', 'sequence', 'image_128', 'active'])
        self.invalidate_recordset()

        if not self.active:
            return None

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        image_url = (
            f"{base_url}/web/image/pos.category/{self.id}/image_128"
            if self.image_128 else ''
        )

        # sécurisation racine
        root = self
        visited = set()

        while root.parent_id and root.id not in visited:
            visited.add(root.id)
            root = root.parent_id.sudo()

        return {
            'id': self.x_tr_uuid or str(self.id),
            'parentId': self.parent_id.x_tr_uuid if self.parent_id else None,
            'kindId': root.x_tr_uuid or str(root.id),
            'kindName': root.name or '',
            'name': self.name or '',
            'imageUrl': image_url,
            'sortOrder': self.sequence or 0
        }
