/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

/**
 * TR Bridge — Notification POS pour nouvelles réservations
 *
 * - Écoute le canal bus `tr_reservation_notifications`
 * - Affiche un toast visuel + joue un bip sonore quand une nouvelle
 *   réservation arrive, pour alerter la caissière.
 */
patch(PosStore.prototype, {
    /**
     * Override setup : abonnement au canal bus après initialisation du POS.
     */
    async setup() {
        await super.setup(...arguments);
        this._trSubscribeReservationBus();
    },

    /**
     * Abonnement au canal bus TR.
     */
    _trSubscribeReservationBus() {
        try {
            const busService = this.env?.services?.bus_service;
            if (!busService) {
                console.warn("[TR BRIDGE] bus_service non disponible dans le POS");
                return;
            }
            busService.addChannel("tr_reservation_notifications");
            busService.addEventListener("notification", (event) => {
                for (const notif of event.detail) {
                    if (notif.type === "new_reservation") {
                        this._trOnNewReservation(notif.payload || notif);
                    }
                }
            });
            console.info("[TR BRIDGE] Abonné au canal tr_reservation_notifications");
        } catch (e) {
            console.warn("[TR BRIDGE] Échec abonnement bus :", e);
        }
    },

    /**
     * Callback : nouvelle réservation reçue.
     * @param {Object} data  { member, space, start, uuid, status }
     */
    _trOnNewReservation(data) {
        // 1. Toast visuel
        try {
            const notif = this.env?.services?.notification;
            if (notif) {
                notif.add(
                    `${data.member || "Membre"} → ${data.space || "Espace"}${data.start ? " à " + data.start : ""}`,
                    {
                        title: "Nouvelle réservation",
                        type: "warning",
                        sticky: false,
                    }
                );
            }
        } catch (e) {
            console.warn("[TR BRIDGE] Toast échoué :", e);
        }

        // 2. Bip sonore (Web Audio API)
        this._trPlayBip();
    },

    /**
     * Bip deux tons via Web Audio API.
     * Ne lève jamais d'exception.
     */
    _trPlayBip() {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;

            const ctx = new AudioCtx();
            const gain = ctx.createGain();
            gain.connect(ctx.destination);
            gain.gain.setValueAtTime(0.35, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);

            const osc = ctx.createOscillator();
            osc.connect(gain);
            osc.type = "sine";
            osc.frequency.setValueAtTime(880, ctx.currentTime);
            osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.15);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.45);
        } catch (e) {
            // Silencieux — le son est optionnel
        }
    },
});
