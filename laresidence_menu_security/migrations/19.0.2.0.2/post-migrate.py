import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Assigne l'utilisateur DIVISION COMMERCIAL au groupe group_division_commercial."""
    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'laresidence_menu_security' AND name = 'group_division_commercial'
    """)
    row = cr.fetchone()
    if row:
        group_id = row[0]
        cr.execute("""
            INSERT INTO res_groups_users_rel (gid, uid)
            VALUES (%s, 65)
            ON CONFLICT DO NOTHING
        """, (group_id,))
        _logger.info("migrate 2.0.2: utilisateur 65 (DIVISION COMMERCIAL) assigné au groupe %s", group_id)
    else:
        _logger.warning("migrate 2.0.2: groupe group_division_commercial introuvable")

    # Désactiver les menus booking_engine (au cas où pas encore fait)
    cr.execute("""
        UPDATE ir_ui_menu SET active = false
        WHERE id IN (
            SELECT m.id FROM ir_ui_menu m
            JOIN ir_model_data d ON d.model = 'ir.ui.menu' AND d.res_id = m.id
            WHERE d.module = 'booking_engine'
        )
    """)

    # Corriger l'accès webhook.config : s'assurer que base.group_user a bien l'accès
    cr.execute("""
        SELECT res_id FROM ir_model_data WHERE module = 'base' AND name = 'group_user'
    """)
    bu_row = cr.fetchone()
    cr.execute("SELECT id FROM ir_model WHERE model = 'webhook.config'")
    wm_row = cr.fetchone()
    if bu_row and wm_row:
        group_user_id = bu_row[0]
        model_id = wm_row[0]
        cr.execute("""
            UPDATE ir_model_access SET group_id = %s
            WHERE name = 'webhook.config.user' AND model_id = %s
        """, (group_user_id, model_id))
        if cr.rowcount == 0:
            cr.execute("""
                INSERT INTO ir_model_access
                    (name, active, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink)
                VALUES ('webhook.config.user', true, %s, %s, true, true, true, true)
            """, (model_id, group_user_id))
        _logger.info("migrate 2.0.2: webhook.config access corrigé pour group_user id=%s", group_user_id)
    else:
        _logger.warning("migrate 2.0.2: webhook.config ou base.group_user introuvable, accès non corrigé")
