# -*- coding: utf-8 -*-
"""
Script de génération de données de test pour les réservations.

Usage (Odoo shell) :
    odoo-bin shell -d <database> < theresidence_api/scripts/seed_test_reservations.py

Ou depuis le shell interactif :
    exec(open('theresidence_api/scripts/seed_test_reservations.py').read())
"""

import uuid
from datetime import datetime, timedelta

env = env  # noqa — disponible dans le contexte Odoo shell

TODAY = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

print("=" * 60)
print("SEED TEST DATA — The Residence Reservations")
print("=" * 60)

# ──────────────────────────────────────────────
# 1. MEMBRE (res.partner)
# ──────────────────────────────────────────────

member = env['res.partner'].search([('x_tr_uuid', '!=', False)], limit=1)

if not member:
    member = env['res.partner'].create({
        'name': 'Konan Yao',
        'email': 'konan.yao@test.ci',
        'phone': '+22507000001',
        'x_tr_uuid': str(uuid.uuid4()),
        'x_tr_is_member': True,
    })
    print(f"[OK] Membre créé : {member.name} (UUID: {member.x_tr_uuid})")
else:
    print(f"[--] Membre existant utilisé : {member.name} (UUID: {member.x_tr_uuid})")

# ──────────────────────────────────────────────
# 2. ESPACE (product.template)
# ──────────────────────────────────────────────

space = env['product.template'].search([('x_tr_is_space', '=', True)], limit=1)

if not space:
    space = env['product.template'].create({
        'name': 'Salle Ivoire',
        'type': 'service',
        'x_tr_is_space': True,
        'x_tr_space_capacity': 10,
        'list_price': 25000.0,
        'description_sale': 'Salle de réunion climatisée avec projecteur',
    })
    print(f"[OK] Espace créé : {space.name} (UUID: {space.x_tr_space_uuid})")
else:
    print(f"[--] Espace existant utilisé : {space.name} (UUID: {space.x_tr_space_uuid})")

# ──────────────────────────────────────────────
# 3. RÉSERVATIONS DE TEST
# ──────────────────────────────────────────────

reservations_data = [
    {
        'label': 'Réservation PENDING — ce matin',
        'status': 'PENDING',
        'start_offset_h': 9,
        'duration_h': 2,
        'guests': 3,
        'notes': 'Réunion équipe projet Alpha',
    },
    {
        'label': 'Réservation APPROVED — ce midi',
        'status': 'APPROVED',
        'start_offset_h': 12,
        'duration_h': 1,
        'guests': 0,
        'notes': 'Entretien RH',
    },
    {
        'label': 'Réservation CHECKED_IN — cet après-midi',
        'status': 'CHECKED_IN',
        'start_offset_h': 14,
        'duration_h': 3,
        'guests': 5,
        'notes': 'Workshop innovation',
    },
    {
        'label': 'Réservation PENDING — soirée',
        'status': 'PENDING',
        'start_offset_h': 18,
        'duration_h': 2,
        'guests': 8,
        'notes': 'Événement client Abidjan Tech',
    },
]

product = space.product_variant_id
if not product:
    print("[ERR] Aucune variante produit pour l'espace — impossible de créer les lignes de commande")
    raise SystemExit(1)

created = []
for data in reservations_data:
    start = TODAY + timedelta(hours=data['start_offset_h'])
    end   = start + timedelta(hours=data['duration_h'])

    order = env['sale.order'].create({
        'partner_id': member.id,
        'x_tr_is_reservation': True,
        'x_tr_reservation_status': data['status'],
        'x_tr_space_id': space.id,
        'x_tr_start_time': start,
        'x_tr_end_time': end,
        'x_tr_guest_count': data['guests'],
        'x_tr_notes': data['notes'],
    })

    env['sale.order.line'].create({
        'order_id': order.id,
        'product_id': product.id,
        'product_uom_qty': 1,
        'price_unit': space.list_price,
    })

    created.append(order)
    print(f"[OK] {data['label']}")
    print(f"     UUID: {order.x_tr_uuid}  |  {start.strftime('%H:%M')} - {end.strftime('%H:%M')}  |  statut: {data['status']}")

# ──────────────────────────────────────────────
# 4. COMMIT
# ──────────────────────────────────────────────

env.cr.commit()

print()
print("=" * 60)
print(f"DONE — {len(created)} réservation(s) créée(s) pour aujourd'hui")
print(f"Membre  : {member.name} ({member.email})")
print(f"Espace  : {space.name}")
print(f"Ouvrir le POS et cliquer sur le bouton calendrier pour vérifier.")
print("=" * 60)
