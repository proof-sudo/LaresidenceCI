import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

SEP = "=" * 80


def post_init_hook(env):
    cr = env.cr

    _logger.info(SEP)
    _logger.info("LARESIDENCE MENU DIAGNOSTIC — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    _logger.info(SEP)

    # ── 1. Menus racines ─────────────────────────────────────────────────────
    cr.execute("""
        SELECT m.id, m.name, m.sequence,
               COALESCE(d.module || '.' || d.name,
                        '(no_xml_id,id=' || m.id::text || ')') AS xml_id
        FROM ir_ui_menu m
        LEFT JOIN ir_model_data d
               ON d.model = 'ir.ui.menu' AND d.res_id = m.id
        WHERE m.parent_id IS NULL
        ORDER BY m.sequence
    """)
    menus = cr.fetchall()   # (id, name, sequence, xml_id)

    # Groupes associés à chaque menu
    menu_groups = {}    # {menu_id: [(gid, gname, gxml_id), ...]}
    try:
        cr.execute("SAVEPOINT mg_read")
        cr.execute("""
            SELECT rel.menu_id, g.id, g.name,
                   COALESCE(d.module || '.' || d.name, '') AS xml_id
            FROM ir_ui_menu_group_rel rel
            JOIN res_groups g ON g.id = rel.gid
            LEFT JOIN ir_model_data d
                   ON d.model = 'res.groups' AND d.res_id = g.id
        """)
        for menu_id, gid, gname, gxml in cr.fetchall():
            menu_groups.setdefault(menu_id, []).append((gid, gname, gxml))
        cr.execute("RELEASE SAVEPOINT mg_read")
    except Exception as exc:
        cr.execute("ROLLBACK TO SAVEPOINT mg_read")
        _logger.warning("menu_groups query failed: %s", exc)

    _logger.info("\n>>> APP-LEVEL MENUS :\n")
    for mid, mname, mseq, xml_id in menus:
        grps = menu_groups.get(mid, [])
        if grps:
            groups_str = ' | '.join(f'{gname} [{gxml}]' for _, gname, gxml in grps)
            flag = "⚠ base.group_user" if any(x == 'base.group_user' for _, _, x in grps) else "OK"
        else:
            groups_str = "AUCUN GROUPE — visible par tous"
            flag = "⚠ NO GROUP"
        _logger.info("  [%-20s] seq=%-4s | %-55s | %s | groupes: %s",
                     flag, mseq, xml_id, mname, groups_str)

    # ── 2. Users internes ────────────────────────────────────────────────────
    cr.execute("""
        SELECT u.id, p.name, u.login
        FROM res_users u
        JOIN res_partner p ON p.id = u.partner_id
        WHERE u.share = false AND u.active = true
        ORDER BY p.name
    """)
    users = cr.fetchall()   # (uid, name, login)

    # Groupes de chaque user
    user_groups = {}    # {uid: [(gid, gname, gxml_id), ...]}
    try:
        cr.execute("SAVEPOINT ug_read")
        cr.execute("""
            SELECT rel.uid, g.id, g.name,
                   COALESCE(d.module || '.' || d.name, '') AS xml_id
            FROM res_groups_users_rel rel
            JOIN res_groups g ON g.id = rel.gid
            LEFT JOIN ir_model_data d
                   ON d.model = 'res.groups' AND d.res_id = g.id
        """)
        for uid, gid, gname, gxml in cr.fetchall():
            user_groups.setdefault(uid, []).append((gid, gname, gxml))
        cr.execute("RELEASE SAVEPOINT ug_read")
    except Exception as exc:
        cr.execute("ROLLBACK TO SAVEPOINT ug_read")
        _logger.warning("user_groups query failed: %s", exc)

    _logger.info("\n>>> USERS INTERNES — groupes + menus visibles :\n")
    for uid, uname, ulogin in users:
        ugrps = user_groups.get(uid, [])
        uid_set = {gid for gid, _, _ in ugrps}
        groups_str = ', '.join(sorted(gname for _, gname, _ in ugrps)) or '(aucun)'

        visible = []
        for mid, mname, _, _ in menus:
            mgid_set = {gid for gid, _, _ in menu_groups.get(mid, [])}
            if not mgid_set or mgid_set & uid_set:
                visible.append(mname)

        _logger.info("  USER : %-30s login=%s", uname, ulogin)
        _logger.info("    groupes : %s", groups_str)
        _logger.info("    menus   : %s", ' | '.join(visible) if visible else '(aucun)')
        _logger.info("")

    _logger.info(SEP)
    _logger.info("FIN DIAGNOSTIC")
    _logger.info(SEP)
