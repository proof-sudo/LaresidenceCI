/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { _t } from "@web/core/l10n/translation";

/**
 * EposDirectKitchenPrinter — Ticket cuisine/bar ePOS direct (réseau local).
 *
 * Flux :
 *   1. orm.call → serveur Odoo filtre les lignes, génère XML + retourne l'IP
 *   2. fetch() → navigateur envoie le XML directement à l'imprimante (~2ms)
 */
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

        let result;
        try {
            result = await this.pos.env.services.orm.call(
                'pos.printer', '_get_epos_kitchen_xml', [this.printerId, orderId]
            );
        } catch (err) {
            return this._error(_t("Erreur serveur"), err?.message || _t("Impossible de contacter Odoo."));
        }

        if (!result?.success) {
            return this._error(_t("Erreur impression cuisine"), result?.message || _t("Erreur inconnue."));
        }

        // Aucune ligne pour cette station — pas une erreur
        if (!result.xml) {
            return { successful: true };
        }

        return this._sendToDevice(result.ip, result.xml);
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
                return this._error(_t("Erreur imprimante"), _t("Code: %s", code));
            }
        } catch (_) {
            // Firmware Epson sans XML valide — on ignore
        }

        return { successful: true };
    }

    _error(title, body) {
        return { successful: false, message: { title, body } };
    }
}
