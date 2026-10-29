/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { _t } from "@web/core/l10n/translation";

export class EposDirectKitchenPrinter extends BasePrinter {

    setup({ config, pos }) {
        super.setup(...arguments);
        this.printerId = config.id;
        this.pos = pos;
    }

    async printReceipt(receipt) {
        const order = this.pos.get_order();
        if (!order) {
            return this._error(_t("Aucune commande active"), _t("Aucune commande sélectionnée."));
        }
        const orderId = order.server_id;
        if (!orderId) {
            return this._error(_t("Commande non synchronisée"), _t("Attendez la fin du paiement."));
        }

        const t0 = performance.now();
        let result;
        try {
            result = await this.pos.env.services.orm.call(
                'pos.printer', '_enqueue_epos_kitchen', [this.printerId, orderId]
            );
        } catch (err) {
            this._log('kitchen', 'error', Math.round(performance.now() - t0), '', err?.message || 'Erreur serveur', order.name);
            return this._error(_t("Erreur serveur"), err?.message || _t("Impossible de contacter Odoo."));
        }

        const duration = Math.round(performance.now() - t0);

        if (!result?.success) {
            this._log('kitchen', 'error', duration, '', result?.message || '', order.name);
            return this._error(_t("Erreur impression cuisine"), result?.message || _t("Erreur inconnue."));
        }

        // Aucune ligne pour cette station : rien à mettre en file d'attente.
        if (!result.job_id) {
            return { successful: true };
        }

        this._log('kitchen', 'success', duration, '', 'queued job_id=' + result.job_id, order.name);
        return { successful: true };
    }

    sendPrintingJob(_img) {
        return Promise.resolve(true);
    }

    /** Fire-and-forget : pas d'await, zéro impact sur la vitesse. */
    _log(jobType, status, durationMs, ip, message, orderName) {
        this.pos.env.services.orm.call('pos.printer', '_create_log', [
            this.printerId,
            { job_type: jobType, status, duration_ms: durationMs, ip, message, order_name: orderName || '' },
        ]).catch((err) => console.error('[ePOS] _create_log failed:', err));
    }

    _error(title, body) {
        return { successful: false, message: { title, body } };
    }
}
