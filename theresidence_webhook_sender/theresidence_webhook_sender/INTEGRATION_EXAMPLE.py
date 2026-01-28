# -*- coding: utf-8 -*-
"""
EXEMPLE D'INTÉGRATION DU WEBHOOK SENDER
========================================

Ce fichier montre comment modifier votre module existant pour utiliser
le nouveau service de webhooks sortants.

IMPORTANT: Ce fichier est un EXEMPLE. Ne l'ajoutez pas à votre module.
Utilisez-le comme référence pour modifier vos fichiers existants.
"""

# ==============================================================================
# EXEMPLE 1: Modification de sale_order.py
# ==============================================================================

# AVANT:
"""
class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    def action_approve_reservation(self):
        for order in self:
            if order.x_tr_reservation_status != 'PENDING':
                raise ValidationError(_("Seules les réservations en attente peuvent être approuvées."))
            old = order.x_tr_reservation_status
            order.x_tr_reservation_status = 'APPROVED'
            order.action_confirm()
            self.env['theresidence.webhook'].trigger_event(  # <-- ANCIEN
                'RESERVATION_STATUS_CHANGED', 'reservation', order.x_tr_uuid,
                order.to_reservation_api_dict(), old, 'APPROVED'
            )
"""

# APRÈS:
"""
class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    def action_approve_reservation(self):
        for order in self:
            if order.x_tr_reservation_status != 'PENDING':
                raise ValidationError(_("Seules les réservations en attente peuvent être approuvées."))
            old = order.x_tr_reservation_status
            order.x_tr_reservation_status = 'APPROVED'
            order.action_confirm()
            self.env['theresidence.webhook.service'].trigger_event(  # <-- NOUVEAU
                'RESERVATION_STATUS_CHANGED', 'reservation', order.x_tr_uuid,
                order.to_reservation_api_dict(), old, 'APPROVED'
            )
"""

# ==============================================================================
# EXEMPLE 2: Modification de pos_order.py
# ==============================================================================

# AVANT:
"""
class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    def action_confirm_order(self):
        for order in self:
            if order.x_tr_order_status != 'PENDING':
                raise ValidationError(_("Seules les commandes en attente peuvent être confirmées."))
            old = order.x_tr_order_status
            order.x_tr_order_status = 'CONFIRMED'
            self.env['theresidence.webhook'].trigger_event(  # <-- ANCIEN
                'ORDER_STATUS_CHANGED', 'order', order.x_tr_uuid,
                order.to_order_api_dict(), old, 'CONFIRMED'
            )
"""

# APRÈS:
"""
class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    def action_confirm_order(self):
        for order in self:
            if order.x_tr_order_status != 'PENDING':
                raise ValidationError(_("Seules les commandes en attente peuvent être confirmées."))
            old = order.x_tr_order_status
            order.x_tr_order_status = 'CONFIRMED'
            self.env['theresidence.webhook.service'].trigger_event(  # <-- NOUVEAU
                'ORDER_STATUS_CHANGED', 'order', order.x_tr_uuid,
                order.to_order_api_dict(), old, 'CONFIRMED'
            )
"""

# ==============================================================================
# EXEMPLE 3: Liste complète des modifications nécessaires
# ==============================================================================

MODIFICATIONS_REQUISES = {
    'sale_order.py': {
        'ligne_143': 'create_reservation_from_api() → RESERVATION_CREATED',
        'ligne_156': 'action_approve_reservation() → RESERVATION_STATUS_CHANGED/APPROVED',
        'ligne_168': 'action_reject_reservation() → RESERVATION_STATUS_CHANGED/REJECTED',
        'ligne_179': 'action_checkin_reservation() → RESERVATION_STATUS_CHANGED/CHECKED_IN',
        'ligne_191': 'action_cancel_reservation() → RESERVATION_CANCELLED',
        'ligne_246': 'create_subscription_from_api() → SUBSCRIPTION_CREATED',
        'ligne_258': 'action_pause_subscription() → SUBSCRIPTION_STATUS_CHANGED/PAUSED',
        'ligne_269': 'action_resume_subscription() → SUBSCRIPTION_STATUS_CHANGED/ACTIVE',
        'ligne_280': 'action_cancel_subscription() → SUBSCRIPTION_CANCELLED',
    },
    'pos_order.py': {
        'ligne_89': 'create_order_from_api() → ORDER_CREATED',
        'ligne_100': 'action_confirm_order() → ORDER_STATUS_CHANGED/CONFIRMED',
        'ligne_111': 'action_ready_order() → ORDER_STATUS_CHANGED/READY',
        'ligne_122': 'action_complete_order() → ORDER_STATUS_CHANGED/COMPLETED',
        'ligne_133': 'action_cancel_order() → ORDER_CANCELLED',
    }
}

# ==============================================================================
# COMMANDE POUR REMPLACEMENT AUTOMATIQUE
# ==============================================================================

"""
# Dans le terminal, dans le dossier de votre module existant:

# Méthode 1: sed (Linux/Mac)
find . -name "*.py" -type f -exec sed -i "s/self\.env\['theresidence\.webhook'\]/self.env['theresidence.webhook.service']/g" {} \;

# Méthode 2: Python script
python3 << 'EOF'
import os
import re

def replace_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remplacer theresidence.webhook par theresidence.webhook.service
    new_content = content.replace(
        "self.env['theresidence.webhook']",
        "self.env['theresidence.webhook.service']"
    )
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✓ Modifié: {filepath}")
    else:
        print(f"- Aucun changement: {filepath}")

# Parcourir tous les fichiers .py
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            replace_in_file(filepath)
EOF
"""

# ==============================================================================
# APRÈS LES MODIFICATIONS
# ==============================================================================

"""
1. Redémarrer Odoo
2. Mettre à jour le module existant
3. Installer le module theresidence_webhook_sender
4. Vérifier la configuration dans Webhooks The Residence > Configuration
5. Tester en créant une commande/réservation
6. Vérifier que le webhook apparaît dans la Queue
7. Vérifier les logs pour confirmer l'envoi
"""

# ==============================================================================
# VÉRIFICATION
# ==============================================================================

"""
# Pour vérifier que les modifications ont bien été faites:

grep -r "theresidence.webhook'" .
# Ne devrait rien retourner (ou seulement des commentaires)

grep -r "theresidence.webhook.service" .
# Devrait afficher tous les appels modifiés
"""

# ==============================================================================
# DÉPENDANCES DANS __manifest__.py
# ==============================================================================

"""
Dans le __manifest__.py de votre module existant, ajoutez:

{
    'name': 'The Residence Integration',
    ...
    'depends': [
        'base',
        'sale',
        'point_of_sale',
        'theresidence_webhook_sender',  # <-- AJOUTER CETTE LIGNE
    ],
    ...
}
"""
