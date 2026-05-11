import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    - Retirer base.group_partner_manager de CUISINE (ne peut pas créer de contacts)
    - group_contacts_full_details est automatiquement hérité via
      group_division_commercial et group_division_direction (implied_ids)
    """
    # Récupérer l'ID de base.group_partner_manager
    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'base' AND name = 'group_partner_manager'
    """)
    row = cr.fetchone()
    if not row:
        _logger.warning("migrate 2.0.7: base.group_partner_manager introuvable")
        return
    partner_manager_id = row[0]

    # Retirer group_partner_manager de CUISINE
    cr.execute("SELECT id FROM res_users WHERE login = 'cuisine@laresidence-abidjan.com'")
    row = cr.fetchone()
    if row:
        cuisine_uid = row[0]
        cr.execute(
            "DELETE FROM res_groups_users_rel WHERE uid = %s AND gid = %s",
            (cuisine_uid, partner_manager_id)
        )
        _logger.info(
            "migrate 2.0.7: group_partner_manager retiré de CUISINE (uid=%s, rowcount=%s)",
            cuisine_uid, cr.rowcount
        )
    else:
        _logger.info("migrate 2.0.7: user cuisine@laresidence-abidjan.com non trouvé")

    # Désactiver les anciennes règles division si elles existent encore
    for xmlid_name in ('rule_contacts_all_commercial', 'rule_contacts_all_direction'):
        cr.execute(
            "SELECT res_id FROM ir_model_data WHERE module = 'laresidence_menu_security' AND name = %s",
            (xmlid_name,)
        )
        row = cr.fetchone()
        if row:
            cr.execute("UPDATE ir_rule SET active = false WHERE id = %s", (row[0],))
            _logger.info("migrate 2.0.7: %s désactivée (id=%s)", xmlid_name, row[0])
