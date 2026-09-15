import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Désactiver tous les menus racines du module website."""
    cr.execute("""
        UPDATE ir_ui_menu SET active = false
        WHERE id IN (
            SELECT m.id FROM ir_ui_menu m
            JOIN ir_model_data d ON d.model = 'ir.ui.menu' AND d.res_id = m.id
            WHERE d.module = 'website' AND m.parent_id IS NULL
        )
    """)
    _logger.info("migrate 2.0.3: %d menu(s) website désactivé(s)", cr.rowcount)
