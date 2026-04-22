import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

SEP = "=" * 80


def post_init_hook(env):
    _logger.info(SEP)
    _logger.info("LARESIDENCE MENU DIAGNOSTIC — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    _logger.info(SEP)

    root_menus = env['ir.ui.menu'].search([('parent_id', '=', False)], order='sequence asc')

    # ── 1. Liste de tous les menus racines ──────────────────────────────────
    _logger.info("\n>>> APP-LEVEL MENUS (tous les menus racines) :\n")
    for menu in root_menus:
        xml_ids = menu.get_external_id()
        xml_id = xml_ids.get(menu.id) or f'(no_xml_id, db_id={menu.id})'
        if menu.groups_id:
            groups_str = ' | '.join(
                f'{g.full_name} [{g.category_id.name}/{g.name}]'
                for g in menu.groups_id
            )
            flag = "⚠ base.group_user" if 'base.group_user' in [g.xml_id for g in menu.groups_id] else "OK"
        else:
            groups_str = "AUCUN GROUPE — visible par tous"
            flag = "⚠ NO GROUP"

        _logger.info(
            "  [%s] seq=%-4s | xml=%-55s | %s | groupes: %s",
            flag, menu.sequence, xml_id, menu.name, groups_str,
        )

    # ── 2. Pour chaque user interne actif ────────────────────────────────────
    _logger.info("\n>>> USERS INTERNES — groupes + menus visibles :\n")
    users = env['res.users'].search(
        [('share', '=', False), ('active', '=', True)],
        order='name asc',
    )

    for user in users:
        biz_groups = user.groups_id.filtered(
            lambda g: g.category_id and g.category_id.name not in (
                'Technical', 'Extra Rights', 'Hidden'
            )
        )
        groups_str = ', '.join(sorted(g.full_name for g in biz_groups)) or '(aucun groupe métier)'

        visible = []
        for menu in root_menus:
            if not menu.groups_id or (menu.groups_id & user.groups_id):
                visible.append(menu.name)

        _logger.info("  USER : %-30s login=%s", user.name, user.login)
        _logger.info("    groupes : %s", groups_str)
        _logger.info("    menus   : %s", ' | '.join(visible) if visible else '(aucun)')
        _logger.info("")

    _logger.info(SEP)
    _logger.info("FIN DIAGNOSTIC")
    _logger.info(SEP)
