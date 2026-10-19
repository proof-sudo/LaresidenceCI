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
            RESERVED: "Réservée",
            ARRIVED: "Arrivée",
            CANCELLED: "Annulée",
            COMPLETED: "Libéré",
        };
        return labels[status] || status;
    }

    _parseDate(isoString) {
        if (!isoString) return null;
        // Odoo renvoie "YYYY-MM-DDTHH:MM:SS" sans fuseau horaire (UTC implicite).
        // Sans le suffixe 'Z', new Date() l'interprète en heure locale et décale la date.
        if (/Z$|[+-]\d{2}:\d{2}$/.test(isoString)) return new Date(isoString);
        return new Date(isoString.replace(" ", "T") + "Z");
    }

    formatTime(isoString) {
        if (!isoString) return "";
        const d = this._parseDate(isoString);
        if (!d || isNaN(d)) return "";
        return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    }

    formatDate(isoString) {
        if (!isoString) return "";
        const d = this._parseDate(isoString);
        if (!d || isNaN(d)) return "";
        return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" }) + " · ";
    }

    async reserveReservation(uuid) {
        this.state.actionLoading = uuid;
        try {
            await this.orm.call("sale.order", "pos_reserve_reservation", [uuid]);
            this.notification.add("Réservation confirmée", { type: "success" });
            await this.loadReservations();
        } catch (e) {
            this.notification.add(
                e?.data?.message || e?.message || "Erreur lors de la réservation",
                { type: "danger" }
            );
        } finally {
            this.state.actionLoading = null;
        }
    }

    async arriveReservation(uuid) {
        this.state.actionLoading = uuid;
        try {
            await this.orm.call("sale.order", "pos_arrive_reservation", [uuid]);
            this.notification.add("Arrivée enregistrée", { type: "success" });
            await this.loadReservations();
        } catch (e) {
            this.notification.add(
                e?.data?.message || e?.message || "Erreur lors de l'enregistrement de l'arrivée",
                { type: "danger" }
            );
        } finally {
            this.state.actionLoading = null;
        }
    }

    async releaseReservation(uuid) {
        this.state.actionLoading = uuid;
        try {
            await this.orm.call("sale.order", "pos_release_reservation", [uuid]);
            this.notification.add("Espace libéré", { type: "success" });
            await this.loadReservations();
        } catch (e) {
            this.notification.add(
                e?.data?.message || e?.message || "Erreur lors de la libération",
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
