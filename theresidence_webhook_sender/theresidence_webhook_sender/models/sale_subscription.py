# -*- coding: utf-8 -*-

import uuid
from odoo import models, fields, api


class SaleSubscription(models.Model):
    _inherit = 'sale.subscription'

    x_tr_uuid = fields.Char(string='UUID TR', copy=False, readonly=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())
        
        records = super().create(vals_list)
        
        # WEBHOOK: Création d'abonnement
        for record in records:
            if record.x_tr_uuid:
                self.env['theresidence.webhook.service'].trigger_event(
                    internal_event='SUBSCRIPTION_CREATED',
                    entity_type='subscription',
                    entity_id=record.x_tr_uuid,
                    data=record.to_subscription_api_dict(),
                )
        
        return records

    def write(self, vals):
        # Capturer les anciennes valeurs
        old_values = {}
        for record in self:
            if record.x_tr_uuid:
                old_values[record.id] = {
                    'stage_id': record.stage_id.id if record.stage_id else None,
                    'stage_category': record.stage_id.category if record.stage_id else None,
                    'date_start': record.date_start,
                    'recurring_next_date': record.recurring_next_date,
                }
        
        result = super().write(vals)
        
        # WEBHOOK: Modification d'abonnement
        for record in self:
            if record.x_tr_uuid:
                old_val = old_values.get(record.id, {})
                
                # Changement de statut (stage)
                if 'stage_id' in vals:
                    old_stage_category = old_val.get('stage_category')
                    new_stage_category = record.stage_id.category if record.stage_id else None
                    
                    if old_stage_category != new_stage_category:
                        # Mapper les catégories Odoo vers les statuts API
                        status_mapping = {
                            'draft': 'DRAFT',
                            'progress': 'ACTIVE',
                            'closed': 'CANCELLED',
                            'paused': 'PAUSED',
                        }
                        
                        old_status = status_mapping.get(old_stage_category, 'DRAFT')
                        new_status = status_mapping.get(new_stage_category, 'DRAFT')
                        
                        # Événement d'annulation
                        if new_status == 'CANCELLED':
                            self.env['theresidence.webhook.service'].trigger_event(
                                internal_event='SUBSCRIPTION_CANCELLED',
                                entity_type='subscription',
                                entity_id=record.x_tr_uuid,
                                data=record.to_subscription_api_dict(),
                                old_status=old_status,
                                new_status=new_status,
                            )
                        else:
                            # Événement de changement de statut
                            self.env['theresidence.webhook.service'].trigger_event(
                                internal_event='SUBSCRIPTION_STATUS_CHANGED',
                                entity_type='subscription',
                                entity_id=record.x_tr_uuid,
                                data=record.to_subscription_api_dict(),
                                old_status=old_status,
                                new_status=new_status,
                            )
                
                # Autres modifications (sans changement de statut)
                changed_fields = []
                
                if 'date_start' in vals and old_val.get('date_start') != record.date_start:
                    changed_fields.append('startDate')
                if 'recurring_next_date' in vals and old_val.get('recurring_next_date') != record.recurring_next_date:
                    changed_fields.append('nextDate')
                if 'partner_id' in vals:
                    changed_fields.append('member')
                if 'template_id' in vals:
                    changed_fields.append('plan')
                
                if changed_fields and 'stage_id' not in vals:
                    self.env['theresidence.webhook.service'].trigger_event(
                        internal_event='SUBSCRIPTION_UPDATED',
                        entity_type='subscription',
                        entity_id=record.x_tr_uuid,
                        data={**record.to_subscription_api_dict(), 'changedFields': changed_fields},
                    )
        
        return result

    def to_subscription_api_dict(self):
        """Convertit l'abonnement en dictionnaire pour l'API."""
        self.ensure_one()
        
        # Mapper le statut Odoo vers le statut API
        stage_category = self.stage_id.category if self.stage_id else 'draft'
        status_mapping = {
            'draft': 'DRAFT',
            'progress': 'ACTIVE',
            'closed': 'CANCELLED',
            'paused': 'PAUSED',
        }
        status = status_mapping.get(stage_category, 'DRAFT')
        
        # Récupérer le plan d'abonnement
        plan = None
        if self.template_id:
            product = self.env['product.template'].search([
                ('x_tr_is_subscription_plan', '=', True),
                ('id', '=', self.template_id.id)
            ], limit=1)
            
            if product:
                plan = {
                    'id': product.x_tr_space_uuid or str(product.id),
                    'name': product.name,
                }
        
        # Récupérer le membre
        member = None
        if self.partner_id and self.partner_id.x_tr_is_member:
            member = {
                'id': self.partner_id.x_tr_uuid or str(self.partner_id.id),
                'name': self.partner_id.name,
                'email': self.partner_id.email or '',
            }
        
        return {
            'id': self.x_tr_uuid or str(self.id),
            'status': status,
            'startDate': self.date_start.isoformat() if self.date_start else None,
            'endDate': self.date.isoformat() if self.date else None,
            'nextDate': self.recurring_next_date.isoformat() if self.recurring_next_date else None,
            'recurringTotal': float(self.recurring_total) if self.recurring_total else 0.0,
            'currency': self.currency_id.name if self.currency_id else 'XOF',
            'member': member,
            'plan': plan,
            'reference': self.code or '',
        }