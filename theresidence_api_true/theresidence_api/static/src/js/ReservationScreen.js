/** @odoo-module */

import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ReservationPanel extends Component {
    static template = "theresidence_api.ReservationPanel";
    static props = { onClose: Function };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            reservations: [],
            loading: true,
            filter: "ALL",
            dateFilter: "today",
            actionLoading: null,
        });
        onMounted(() => this.loadReservations());
    }

    async setDateFilter(df) {
        this.state.dateFilter = df;
        await this.loadReservations();
    }

    async loadReservations() {
        this.state.loading = true;
        try {
            const result = await this.orm.call("sale.order", "get_pos_reservations", [this.state.dateFilter]);
            this.state.reservations = result;
        } catch (e) {
            this.notification.add("Erreur lors du chargement des réservations", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    get filteredReservations() {
        if (this.state.filter === "ALL") {
            return this.state.reservations;
        }
        return this.state.reservations.filter((r) => r.status === this.state.filter);
    }

    setFilter(filter) {
        this.state.filter = filter;
    }

    statusLabel(status) {
        const labels = {
            PENDING: "En attente",
            APPROVED: "Approuvée",
            CHECKED_IN: "Check-in",
            CANCELLED: "Annulée",
            COMPLETED: "Terminée",
            REJECTED: "Rejetée",
        };
        return labels[status] || status;
    }

    formatTime(isoString) {
        if (!isoString) return "";
        const d = new Date(isoString);
        return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    }

    formatDate(isoString) {
        if (!isoString) return "";
        const d = new Date(isoString);
        return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" }) + " · ";
    }

    async approveReservation(reservationUuid) {
        const rec = await this._findRecordId(reservationUuid);
        if (!rec) return;
        this.state.actionLoading = reservationUuid;
        try {
            await this.orm.call("sale.order", "action_approve_reservation", [[rec]]);
            this.notification.add("Réservation approuvée", { type: "success" });
            await this.loadReservations();
        } catch (e) {
            this.notification.add(e.message || "Erreur lors de l'approbation", { type: "danger" });
        } finally {
            this.state.actionLoading = null;
        }
    }

    async checkinReservation(reservationUuid) {
        const rec = await this._findRecordId(reservationUuid);
        if (!rec) return;
        this.state.actionLoading = reservationUuid;
        try {
            await this.orm.call("sale.order", "action_checkin_reservation", [[rec]]);
            this.notification.add("Check-in effectué", { type: "success" });
            await this.loadReservations();
        } catch (e) {
            this.notification.add(e.message || "Erreur lors du check-in", { type: "danger" });
        } finally {
            this.state.actionLoading = null;
        }
    }

    async cancelReservation(reservationUuid) {
        const rec = await this._findRecordId(reservationUuid);
        if (!rec) return;
        this.state.actionLoading = reservationUuid;
        try {
            await this.orm.call("sale.order", "action_cancel_reservation", [[rec]]);
            this.notification.add("Réservation annulée", { type: "warning" });
            await this.loadReservations();
        } catch (e) {
            this.notification.add(e.message || "Erreur lors de l'annulation", { type: "danger" });
        } finally {
            this.state.actionLoading = null;
        }
    }

    async _findRecordId(uuid) {
        const records = await this.orm.searchRead(
            "sale.order",
            [["x_tr_uuid", "=", uuid]],
            ["id"],
            { limit: 1 }
        );
        if (!records.length) {
            this.notification.add("Réservation introuvable", { type: "danger" });
            return null;
        }
        return records[0].id;
    }
}
