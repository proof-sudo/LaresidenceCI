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

    async approveReservation(uuid) {
        this.state.actionLoading = uuid;
        try {
            await this.orm.call("sale.order", "pos_approve_reservation", [uuid]);
            this.notification.add("Réservation approuvée", { type: "success" });
            await this.loadReservations();
        } catch (e) {
            this.notification.add(
                e?.data?.message || e?.message || "Erreur lors de l'approbation",
                { type: "danger" }
            );
        } finally {
            this.state.actionLoading = null;
        }
    }

    async checkinReservation(uuid) {
        this.state.actionLoading = uuid;
        try {
            await this.orm.call("sale.order", "pos_checkin_reservation", [uuid]);
            this.notification.add("Check-in effectué", { type: "success" });
            await this.loadReservations();
        } catch (e) {
            this.notification.add(
                e?.data?.message || e?.message || "Erreur lors du check-in",
                { type: "danger" }
            );
        } finally {
            this.state.actionLoading = null;
        }
    }

    async cancelReservation(uuid) {
        this.state.actionLoading = uuid;
        try {
            await this.orm.call("sale.order", "pos_cancel_reservation", [uuid]);
            this.notification.add("Réservation annulée", { type: "warning" });
            await this.loadReservations();
        } catch (e) {
            this.notification.add(
                e?.data?.message || e?.message || "Erreur lors de l'annulation",
                { type: "danger" }
            );
        } finally {
            this.state.actionLoading = null;
        }
    }
}
