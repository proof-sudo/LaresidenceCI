/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { EposDirectPrinter }        from "../utils/printer/epos_direct_printer";
import { EposDirectKitchenPrinter } from "../utils/printer/epos_direct_kitchen_printer";

/**
 * Patch de PosStore.createPrinter pour instancier les classes correctes
 * selon le type d'imprimante configuré.
 *
 *   'epos_direct'         → EposDirectPrinter        (reçu client)
 *   'epos_direct_kitchen' → EposDirectKitchenPrinter  (ticket cuisine / bar)
 *
 * Tous les autres types (iot, epson_epos, etc.) passent par super.createPrinter()
 * sans aucune modification.
 */
patch(PosStore.prototype, {
    createPrinter(config) {
        switch (config.printer_type) {
            case 'epos_direct':
                return new EposDirectPrinter({ config, pos: this });
            case 'epos_direct_kitchen':
                return new EposDirectKitchenPrinter({ config, pos: this });
            default:
                return super.createPrinter(...arguments);
        }
    },
});
