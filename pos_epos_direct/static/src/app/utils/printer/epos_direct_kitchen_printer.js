/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { _t } from "@web/core/l10n/translation";

/**
 * EposDirectKitchenPrinter — Imprimante ticket CUISINE / BAR ePOS directe.
 *
 * Conçue pour les imprimantes de station (cuisine, bar, grill, etc.).
 * Génère un ticket de préparation côté serveur :
 *   - Filtre les lignes selon les catégories configurées sur l'imprimante
 *   - Format grand, lisible, sans prix
 *   - Affiche le numéro de table si pos_restaurant est actif
 *   - Affiche les notes de ligne et de commande
 *
 * Type imprimante : 'epos_direct_kitchen'
 * Méthode serveur : pos.printer._send_epos_kitchen_ticket(printer_id, order_id)
 */
export class EposDirectKitchenPrinter extends BasePrinter {

    setup({ config, pos }) {
        super.setup(...arguments);
        this.printerId = config.id;
        this.pos = pos;
    }

    /**
     * Surcharge printReceipt pour bypasser html2canvas.
     * Appelé par le POS chaque fois qu'une commande est envoyée en préparation.
     * Le paramètre `receipt` (HTMLElement) est ignoré — on récupère l'ordre
     * courant et on délègue la génération/envoi du ticket au serveur.
     * @override
     */
    async printReceipt(receipt) {
        const order = this.pos.get_order();

        if (!order) {
            return this._error(
                _t("Aucune commande active"),
                _t("Aucune commande n'est sélectionnée dans la caisse.")
            );
        }

        const orderId = order.server_id;
        if (!orderId) {
            return this._error(
                _t("Commande non synchronisée"),
                _t("La commande n'est pas encore enregistrée sur le serveur.")
            );
        }

        try {
            const result = await this.pos.env.services.orm.call(
                'pos.printer',
                '_send_epos_kitchen_ticket',
                [this.printerId, orderId],
            );

            // 'nothing_to_print' n'est pas une erreur — aucun article pour cette station
            if (result?.message === 'nothing_to_print') {
                return { successful: true };
            }

            if (!result || !result.success) {
                return this._error(
                    _t("Erreur d'impression cuisine"),
                    result?.message || _t("Erreur inconnue.")
                );
            }

            return { successful: true };
        } catch (err) {
            return this._error(
                _t("Erreur de connexion serveur"),
                err?.message || _t("Impossible de contacter le serveur Odoo.")
            );
        }
    }

    /**
     * Non utilisée (pas d'impression par image dans ce mode).
     * @override
     */
    sendPrintingJob(_img) {
        return Promise.resolve(true);
    }

    _error(title, body) {
        return { successful: false, message: { title, body } };
    }
}
