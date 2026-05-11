from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_show_contact_details = fields.Boolean(
        compute='_compute_show_contact_details',
        string='Afficher coordonnées',
    )

    @api.depends('supplier_rank', 'employee_ids')
    def _compute_show_contact_details(self):
        full_access = self.env.user.has_group(
            'laresidence_menu_security.group_contacts_full_details'
        )
        for partner in self:
            if full_access:
                partner.x_show_contact_details = True
            else:
                is_supplier = partner.supplier_rank > 0
                is_employee = bool(partner.sudo().employee_ids)
                partner.x_show_contact_details = is_supplier or is_employee
