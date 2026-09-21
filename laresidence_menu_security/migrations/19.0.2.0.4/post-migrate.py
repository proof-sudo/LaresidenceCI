import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Assigner Djakaridja (id=2) à group_division_direction pour l'accès total contacts."""
    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'laresidence_menu_security' AND name = 'group_division_direction'
    """)
    row = cr.fetchone()
    if not row:
        _logger.warning("migrate 2.0.4: groupe group_division_direction introuvable")
        return
    group_id = row[0]

    cr.execute("""
        INSERT INTO res_groups_users_rel (gid, uid)
        VALUES (%s, 2)
        ON CONFLICT DO NOTHING
    """, (group_id,))

    _logger.info("migrate 2.0.4: utilisateur 2 (Djakaridja) assigné au groupe group_division_direction id=%s", group_id)

    # Supprimer la règle rule_contacts_all_admin si elle existe encore en base
    cr.execute("""
        DELETE FROM ir_rule
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'laresidence_menu_security' AND name = 'rule_contacts_all_admin'
        )
    """)
    if cr.rowcount:
        _logger.info("migrate 2.0.4: rule_contacts_all_admin supprimée")
