from odoo import models


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    def _get_bom_finished_products(self, boms):
        """Retourne les produits finis des BoMs données."""
        finished = boms.mapped('product_id').filtered(lambda p: p.id)
        boms_no_variant = boms.filtered(lambda b: not b.product_id)
        if boms_no_variant:
            finished |= boms_no_variant.mapped(
                'product_tmpl_id.product_variant_id'
            ).filtered(lambda p: p.id)
        return finished

    def _trigger_bom_cost_cascade(self, boms):
        """
        Recalcule le coût des produits finis des BoMs données,
        puis cascade vers toutes les nomenclatures parentes.
        """
        finished = self._get_bom_finished_products(boms)
        if not finished:
            return
        # Recalculer le coût des produits finis directement impactés.
        # Le flag _no_bom_cost_cascade évite que le write() de standard_price
        # déclenche une 2e cascade en parallèle depuis product_product.py.
        finished.with_context(_no_bom_cost_cascade=True).button_bom_cost()
        # Puis cascader vers les BoMs parentes (niveaux supérieurs)
        finished._cascade_bom_cost_update(visited_product_ids=set(finished.ids))

    def create(self, vals_list):
        lines = super().create(vals_list)
        boms = lines.mapped('bom_id')
        if boms:
            self._trigger_bom_cost_cascade(boms)
        return lines

    def write(self, vals):
        result = super().write(vals)
        # Recalculer uniquement si un champ influençant le coût a changé
        if 'product_id' in vals or 'product_qty' in vals:
            boms = self.mapped('bom_id')
            if boms:
                self._trigger_bom_cost_cascade(boms)
        return result

    def unlink(self):
        # Capturer les BoMs AVANT la suppression (après, la relation n'existe plus)
        boms = self.mapped('bom_id')
        result = super().unlink()
        # Recalculer les BoMs encore existantes
        if boms.exists():
            self._trigger_bom_cost_cascade(boms.exists())
        return result
