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
                'pos.printer', '_get_epos_kitchen_xml', [this.printerId, orderId]
            );
        } catch (err) {
            this._log('kitchen', 'error', Math.round(performance.now() - t0), '', err?.message || 'Erreur serveur', order.name);
            return this._error(_t("Erreur serveur"), err?.message || _t("Impossible de contacter Odoo."));
        }

        if (!result?.success) {
            this._log('kitchen', 'error', Math.round(performance.now() - t0), result?.ip || '', result?.message || '', order.name);
            return this._error(_t("Erreur impression cuisine"), result?.message || _t("Erreur inconnue."));
        }

        // Aucune ligne pour cette station
        if (!result.xml) {
            return { successful: true };
        }

        const printResult = await this._sendToDevice(result.ip, result.xml);
        const duration = Math.round(performance.now() - t0);

        if (printResult.successful) {
            this._log('kitchen', 'success', duration, result.ip, '', order.name);
        } else {
            this._log('kitchen', 'error', duration, result.ip, printResult.message?.body || '', order.name);
        }

        return printResult;
    }

    sendPrintingJob(_img) {
        return Promise.resolve(true);
    }

    async _sendToDevice(ip, xmlStr) {
        const baseUrl = ip.startsWith('http') ? ip : 'http://' + ip;
        const url = baseUrl.replace(/\/$/, '') + '/cgi-bin/epos/service.cgi';

        let resp;
        try {
            resp = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'text/xml; charset=utf-8',
                    'If-Modified-Since': 'Thu, 01 Jan 1970 00:00:00 GMT',
                },
                body: xmlStr,
            });
        } catch (err) {
            return this._error(
                _t("Imprimante cuisine inaccessible"),
                _t("Vérifiez que l'imprimante est allumée et sur le même réseau. (%s)", ip)
            );
        }

        if (!resp.ok) {
            return this._error(_t("Erreur imprimante"), _t("HTTP %s", resp.status));
        }

        try {
            const text = await resp.text();
            const doc = new DOMParser().parseFromString(text, 'text/xml');
            const response = doc.querySelector('response');
            if (response && response.getAttribute('success') === 'false') {
                const code = response.getAttribute('code') || '?';
                return this._error(_t("Erreur imprimante"), _t("Code Epson: %s", code));
            }
        } catch (_) { /* firmware sans XML valide */ }

        return { successful: true };
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
