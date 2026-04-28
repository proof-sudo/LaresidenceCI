# -*- coding: utf-8 -*-
from odoo import api, fields, models

GROUP_XMLIDS = {
    'x_tr_admin':         'theresidence_api.group_tr_admin',
    'x_tr_members':       'theresidence_api.group_tr_members',
    'x_tr_reservations':  'theresidence_api.group_tr_reservations',
    'x_tr_subscriptions': 'theresidence_api.group_tr_subscriptions',
    'x_tr_orders':        'theresidence_api.group_tr_orders',
    'x_tr_config':        'theresidence_api.group_tr_config',
}


class ResUsers(models.Model):
    _inherit = 'res.users'

    x_tr_admin = fields.Boolean(
        string='Administrateur TR',
        compute='_compute_tr_groups',
        inverse=lambda self: self._set_tr_group('x_tr_admin'),
    )
    x_tr_members = fields.Boolean(
        string='Gestionnaire Membres',
        compute='_compute_tr_groups',
        inverse=lambda self: self._set_tr_group('x_tr_members'),
    )
    x_tr_reservations = fields.Boolean(
        string='Gestionnaire Réservations',
        compute='_compute_tr_groups',
        inverse=lambda self: self._set_tr_group('x_tr_reservations'),
    )
    x_tr_subscriptions = fields.Boolean(
        string='Gestionnaire Abonnements',
        compute='_compute_tr_groups',
        inverse=lambda self: self._set_tr_group('x_tr_subscriptions'),
    )
    x_tr_orders = fields.Boolean(
        string='Gestionnaire Commandes',
        compute='_compute_tr_groups',
        inverse=lambda self: self._set_tr_group('x_tr_orders'),
    )
    x_tr_config = fields.Boolean(
        string='Configuration',
        compute='_compute_tr_groups',
        inverse=lambda self: self._set_tr_group('x_tr_config'),
    )

    def _get_tr_group(self, xmlid):
        return self.env.ref(xmlid, raise_if_not_found=False)

    @api.depends('write_date')
    def _compute_tr_groups(self):
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
            fname: (self._get_tr_group(xmlid).id
                    if self._get_tr_group(xmlid) else None)
            for fname, xmlid in GROUP_XMLIDS.items()
        }
        for user in self:
            user_groups = memberships.get(user.id, set())
            for fname, gid in group_ids.items():
                user[fname] = bool(gid and gid in user_groups)

    def _set_tr_group(self, fname):
        xmlid = GROUP_XMLIDS[fname]
        group = self._get_tr_group(xmlid)
        if not group:
            return
        for user in self:
            if user[fname]:
                user.sudo().write({'groups_id': [(4, group.id)]})
            else:
                user.sudo().write({'groups_id': [(3, group.id)]})
