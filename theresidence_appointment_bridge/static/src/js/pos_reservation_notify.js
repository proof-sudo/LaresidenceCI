/** @odoo-module */

/**
 * TR Bridge — Notification POS pour nouvelles réservations
 *
 * Enregistre un service via le registry Odoo.
 * Fonctionne dans le contexte POS d'Odoo 17-19.
 *
 * Son : utilise le fichier WAV du module (new Audio),
 *        avec fallback Web Audio API si le fichier échoue.
 */

import { registry } from "@web/core/registry";

// ─────────────────────────────────────────────────────────────
// Son WAV via Audio API
// ─────────────────────────────────────────────────────────────
const SOUND_URL = "/theresidence_appointment_bridge/static/src/sounds/new_reservation.wav";

async function playNotificationSound() {
    try {
        const audio = new Audio(SOUND_URL);
        audio.preload = "auto";
        await audio.play();
    } catch {
        // Fallback : bip via Web Audio API
        _playWebAudioBip();
    }
}

function _playWebAudioBip() {
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
                    // Le type est défini dans le 2e arg de bus.bus._sendone (Python)
                    if (notif.type !== "new_reservation") continue;

                    const data = notif.payload || notif;
                    const parts = [
                        data.member || "Membre",
                        "→",
                        data.space || "Espace",
                    ];
                    if (data.start) parts.push("à " + data.start);
                    const msg = parts.join(" ");

                    notification.add(msg, {
                        title: "Nouvelle réservation",
                        type: "warning",
                        sticky: false,
                    });

                    playNotificationSound();
                }
            });

            console.info("[TR BRIDGE] Service notification réservation actif");
        } catch (e) {
            console.warn("[TR BRIDGE] Échec démarrage service notification :", e);
        }
    },
};

registry.category("services").add("tr_reservation_notify", trReservationNotifyService);
