/** @odoo-module **/

import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { _t } from "@web/core/l10n/translation";

/**
 * EposDirectPrinter — Reçu client ePOS direct (réseau local).
 *
 * Flux :
 *   1. orm.call → serveur Odoo génère le XML ESC/POS + retourne l'IP
 *   2. fetch() → navigateur envoie le XML directement à l'imprimante (~2ms)
 *
 * Plus de round-trip cloud pour l'impression : le serveur sert uniquement
 * à générer le XML (accès aux données commande/société).
 */
export class EposDirectPrinter extends BasePrinter {

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
                'pos.printer', '_get_epos_receipt_xml', [this.printerId, orderId]
            );
        } catch (err) {
            return this._error(_t("Erreur serveur"), err?.message || _t("Impossible de contacter Odoo."));
        }

        if (!result?.success) {
            return this._error(_t("Erreur impression"), result?.message || _t("Erreur inconnue."));
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
                _t("Imprimante inaccessible"),
                _t("Vérifiez que l'imprimante est allumée et sur le même réseau. (%s)", ip)
            );
        }

        if (!resp.ok) {
            return this._error(_t("Erreur imprimante"), _t("HTTP %s", resp.status));
        }

        // Vérification réponse XML Epson
        try {
            const text = await resp.text();
            const doc = new DOMParser().parseFromString(text, 'text/xml');
            const response = doc.querySelector('response');
            if (response && response.getAttribute('success') === 'false') {
                const code = response.getAttribute('code') || '?';
                return this._error(_t("Erreur imprimante"), _t("Code: %s", code));
            }
        } catch (_) {
            // Certains firmware Epson ne renvoient pas de XML valide — on ignore
        }

        return { successful: true };
    }

    _error(title, body) {
        return { successful: false, message: { title, body } };
    }
}
