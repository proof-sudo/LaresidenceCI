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

    @api.depends('groups_id')
    def _compute_tr_groups(self):
        groups = {
            fname: self._get_tr_group(xmlid)
            for fname, xmlid in GROUP_XMLIDS.items()
        }
        for user in self:
            for fname, group in groups.items():
                user[fname] = bool(group and group in user.groups_id)

    def _set_tr_group(self, fname):
        xmlid = GROUP_XMLIDS[fname]
        group = self._get_tr_group(xmlid)
        if not group:
            return
        for user in self:
            if user[fname]:
                user.groups_id = [(4, group.id)]
            else:
                user.groups_id = [(3, group.id)]
