/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/navbar/navbar";

patch(Navbar.prototype, {
    showReservationScreen() {
        this.pos.showScreen("ReservationScreen");
    },
});
