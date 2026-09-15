import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Désactive complètement les menus booking_engine pour tous les utilisateurs."""
    cr.execute("""
        SELECT m.id FROM ir_ui_menu m
        JOIN ir_model_data d ON d.model = 'ir.ui.menu' AND d.res_id = m.id
        WHERE d.module = 'booking_engine' AND m.parent_id IS NULL
    """)
    menu_ids = [r[0] for r in cr.fetchall()]

    for menu_id in menu_ids:
        cr.execute("UPDATE ir_ui_menu SET active = false WHERE id = %s", (menu_id,))

    if menu_ids:
        _logger.info("migrate 2.0.1: %d menu(s) booking_engine désactivé(s)", len(menu_ids))
    else:
        _logger.info("migrate 2.0.1: aucun menu booking_engine trouvé")
