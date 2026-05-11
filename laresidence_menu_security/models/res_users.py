from odoo import api, fields, models

GROUP_CONTACTS = {
    'x_contacts_full_details': 'laresidence_menu_security.group_contacts_full_details',
    'x_contacts_can_create':   'base.group_partner_manager',
}


class ResUsers(models.Model):
    _inherit = 'res.users'

    x_contacts_full_details = fields.Boolean(
        string='Coordonnées complètes (clients inclus)',
        compute='_compute_contact_groups',
        inverse=lambda self: self._set_contact_group('x_contacts_full_details'),
    )
    x_contacts_can_create = fields.Boolean(
        string='Peut créer / modifier des contacts',
        compute='_compute_contact_groups',
        inverse=lambda self: self._set_contact_group('x_contacts_can_create'),
    )

    def _get_contact_group(self, xmlid):
        return self.env.ref(xmlid, raise_if_not_found=False)

    @api.depends('write_date')
    def _compute_contact_groups(self):
        if not self.ids:
            return
        self.env.cr.execute(
            "SELECT r.uid, r.gid FROM res_groups_users_rel r WHERE r.uid IN %s",
            (tuple(self.ids),)
        )
        memberships = {}
        for uid, gid in self.env.cr.fetchall():
            memberships.setdefault(uid, set()).add(gid)

        group_ids = {
            fname: (self._get_contact_group(xmlid).id if self._get_contact_group(xmlid) else None)
            for fname, xmlid in GROUP_CONTACTS.items()
        }
        for user in self:
            user_groups = memberships.get(user.id, set())
            for fname, gid in group_ids.items():
                user[fname] = bool(gid and gid in user_groups)

    def _set_contact_group(self, fname):
        xmlid = GROUP_CONTACTS[fname]
        group = self._get_contact_group(xmlid)
        if not group:
            return
        for user in self:
            if user[fname]:
                self.env.cr.execute(
                    "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (group.id, user.id),
                )
            else:
                self.env.cr.execute(
                    "DELETE FROM res_groups_users_rel WHERE gid = %s AND uid = %s",
                    (group.id, user.id),
                )
        self.env.cr.execute(
            "UPDATE res_users SET write_date = NOW() WHERE id IN %s",
            (tuple(self.ids),),
        )
        self.invalidate_recordset(list(GROUP_CONTACTS.keys()) + ['write_date'])
        self.env.registry.clear_cache()
