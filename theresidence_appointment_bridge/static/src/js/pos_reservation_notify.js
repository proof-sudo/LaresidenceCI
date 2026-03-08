/** @odoo-module */

/**
 * TR Bridge — Notification POS pour nouvelles réservations
 *
 * Ce fichier :
 * 1. Écoute le canal bus `tr_reservation_notifications`
 * 2. Affiche un toast visuel (notification Odoo) quand une nouvelle réservation arrive
 * 3. Joue un son d'alerte
 *
 * Compatibilité Odoo 17-19 : utilise le patch sur PosStore.
 */

import { patch } from "@web/core/utils/patch";

// On tente d'importer PosStore depuis les deux chemins connus
let PosStore;
try {
    ({ PosStore } = await import("@point_of_sale/app/store/pos_store"));
} catch {
    try {
        ({ PosStore } = await import("@point_of_sale/js/PosModel"));
    } catch {
        PosStore = null;
    }
}

if (PosStore) {
    patch(PosStore.prototype, {
        /**
         * Override setup : on s'abonne au canal bus après init du POS.
         */
        async setup() {
            await super.setup(...arguments);
            this._subscribeReservationBus();
        },

        /**
         * Abonnement au canal bus TR.
         * Utilise l'API bus_service d'Odoo (disponible depuis Odoo 16).
         */
        _subscribeReservationBus() {
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
                            this._onNewReservation(notif.payload || notif);
                        }
                    }
                });
                console.info("[TR BRIDGE] Abonné au canal tr_reservation_notifications");
            } catch (e) {
                console.warn("[TR BRIDGE] Échec abonnement bus :", e);
            }
        },

        /**
         * Callback déclenché à chaque nouvelle réservation.
         * @param {Object} data  { member, space, start, uuid, status }
         */
        _onNewReservation(data) {
            // 1. Notification visuelle (toast Odoo)
            try {
                const notif = this.env?.services?.notification;
                if (notif) {
                    notif.add(
                        `${data.member || "Membre"} → ${data.space || "Espace"} à ${data.start || ""}`,
                        {
                            title: "🔔 Nouvelle réservation",
                            type: "warning",
                            sticky: false,
                        }
                    );
                }
            } catch (e) {
                console.warn("[TR BRIDGE] Notification toast échouée :", e);
            }

            // 2. Son d'alerte
            this._playNotificationSound();
        },

        /**
         * Joue un son d'alerte.
         * Utilise le son natif Odoo si disponible, sinon Web Audio API.
         */
        _playNotificationSound() {
            try {
                // Tentative 1 : son natif Odoo (disponible dans certaines versions)
                const sound = this.env?.services?.sound;
                if (sound?.play) {
                    sound.play("notification");
                    return;
                }

                // Tentative 2 : Web Audio API — bip simple
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = ctx.createOscillator();
                const gainNode = ctx.createGain();

                oscillator.connect(gainNode);
                gainNode.connect(ctx.destination);

                oscillator.type = "sine";
                oscillator.frequency.setValueAtTime(880, ctx.currentTime);      // La5
                oscillator.frequency.setValueAtTime(1100, ctx.currentTime + 0.1); // Do#6
                gainNode.gain.setValueAtTime(0.4, ctx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);

                oscillator.start(ctx.currentTime);
                oscillator.stop(ctx.currentTime + 0.5);
            } catch (e) {
                console.warn("[TR BRIDGE] Son d'alerte non joué :", e);
            }
        },
    });
}
