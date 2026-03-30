/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { _t } from "@web/core/l10n/translation";

/**
 * EposDirectPrinter — Imprimante reçu CLIENT ePOS directe.
 *
 * Bypasse entièrement html2canvas : au lieu de convertir le reçu HTML en image,
 * on envoie l'ID de la commande au serveur Odoo qui génère le XML ePOS texte
 * natif et l'envoie directement à l'imprimante.
 *
 * Type imprimante : 'epos_direct'
 * Méthode serveur : pos.printer._send_epos_receipt(printer_id, order_id)
 */
export class EposDirectPrinter extends BasePrinter {

    setup({ config, pos }) {
        super.setup(...arguments);
        this.printerId = config.id;
        this.pos = pos;
    }

    /**
     * Surcharge printReceipt pour bypasser html2canvas.
     * Le paramètre `receipt` (HTMLElement) est ignoré volontairement —
     * on utilise l'ordre courant du POS store.
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
                _t("La commande n'est pas encore enregistrée sur le serveur. Veuillez attendre la fin du paiement.")
            );
        }

        return this._callServer('_send_epos_receipt', orderId);
    }

    /**
     * Non utilisée (pas d'impression par image dans ce mode).
     * @override
     */
    sendPrintingJob(_img) {
        return Promise.resolve(true);
    }

    // ── Utilitaires ──────────────────────────────────────────────────────────

    async _callServer(method, orderId) {
        try {
            const result = await this.pos.env.services.orm.call(
                'pos.printer',
                method,
                [this.printerId, orderId],
            );

            if (!result || !result.success) {
                return this._error(
                    _t("Erreur d'impression"),
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

    _error(title, body) {
        return { successful: false, message: { title, body } };
    }
}
