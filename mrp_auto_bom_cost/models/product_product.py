from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def write(self, vals):
        result = super().write(vals)
        # Déclencher la cascade uniquement si standard_price a changé
        # et qu'on n'est pas déjà dans une cascade (anti-boucle infinie)
        if 'standard_price' in vals and not self.env.context.get('_no_bom_cost_cascade'):
            self._cascade_bom_cost_update(visited_product_ids=set(self.ids))
        return result

    def _cascade_bom_cost_update(self, visited_product_ids=None):
        """
        Recalcule en cascade le coût de toutes les nomenclatures parentes
        qui utilisent ces produits comme composants.

        Algorithme :
        1. Trouver toutes les BoMs dont une ligne contient ce produit
        2. Pour chaque BoM, recalculer le coût du produit fini via button_bom_cost()
        3. Cascader récursivement vers les BoMs parentes du produit fini
        """
        if visited_product_ids is None:
            visited_product_ids = set()

        # Trouver toutes les BoMs où ces produits apparaissent comme composants
        parent_boms = self.env['mrp.bom'].search([
            ('bom_line_ids.product_id', 'in', self.ids)
        ])
        if not parent_boms:
            return

        # Récupérer les produits finis associés à ces BoMs
        # Cas 1 : BoM liée à une variante spécifique
        finished_products = parent_boms.mapped('product_id').filtered(lambda p: p.id)

        # Cas 2 : BoM liée à un template sans variante spécifique → prendre la variante par défaut
        boms_no_variant = parent_boms.filtered(lambda b: not b.product_id)
        if boms_no_variant:
            default_variants = boms_no_variant.mapped(
                'product_tmpl_id.product_variant_id'
            ).filtered(lambda p: p.id)
            finished_products |= default_variants

        # Exclure les produits déjà traités pour éviter les boucles
        new_products = finished_products.filtered(
            lambda p: p.id not in visited_product_ids
        )
        if not new_products:
            return

        # Marquer ces produits comme visités
        visited_product_ids |= set(new_products.ids)

        # Recalculer le coût des produits finis à partir de leur nomenclature.
        # Le context flag _no_bom_cost_cascade empêche write() de re-déclencher
        # une cascade immédiate depuis ce même appel.
        new_products.with_context(_no_bom_cost_cascade=True).button_bom_cost()

        # Cascader vers les nomenclatures parentes des produits finis qu'on vient
        # de recalculer (leurs nouveaux prix peuvent impacter d'autres BoMs)
        new_products._cascade_bom_cost_update(visited_product_ids=visited_product_ids)
