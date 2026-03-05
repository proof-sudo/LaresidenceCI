/** @odoo-module */

import { Component, useState, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";

export class ReservationButton extends Component {
    static template = "theresidence_api.ReservationButton";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.state = useState({ pendingCount: 0 });
        onMounted(() => this.loadCount());
    }

    async loadCount() {
        try {
            const result = await this.orm.call("sale.order", "get_pos_reservations", []);
            this.state.pendingCount = result.filter((r) => r.status === "PENDING").length;
        } catch (_) {
            // silencieux si erreur de chargement du compteur
        }
    }

    get pendingCount() {
        return this.state.pendingCount;
    }

    onClick() {
        this.pos.showScreen("ReservationScreen");
    }
}

patch(Navbar.prototype, {
    get reservationButton() {
        return ReservationButton;
    },
});

registry.category("pos_navbar_buttons").add("ReservationButton", {
    component: ReservationButton,
    condition: () => true,
});
