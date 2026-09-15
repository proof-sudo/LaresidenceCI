from odoo import models, fields, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    approval_request_id = fields.Many2one(
        'approval.request',
        string="Demande d'approbation",
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    approval_state = fields.Selection(
        related='approval_request_id.request_status',
        string="Statut approbation",
        store=True,
    )

    # ------------------------------------------------------------------

    def button_confirm(self):
        if self.env.context.get('skip_approval_check'):
            return super().button_confirm()

        for order in self:
            # Déjà approuvé → on laisse passer
            if order._is_approved():
                continue

            rules = order._get_applicable_rules()
            if not rules:
                continue

            # Approbation déjà en cours → bloquer sans recréer
            if order.approval_request_id and order.approval_request_id.request_status == 'pending':
                raise UserError(_(
                    "Une demande d'approbation est déjà en cours pour ce bon de commande.\n"
                    "Référence : %s"
                ) % order.approval_request_id.name)

            order._create_approval_request(rules)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Approbation requise"),
                    'message': _(
                        "Le bon de commande %s contient des produits nécessitant une validation.\n"
                        "Une demande a été envoyée à : %s"
                    ) % (order.name, ', '.join(rules.mapped('approver_id.name'))),
                    'type': 'warning',
                    'sticky': True,
                },
            }

        return super().button_confirm()

    # ------------------------------------------------------------------

    def _get_parent_category_ids(self, categ):
        """Retourne la catégorie et tous ses parents (chaîne hiérarchique)."""
        ids = []
        while categ:
            ids.append(categ.id)
            categ = categ.parent_id
        return ids

    def _get_applicable_rules(self):
        """Retourne les règles actives applicables aux produits de la commande."""
        all_rules = self.env['purchase.approval.rule'].search([('active', '=', True)])
        if not all_rules:
            return all_rules

        applicable = self.env['purchase.approval.rule']
        seen_approvers = set()

        for line in self.order_line.filtered(lambda l: l.product_id):
            categ = line.product_id.categ_id
            parent_ids = self._get_parent_category_ids(categ)

            for rule in all_rules:
                if rule.id in applicable.ids:
                    continue
                if rule.strict_category:
                    matches = rule.category_id.id == categ.id
                else:
                    matches = rule.category_id.id in parent_ids

                if matches and rule.approver_id.id not in seen_approvers:
                    applicable |= rule
                    seen_approvers.add(rule.approver_id.id)

        return applicable

    def action_view_approval_request(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.request',
            'res_id': self.approval_request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _is_approved(self):
        return (
            self.approval_request_id
            and self.approval_request_id.request_status == 'approved'
        )

    def _create_approval_request(self, rules):
        """Crée et soumet la demande d'approbation liée à ce bon de commande."""
        category = self.env.ref(
            'purchase_category_approval.approval_category_purchase_validation',
            raise_if_not_found=False,
        )
        if not category:
            raise UserError(_(
                "La catégorie d'approbation 'Validation achat' est introuvable.\n"
                "Vérifiez l'installation du module."
            ))

        approver_lines = [(0, 0, {
            'user_id': rule.approver_id.id,
            'required': True,
        }) for rule in rules]

        request = self.env['approval.request'].create({
            'name': _("Validation achat — %s") % self.name,
            'category_id': category.id,
            'request_owner_id': self.env.uid,
            'approver_ids': approver_lines,
        })

        # Lier la PO à la demande avant soumission
        request.purchase_order_id = self.id
        self.approval_request_id = request.id

        # Soumettre → notifie les approbateurs
        request.action_confirm()

        self.message_post(
            body=_(
                "Confirmation bloquée — approbation requise.<br/>"
                "Demande <b>%s</b> envoyée à : %s"
            ) % (request.name, ', '.join(rules.mapped('approver_id.name')))
        )
