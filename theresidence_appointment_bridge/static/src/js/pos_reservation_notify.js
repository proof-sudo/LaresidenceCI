/** @odoo-module */

/**
 * TR Bridge — Notification POS pour nouvelles réservations (Odoo 19)
 *
 * QUAND : uniquement à la création d'une réservation depuis l'app mobile.
 *         Jamais sur les changements de statut (approve/checkin/cancel).
 *
 * PATTERN : patch de Chrome.prototype (même approche que ReservationButton.js)
 *           → useService() dans un contexte OWL component = notification.add()
 *             rendu dans le DOM POS.
 *           Un registry "service" background ne peut pas déclencher le rendu
 *           du composant NotificationList dans POS.
 *
 * CANAL : canal string "tr_reservation_notifications" souscrit via addChannel()
 *         dans onMounted(), après que le composant Chrome est monté.
 */

import { Chrome } from "@point_of_sale/app/pos_app";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onMounted } from "@odoo/owl";

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
// Patch Chrome — même pattern que ReservationButton.js
// Plusieurs patches sur Chrome.prototype sont supportés par OWL.
// ─────────────────────────────────────────────────────────────
patch(Chrome.prototype, {
    setup() {
        super.setup(...arguments);

        const busService = useService("bus_service");
        const notification = useService("notification");

        onMounted(() => {
            // addChannel() est bufferisé jusqu'à la connexion WebSocket
            busService.addChannel("tr_reservation_notifications");

            busService.addEventListener("notification", ({ detail: notifications = [] }) => {
                // DEBUG : log toutes les notifs pour diagnostiquer
                if (notifications.length) {
                    console.log("[TR BRIDGE] Bus reçu:", JSON.stringify(notifications));
                }
                for (const notif of notifications) {
                    if (notif.type !== "tr_new_reservation") continue;

                    const d = notif.payload || {};
                    const body = [
                        d.member || "Membre",
                        "→",
                        d.space  || "Espace",
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

            console.info("[TR BRIDGE] Canal bus souscrit — tr_reservation_notifications");
        });
    },
});
