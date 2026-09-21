/** @odoo-module */

import { useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { Chrome } from "@point_of_sale/app/pos_app";
import { ReservationPanel } from "./ReservationScreen";

patch(Chrome.prototype, {
    setup() {
        super.setup(...arguments);
        this.trState = useState({ showReservations: false });
    },
    openReservationScreen() {
        this.trState.showReservations = true;
    },
    closeReservationScreen() {
        this.trState.showReservations = false;
    },
});

patch(Chrome, {
    components: {
        ...Chrome.components,
        ReservationPanel,
    },
});
