import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Assigne l'utilisateur DIVISION COMMERCIAL au groupe group_division_commercial."""
    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'laresidence_menu_security' AND name = 'group_division_commercial'
    """)
    row = cr.fetchone()
    if not row:
        _logger.warning("migrate 2.0.2: groupe group_division_commercial introuvable")
        return
    group_id = row[0]

    # Assigner l'utilisateur DIVISION COMMERCIAL (ID 65)
    cr.execute("""
        INSERT INTO res_groups_users_rel (gid, uid)
        VALUES (%s, 65)
        ON CONFLICT DO NOTHING
    """, (group_id,))

    _logger.info("migrate 2.0.2: utilisateur 65 (DIVISION COMMERCIAL) assigné au groupe %s", group_id)

    # Désactiver les menus booking_engine (au cas où pas encore fait)
    cr.execute("""
        UPDATE ir_ui_menu SET active = false
        WHERE id IN (
            SELECT m.id FROM ir_ui_menu m
            JOIN ir_model_data d ON d.model = 'ir.ui.menu' AND d.res_id = m.id
            WHERE d.module = 'booking_engine'
        )
    """)
