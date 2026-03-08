/** @odoo-module */

/**
 * TR Bridge — Notification POS pour nouvelles réservations (Odoo 17/18/19)
 *
 * Principe :
 *   - Python envoie via bus.bus._sendone(user.partner_id, 'tr_new_reservation', {...})
 *   - Le canal partenaire est automatiquement souscrit par le bus_service Odoo.
 *   - Ce service écoute le flux global et filtre uniquement 'tr_new_reservation'.
 *   - Cela ne se déclenche QUE lors d'une création de réservation (create), jamais
 *     lors des changements de statut (write ne notifie pas).
 */

import { registry } from "@web/core/registry";

// ─────────────────────────────────────────────────────────────
// Son WAV, fallback bip Web Audio
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
        const Ctx = window.AudioContext || /** @type {any} */ (window).webkitAudioContext;
        if (!Ctx) return;
        const ctx = new Ctx();
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
    } catch { /* jamais bloquant */ }
}

// ─────────────────────────────────────────────────────────────
// Service enregistré dans le registry Odoo (compatible POS 17-19)
// ─────────────────────────────────────────────────────────────
registry.category("services").add("tr_reservation_notify", {
    dependencies: ["bus_service", "notification"],

    start(_env, { bus_service, notification }) {
        try {
            bus_service.addEventListener("notification", ({ detail: notifications = [] }) => {
                for (const notif of notifications) {
                    // Filtre strict : uniquement les messages envoyés par _notify_pos_new_reservation
                    if (notif.type !== "tr_new_reservation") continue;

                    const d = notif.payload || {};
                    const body = [
                        d.member  || "Membre inconnu",
                        "→",
                        d.space   || "Espace inconnu",
                        d.start   ? "à " + d.start : "",
                    ].filter(Boolean).join(" ");

                    notification.add(body, {
                        title: "Nouvelle réservation",
                        type: "warning",
                        sticky: false,
                    });

                    playNotificationSound();
                }
            });

            console.info("[TR BRIDGE] Service notification réservation actif (Odoo 19)");
        } catch (err) {
            console.warn("[TR BRIDGE] Échec démarrage service notification :", err);
        }
    },
});
