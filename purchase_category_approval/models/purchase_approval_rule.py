from odoo import models, fields


class PurchaseApprovalRule(models.Model):
    _name = 'purchase.approval.rule'
    _description = "Règle de validation achat par catégorie"
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    category_id = fields.Many2one(
        'product.category',
        string="Catégorie de produit",
        required=True,
        ondelete='cascade',
    )
    strict_category = fields.Boolean(
        string="Catégorie stricte",
        default=False,
        help=(
            "Coché : s'applique uniquement aux produits de cette catégorie exacte.\n"
            "Décoché : s'applique aussi aux produits des sous-catégories."
        ),
    )
    approver_id = fields.Many2one(
        'res.users',
        string="Manager approbateur",
        required=True,
        domain=[('share', '=', False)],
    )
