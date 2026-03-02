# -*- coding: utf-8 -*-

import uuid
import secrets
import logging

from odoo import models, fields, api,_
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Champs The Residence
    x_tr_uuid = fields.Char(string='UUID TR', copy=False, readonly=True, index=True)
    x_tr_qr_token = fields.Char(string='Token QR', copy=False, readonly=True)
    x_tr_is_member = fields.Boolean(string='Est membre TR', default=False)
    x_tr_member_status = fields.Selection([
        ('PENDING', 'En attente'),
        ('ACTIVE', 'Actif'),
        ('SUSPENDED', 'Suspendu'),
        ('INACTIVE', 'Inactif'),
    ], string='Statut membre', default='PENDING')
    x_tr_membership_type_id = fields.Many2one('theresidence.membership.type', string='Type d\'adhésion')
    x_tr_joined_at = fields.Date(string='Date d\'adhésion')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('x_tr_is_member') and not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())
                vals['x_tr_qr_token'] = f"member-{secrets.token_urlsafe(16)}"
        
        records = super().create(vals_list)
        
        # WEBHOOK: Création de membre
        # for record in records:
        #     if record.x_tr_is_member and record.x_tr_uuid:
        #         self.env['theresidence.webhook.service'].trigger_event(
        #             internal_event='MEMBER_CREATED',
        #             entity_type='member',
        #             entity_id=record.x_tr_uuid,
        #             data=record.to_member_api_dict(),
        #         )
        
        # return records

    def write(self, vals):
        # Capturer les anciennes valeurs pour les membres
        old_values = {}
        for partner in self:
            if partner.x_tr_is_member and partner.x_tr_uuid:
                old_values[partner.id] = {
                    'name': partner.name,
                    'email': partner.email,
                    'phone': partner.phone,
                    'membership_type_id': partner.x_tr_membership_type_id.id if partner.x_tr_membership_type_id else None,
                    'company_name': partner.company_name,
                    'function': partner.function,
                }
        
        # Générer UUID/token si nécessaire
        if vals.get('x_tr_is_member'):
            for partner in self:
                if not partner.x_tr_uuid:
                    vals.setdefault('x_tr_uuid', str(uuid.uuid4()))
                if not partner.x_tr_qr_token:
                    vals.setdefault('x_tr_qr_token', f"member-{secrets.token_urlsafe(16)}")
        
        result = super().write(vals)
        
        # WEBHOOK: Modification de membre
        for partner in self:
            if partner.x_tr_is_member and partner.x_tr_uuid:
                old_val = old_values.get(partner.id, {})
                
                # Changement de type d'adhésion
                if 'x_tr_membership_type_id' in vals:
                    old_membership_id = old_val.get('membership_type_id')
                    new_membership_id = partner.x_tr_membership_type_id.id if partner.x_tr_membership_type_id else None
                    
                    if old_membership_id != new_membership_id:
                        old_membership = self.env['theresidence.membership.type'].browse(old_membership_id) if old_membership_id else None
                        
                        self.env['theresidence.webhook.service'].trigger_event(
                            internal_event='MEMBER_MEMBERSHIP_CHANGED',
                            entity_type='member',
                            entity_id=partner.x_tr_uuid,
                            data={
                                **partner.to_member_api_dict(),
                                'previousMembershipType': {
                                    'code': old_membership.code if old_membership else '',
                                    'name': old_membership.name if old_membership else '',
                                } if old_membership else None,
                            },
                            old_status=old_membership.code if old_membership else None,
                            new_status=partner.x_tr_membership_type_id.code if partner.x_tr_membership_type_id else None,
                        )
                
                # Autres modifications
                changed_fields = []
                if 'name' in vals and old_val.get('name') != partner.name:
                    changed_fields.append('name')
                if 'email' in vals and old_val.get('email') != partner.email:
                    changed_fields.append('email')
                if 'phone' in vals and old_val.get('phone') != partner.phone:
                    changed_fields.append('phone')
                if 'company_name' in vals and old_val.get('company_name') != partner.company_name:
                    changed_fields.append('companyName')
                if 'function' in vals and old_val.get('function') != partner.function:
                    changed_fields.append('jobTitle')
                if 'image_1920' in vals or 'image_128' in vals:
                    changed_fields.append('image')
                
                # if changed_fields and 'x_tr_membership_type_id' not in vals:
                #     self.env['theresidence.webhook.service'].trigger_event(
                #         internal_event='MEMBER_UPDATED',
                #         entity_type='member',
                #         entity_id=partner.x_tr_uuid,
                #         data={**partner.to_member_api_dict(), 'changedFields': changed_fields},
                #     )
        
        return result

    def unlink(self):
        # Capturer les infos avant suppression
        member_data = []
        for partner in self:
            if partner.x_tr_is_member and partner.x_tr_uuid:
                member_data.append({
                    'uuid': partner.x_tr_uuid,
                    'name': partner.name,
                    'email': partner.email,
                })
        
        result = super().unlink()
        

        
        return result

    def to_member_api_dict(self):
        self.ensure_one()
        name_parts = (self.name or '').split(' ', 1)
        return {
            'id': self.x_tr_uuid or str(self.id),
            'firstName': name_parts[0] if name_parts else '',
            'lastName': name_parts[1] if len(name_parts) > 1 else '',
            'email': self.email or '',
            'phone': self.phone or '',
            'companyName': self.parent_id.name if self.parent_id else (self.company_name or ''),
            'jobTitle': self.function or '',
            'membershipTypeId': self.x_tr_membership_type_id.x_uuid if self.x_tr_membership_type_id else None,
            'membershipTypeCode': self.x_tr_membership_type_id.code if self.x_tr_membership_type_id else '',
            'membershipTypeName': self.x_tr_membership_type_id.name if self.x_tr_membership_type_id else '',
            'status': self.x_tr_member_status or 'ACTIVE',
            'joinedAt': self.x_tr_joined_at.isoformat() if self.x_tr_joined_at else '',
            'qrToken': self.x_tr_qr_token or ''
        }

    def action_generate_ceo_subscriptions(self):
        """
        Fonction appelée par le bouton pour créer un abonnement 
        "Abonnement CEO" pour TOUS les contacts membres
        """
        # Rechercher TOUS les contacts avec x_tr_is_member == True
        all_members = self.env['res.partner'].search([
            ('x_tr_is_member', '=', True)
        ])
        
        if not all_members:
            raise UserError(
                "Aucun contact membre trouvé (x_tr_is_member == True)."
            )
        
        # Rechercher le produit "Abonnement CEO"
        subscription_product = self.env['product.product'].search([
            ('name', '=', 'Abonnement CEO'),
            ('recurring_invoice', '=', True)
        ], limit=1)
        
        if not subscription_product:
            raise UserError(
                "Le produit 'Abonnement CEO' n'existe pas. "
                "Veuillez créer ce produit d'abonnement d'abord."
            )
        
        # Récupérer un plan d'abonnement (sale.subscription.plan)
        subscription_plan = self.env['sale.subscription.plan'].search([
            ('name', 'ilike', 'mensuel')
        ], limit=1)
        
        if not subscription_plan:
            # Prendre le premier plan disponible
            subscription_plan = self.env['sale.subscription.plan'].search([], limit=1)
        
        if not subscription_plan:
            raise UserError(
                "Aucun plan d'abonnement trouvé. "
                "Veuillez configurer au moins un plan d'abonnement."
            )
        
        # Compteurs
        created_count = 0
        skipped_count = 0
        error_list = []
        
        # Parcourir TOUS les membres
        for partner in all_members:
            try:
                # Vérifier s'il existe déjà un abonnement actif
                existing_subscription = self.env['sale.order'].search([
                    ('partner_id', '=', partner.id),
                    ('is_subscription', '=', True),
                    ('subscription_state', 'in', ['3_progress', '4_paused'])
                ], limit=1)
                
                if existing_subscription:
                    skipped_count += 1
                    _logger.info(
                        f"Contact {partner.name} ignoré : abonnement actif existant "
                        f"(Référence: {existing_subscription.name})"
                    )
                    continue
                
                # Créer le bon de commande d'abonnement
                subscription_vals = {
                    'partner_id': partner.id,
                    'is_subscription': True,
                    'plan_id': subscription_plan.id,
                    'order_line': [(0, 0, {
                        'product_id': subscription_product.id,
                        'name': subscription_product.name,
                        'product_uom_qty': 1,
                        # 'product_uom_id': subscription_product.uom_id.id,  # Changé de product_uom à product_uom_id
                        'price_unit': subscription_product.list_price,
                    })],
                }
                
                subscription = self.env['sale.order'].create(subscription_vals)
                
                # Confirmer l'abonnement
                subscription.action_confirm()
                
                created_count += 1
                _logger.info(
                    f"Abonnement créé avec succès pour {partner.name} (ID: {subscription.id})"
                )
                
            except Exception as e:
                error_list.append(f"{partner.name}: {str(e)}")
                _logger.error(
                    f"Erreur lors de la création de l'abonnement pour {partner.name}: {str(e)}"
                )
        
        # Préparer le message de résultat
        message_parts = [
            f"✅ {created_count} abonnement(s) créé(s)",
            f"⏭️ {skipped_count} contact(s) ignoré(s) (abonnement existant)",
        ]
        
        if error_list:
            message_parts.append(f"❌ {len(error_list)} erreur(s)")
            message_parts.append("\nDétails des erreurs:")
            message_parts.extend([f"  - {err}" for err in error_list[:5]])  # Afficher max 5 erreurs
            if len(error_list) > 5:
                message_parts.append(f"  ... et {len(error_list) - 5} autre(s) erreur(s)")
        
        message = "\n".join(message_parts)
        
        # Retourner une notification de succès
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Génération des abonnements terminée',
                'message': message,
                'type': 'success' if created_count > 0 else 'warning',
                'sticky': True,  # Afficher plus longtemps pour lire les détails
            }
        }
        
    @api.model
    def create_member_from_api(self, data):
        first_name = data.get('firstName', '')
        last_name = data.get('lastName', '')
        name = f"{first_name} {last_name}".strip() or data.get('email', 'Unknown')
        
        vals = {
            'name': name,
            'email': data.get('email'),
            'phone': data.get('phone'),
            'function': data.get('jobTitle'),
            'company_name': data.get('companyName'),
            'x_tr_is_member': True,
            'x_tr_member_status': data.get('status', 'ACTIVE'),
            'x_tr_joined_at': data.get('joinedAt') or fields.Date.today(),
        }
        
        if data.get('membershipTypeCode'):
            mtype = self.env['theresidence.membership.type'].search([('code', '=', data['membershipTypeCode'])], limit=1)
            if mtype:
                vals['x_tr_membership_type_id'] = mtype.id
        
        if data.get('email'):
            existing = self.search([('email', '=', data['email'])], limit=1)
            if existing:
                existing.write(vals)
                return existing
        
        return self.create(vals)
