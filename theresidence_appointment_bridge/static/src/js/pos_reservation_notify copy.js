/** @odoo-module */

/**
 * TR Bridge — Notification POS pour nouvelles réservations
 *
 * Écoute le canal partenaire de l'utilisateur connecté (souscrit automatiquement
 * par le bus_service Odoo). Pas besoin d'addChannel.
 *
 * Côté Python : _sendone(user.partner_id, 'tr_new_reservation', {...})
 */

import { registry } from "@web/core/registry";

// ─────────────────────────────────────────────────────────────
// Son WAV (exclamation), avec fallback Web Audio API
// ─────────────────────────────────────────────────────────────
const SOUND_URL = "/theresidence_appointment_bridge/static/src/sounds/new_reservation.wav";

async function playNotificationSound() {
    try {
        const audio = new Audio(SOUND_URL);
        audio.preload = "auto";
        await audio.play();
    } catch {
        _webAudioBip();
    }
}

function _webAudioBip() {
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
        // jamais bloquant
    }
}

// ─────────────────────────────────────────────────────────────
// Service TR Notification
// ─────────────────────────────────────────────────────────────
const trReservationNotifyService = {
    dependencies: ["bus_service", "notification"],

    start(env, { bus_service, notification }) {
        try {
            // Pas de addChannel : on écoute le canal partenaire de l'utilisateur
            // connecté, qui est souscrit automatiquement par Odoo bus_service.
            bus_service.addEventListener("notification", (event) => {
                const notifications = event.detail || [];
                for (const notif of notifications) {
                    if (notif.type !== "tr_new_reservation") continue;

                    const data = notif.payload || {};
                    const parts = [data.member || "Membre", "→", data.space || "Espace"];
                    if (data.start) parts.push("à " + data.start);

                    notification.add(parts.join(" "), {
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
