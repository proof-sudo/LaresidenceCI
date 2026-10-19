# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProductDuplicateWizard(models.TransientModel):
    _name = 'product.duplicate.wizard'
    _description = 'Détection et suppression des produits en doublon'

    line_ids = fields.One2many(
        'product.duplicate.wizard.line',
        'wizard_id',
        string='Produits en doublon',
    )
    total_duplicates = fields.Integer(
        compute='_compute_totals',
        string='Total doublons trouvés',
    )
    selected_count = fields.Integer(
        compute='_compute_totals',
        string='Sélectionnés pour suppression',
    )

    @api.depends('line_ids.to_delete')
    def _compute_totals(self):
        for rec in self:
            rec.total_duplicates = len(rec.line_ids)
            rec.selected_count = len(rec.line_ids.filtered('to_delete'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res['line_ids'] = self._find_duplicates()
        return res

    def _find_duplicates(self):
        """
        Recherche tous les product.template actifs dont le nom apparaît
        plus d'une fois. Retourne une liste de valeurs (0, 0, {...}) pour
        le champ One2many.

        Stratégie par défaut : conserver le produit avec le plus petit id
        (le plus ancien), et pré-cocher les autres pour suppression.
        """
        self.env.cr.execute("""
            WITH dup_names AS (
                SELECT name
                FROM product_template
                WHERE active = TRUE
                GROUP BY name
                HAVING COUNT(*) > 1
            )
            SELECT
                pt.id                                          AS product_tmpl_id,
                pt.name                                        AS duplicate_name,
                COALESCE(pt.default_code, '')                  AS default_code,
                pt.create_date                                 AS create_date,
                MIN(pt.id) OVER (PARTITION BY pt.name)         AS first_id,
                COUNT(pt.id) OVER (PARTITION BY pt.name)       AS group_size
            FROM product_template pt
            JOIN dup_names dn ON dn.name = pt.name
            ORDER BY pt.name, pt.id
        """)
        rows = self.env.cr.fetchall()
        lines = []
        for tmpl_id, dup_name, default_code, create_date, first_id, group_size in rows:
            lines.append((0, 0, {
                'product_tmpl_id': tmpl_id,
                'duplicate_name': dup_name,
                'default_code': default_code,
                'create_date': create_date,
                'group_size': group_size,
                # Par défaut : garder le premier (id le plus bas), supprimer les autres
                'to_delete': tmpl_id != first_id,
            }))
        return lines

    def action_refresh(self):
        """Relancer la détection (utile après modifications manuelles)."""
        self.line_ids.unlink()
        self.line_ids = self._find_duplicates()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_select_all(self):
        """Cocher tous les doublons (garder seulement le premier de chaque groupe)."""
        for line in self.line_ids:
            line.to_delete = True
        # Décocher le premier de chaque groupe
        seen = {}
        for line in self.line_ids.sorted('product_tmpl_id'):
            name = line.duplicate_name
            if name not in seen:
                seen[name] = line
                line.to_delete = False

    def action_deselect_all(self):
        """Décocher toutes les cases."""
        self.line_ids.write({'to_delete': False})

    def action_archive(self):
        """
        Archiver les produits sélectionnés (action réversible, recommandée).
        Les produits archivés n'apparaissent plus dans les recherches
        mais leurs données historiques (commandes, mouvements) sont préservées.
        """
        selected = self.line_ids.filtered('to_delete')
        if not selected:
            raise UserError(_("Aucun produit sélectionné."))
        products = selected.mapped('product_tmpl_id')
        products.write({'active': False})
        count = len(products)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Archivage réussi"),
                'message': _("%d produit(s) archivé(s) avec succès.", count),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_delete(self):
        """
        Supprimer définitivement les produits sélectionnés.
        Échoue si un produit est lié à des commandes, mouvements de stock, etc.
        Dans ce cas, utilisez l'archivage.
        """
        selected = self.line_ids.filtered('to_delete')
        if not selected:
            raise UserError(_("Aucun produit sélectionné."))
        products = selected.mapped('product_tmpl_id')
        try:
            count = len(products)
            products.unlink()
        except Exception as e:
            raise UserError(
                _("Impossible de supprimer certains produits car ils sont "
                  "référencés dans des commandes, factures ou mouvements de stock.\n\n"
                  "Conseil : utilisez le bouton « Archiver » à la place — "
                  "les produits seront masqués sans perdre l'historique.\n\n"
                  "Détail technique : %s") % str(e)
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Suppression réussie"),
                'message': _("%d produit(s) supprimé(s) définitivement.", count),
                'type': 'success',
                'sticky': False,
            },
        }


class ProductDuplicateWizardLine(models.TransientModel):
    _name = 'product.duplicate.wizard.line'
    _description = 'Ligne de doublon de produit'
    _order = 'duplicate_name, product_tmpl_id'

    wizard_id = fields.Many2one('product.duplicate.wizard', ondelete='cascade')
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Produit',
        readonly=True,
    )
    duplicate_name = fields.Char(string='Nom en doublon', readonly=True)
    default_code = fields.Char(string='Réf. interne', readonly=True)
    create_date = fields.Datetime(string='Créé le', readonly=True)
    group_size = fields.Integer(string='Nb occurrences', readonly=True)
    to_delete = fields.Boolean(string='À supprimer', default=False)
