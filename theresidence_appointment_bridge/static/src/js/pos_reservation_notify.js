/** @odoo-module */

/**
 * TR Bridge — Notification POS pour nouvelles réservations (Odoo 19)
 *
 * QUAND le popup et le son se déclenchent :
 *   → Uniquement quand une nouvelle réservation est créée depuis l'app mobile
 *     (POST /v1/external/reservations → sale.order.create() → _notify_pos_new_reservation())
 *   → JAMAIS lors d'un changement de statut (approve, checkin, cancel) : le write()
 *     ne notifie pas, seul create() le fait.
 *
 * POURQUOI canal string et non canal partenaire :
 *   → Le POS ne charge pas le module discuss. Sans discuss, le canal partenaire
 *     (user.partner_id) n'est pas souscrit automatiquement dans le bus_service POS.
 *   → Un canal string ("tr_reservation_notifications") avec addChannel() est
 *     souscrit explicitement et fonctionne de manière fiable en POS Odoo 19.
 *
 * Python côté serveur :
 *   bus.bus._sendone('tr_reservation_notifications', 'tr_new_reservation', {...})
 */

import { registry } from "@web/core/registry";

// ─────────────────────────────────────────────────────────────
// Son WAV (exclamation), fallback bip Web Audio API
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
// Service TR — compatible POS Odoo 19
// ─────────────────────────────────────────────────────────────
registry.category("services").add("tr_reservation_notify", {
    dependencies: ["bus_service", "notification"],

    start(_env, { bus_service, notification }) {
        try {
            // Souscription explicite au canal string TR.
            // addChannel() bufferise la demande jusqu'à ce que le bus soit connecté.
            bus_service.addChannel("tr_reservation_notifications");

            bus_service.addEventListener("notification", ({ detail: notifications = [] }) => {
                for (const notif of notifications) {
                    if (notif.type !== "tr_new_reservation") continue;

                    const d = notif.payload || {};
                    const body = [
                        d.member || "Membre inconnu",
                        "→",
                        d.space  || "Espace inconnu",
                        d.start  ? "à " + d.start : "",
                    ].filter(Boolean).join(" ");

                    notification.add(body, {
                        title: "Nouvelle réservation",
                        type: "warning",
                        sticky: false,
                    });

                    playNotificationSound();
                }
            });

            console.info("[TR BRIDGE] Service notification actif — canal tr_reservation_notifications");
        } catch (err) {
            console.warn("[TR BRIDGE] Échec démarrage service notification :", err);
        }
    },
});
