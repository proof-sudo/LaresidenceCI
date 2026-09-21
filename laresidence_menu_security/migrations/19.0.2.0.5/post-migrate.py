import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Accorder l'accès complet à webhook.config pour base.group_user."""
    cr.execute("SELECT id FROM ir_model WHERE model = 'webhook.config'")
    row = cr.fetchone()
    if not row:
        _logger.info("migrate 2.0.5: modèle webhook.config absent, rien à faire")
        return
    model_id = row[0]

    cr.execute("SELECT res_id FROM ir_model_data WHERE module = 'base' AND name = 'group_user'")
    row = cr.fetchone()
    if not row:
        _logger.warning("migrate 2.0.5: base.group_user introuvable")
        return
    group_user_id = row[0]

    # Mettre à jour les droits existants (active=true indispensable)
    cr.execute("""
        UPDATE ir_model_access
        SET active = true, perm_read = true, perm_write = true, perm_create = true, perm_unlink = true
        WHERE model_id = %s AND group_id = %s
    """, (model_id, group_user_id))

    if cr.rowcount == 0:
        # Créer l'entrée si elle n'existe pas
        cr.execute("""
            INSERT INTO ir_model_access
                (name, active, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink)
            VALUES ('webhook.config.user', true, %s, %s, true, true, true, true)
        """, (model_id, group_user_id))
        _logger.info("migrate 2.0.5: accès webhook.config créé pour group_user")
    else:
        _logger.info("migrate 2.0.5: accès webhook.config mis à jour pour group_user (rowcount=%s)", cr.rowcount)
