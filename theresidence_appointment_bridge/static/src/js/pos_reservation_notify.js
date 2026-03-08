/** @odoo-module */

/**
 * TR Bridge — Notification POS pour nouvelles réservations
 *
 * Enregistre un service via le registry Odoo (pas de dépendance sur PosStore).
 * Fonctionne dans le contexte POS d'Odoo 17-19.
 */

import { registry } from "@web/core/registry";

// ─────────────────────────────────────────────────────────────
// Bip sonore — deux tons via Web Audio API
// ─────────────────────────────────────────────────────────────
function playBip() {
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
    } catch {
        // Son optionnel — jamais bloquant
    }
}

// ─────────────────────────────────────────────────────────────
// Service TR Notification
// ─────────────────────────────────────────────────────────────
const trReservationNotifyService = {
    dependencies: ["bus_service", "notification"],

    start(env, { bus_service, notification }) {
        try {
            bus_service.addChannel("tr_reservation_notifications");

            bus_service.addEventListener("notification", (event) => {
                const notifications = event.detail || [];
                for (const notif of notifications) {
                    if (notif.type === "new_reservation") {
                        const data = notif.payload || notif;
                        const msg = [
                            data.member || "Membre",
                            "→",
                            data.space || "Espace",
                            data.start ? "à " + data.start : "",
                        ].filter(Boolean).join(" ");

                        notification.add(msg, {
                            title: "Nouvelle réservation",
                            type: "warning",
                            sticky: false,
                        });

                        playBip();
                    }
                }
            });

            console.info("[TR BRIDGE] Service notification réservation actif");
        } catch (e) {
            console.warn("[TR BRIDGE] Échec démarrage service notification :", e);
        }
    },
};

registry.category("services").add("tr_reservation_notify", trReservationNotifyService);
