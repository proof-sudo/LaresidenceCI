/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Chrome } from "@point_of_sale/app/pos_app";

patch(Chrome.prototype, {
    openReservationScreen() {
        // Odoo 17 compatible
        if (typeof this.pos.showScreen === "function") {
            this.pos.showScreen("ReservationScreen");
        }
        // Odoo 18/19 — mutation directe de mainScreen
        else if (this.pos.mainScreen !== undefined) {
            this.pos.mainScreen.name = "ReservationScreen";
            this.pos.mainScreen.props = {};
        }
    },
});
