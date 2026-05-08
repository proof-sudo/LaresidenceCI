import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    cr = env.cr
    try:
        cr.execute("SAVEPOINT booking_restrict")

        cr.execute("""
            SELECT m.id FROM ir_ui_menu m
            JOIN ir_model_data d ON d.model = 'ir.ui.menu' AND d.res_id = m.id
            WHERE d.module = 'booking_engine' AND m.parent_id IS NULL
        """)
        menu_ids = [r[0] for r in cr.fetchall()]

        for menu_id in menu_ids:
            cr.execute("UPDATE ir_ui_menu SET active = false WHERE id = %s", (menu_id,))

        if menu_ids:
            _logger.info("booking_engine: %d menu(s) désactivé(s)", len(menu_ids))
        else:
            _logger.info("booking_engine: aucun menu racine trouvé (module non installé)")

        cr.execute("RELEASE SAVEPOINT booking_restrict")
    except Exception as exc:
        cr.execute("ROLLBACK TO SAVEPOINT booking_restrict")
        _logger.warning("booking_engine menu restriction échouée: %s", exc)
