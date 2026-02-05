# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api


class PosCategory(models.Model):
    _inherit = 'pos.category'

    x_tr_uuid = fields.Char(string='UUID', readonly=True, copy=False, default=lambda self: str(uuid.uuid4()))
    x_tr_menu_kind_id = fields.Many2one('theresidence.menu.kind', string='Type de menu')

    def _register_hook(self):
        """
        Appelé au démarrage du module pour envoyer toutes les catégories existantes
        via webhook (utile pour la synchronisation initiale)
        
        NOTE: Temporairement désactivé pour éviter les erreurs au démarrage.
        Les webhooks seront déclenchés lors de la création/modification normale des catégories.
        """
        super()._register_hook()
        
        # 🔥 DÉSACTIVÉ: Causer des problèmes au démarrage du module
        # La synchronisation initiale peut être faite manuellement si nécessaire
        return
        
        # # Vérifier si les webhooks sont activés pour les catégories POS
        # webhook_service = self.env['theresidence.webhook.service'].sudo()
        # if not webhook_service.is_event_enabled('POS_CATEGORY_CREATED'):
        #     return
        # 
        # # Récupérer toutes les catégories POS existantes
        # existing_categories = self.search([])
        # 
        # for category in existing_categories:
        #     # S'assurer que la catégorie a un UUID
        #     if not category.x_tr_uuid:
        #         category.with_context(skip_webhook=True).write({
        #             'x_tr_uuid': str(uuid.uuid4())
        #         })
        #     
        #     # Déclencher l'événement de création pour synchronisation
        #     try:
        #         webhook_service.trigger_event(
        #             internal_event='POS_CATEGORY_CREATED',
        #             entity_type='pos_category',
        #             entity_id=category.x_tr_uuid,
        #             data=category.to_category_api_dict(),
        #         )
        #     except Exception:
        #         # En cas d'erreur, on continue sans bloquer
        #         pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())
        
        records = super().create(vals_list)
        
        # Éviter les webhooks si contexte skip_webhook
        if self.env.context.get('skip_webhook'):
            return records
        
        # WEBHOOK: Création de catégorie POS
        webhook_service = self.env['theresidence.webhook.service']
        if webhook_service.is_event_enabled('POS_CATEGORY_CREATED'):
            for record in records:
                if record.x_tr_uuid:
                    webhook_service.trigger_event(
                        internal_event='POS_CATEGORY_CREATED',
                        entity_type='pos_category',
                        entity_id=record.x_tr_uuid,
                        data=record.to_category_api_dict(),
                    )
        
        return records

    def write(self, vals):
        # Éviter les webhooks si contexte skip_webhook
        if self.env.context.get('skip_webhook'):
            return super().write(vals)
        
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
        
        # 🔥 CORRECTION: Invalider le cache après l'écriture
        self.invalidate_recordset()
        
        # WEBHOOK: Modification de catégorie POS
        webhook_service = self.env['theresidence.webhook.service']
        if webhook_service.is_event_enabled('POS_CATEGORY_UPDATED'):
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
                        webhook_service.trigger_event(
                            internal_event='POS_CATEGORY_UPDATED',
                            entity_type='pos_category',
                            entity_id=record.x_tr_uuid,
                            data={**record.to_category_api_dict(), 'changedFields': changed_fields},
                        )
        
        return result

    def unlink(self):
        # Éviter les webhooks si contexte skip_webhook
        if self.env.context.get('skip_webhook'):
            return super().unlink()
        
        # Capturer les infos avant suppression
        category_data = []
        webhook_service = self.env['theresidence.webhook.service']
        send_webhook = webhook_service.is_event_enabled('POS_CATEGORY_DELETED')
        
        if send_webhook:
            for record in self:
                if record.x_tr_uuid:
                    category_data.append({
                        'uuid': record.x_tr_uuid,
                        'name': record.name,
                    })
        
        result = super().unlink()
        
        # WEBHOOK: Suppression de catégorie POS
        if send_webhook:
            for data in category_data:
                webhook_service.trigger_event(
                    internal_event='POS_CATEGORY_DELETED',
                    entity_type='pos_category',
                    entity_id=data['uuid'],
                    data={'id': data['uuid'], 'name': data['name']},
                )
        
        return result

    def to_category_api_dict(self):
        """
        🔥 CORRECTION: Force le rechargement des données depuis la DB
        pour éviter les problèmes de cache
        """
        self.ensure_one()
        
        # 🔥 Force un refresh depuis la base de données
        self.invalidate_recordset(['name', 'parent_id', 'sequence', 'image_128'])
        self.env.cr.execute("""
            SELECT id, name, parent_id, sequence 
            FROM pos_category 
            WHERE id = %s
        """, (self.id,))
        fresh_data = self.env.cr.dictfetchone()
        
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        image_url = (
            f"{base_url}/web/image/pos.category/{self.id}/image_128"
            if self.image_128 else ''
        )

        # 🔥 Trouver la catégorie racine avec des données fraîches
        root_id = fresh_data['id']
        root_name = fresh_data['name']
        current_parent_id = fresh_data['parent_id']
        
        # Remonter jusqu'à la racine
        while current_parent_id:
            self.env.cr.execute("""
                SELECT id, name, parent_id 
                FROM pos_category 
                WHERE id = %s
            """, (current_parent_id,))
            parent_data = self.env.cr.dictfetchone()
            if parent_data:
                root_id = parent_data['id']
                root_name = parent_data['name']
                current_parent_id = parent_data['parent_id']
            else:
                break
        
        # Récupérer l'UUID de la racine
        self.env.cr.execute("""
            SELECT x_tr_uuid 
            FROM pos_category 
            WHERE id = %s
        """, (root_id,))
        root_uuid_data = self.env.cr.dictfetchone()
        root_uuid = root_uuid_data['x_tr_uuid'] if root_uuid_data and root_uuid_data['x_tr_uuid'] else str(root_id)

        return {
            'id': self.x_tr_uuid or str(self.id),
            'kindId': root_uuid,
            'kindName': root_name or '',
            'name': fresh_data['name'] or '',
            'imageUrl': image_url,
            'sortOrder': fresh_data['sequence'] or 0
        }