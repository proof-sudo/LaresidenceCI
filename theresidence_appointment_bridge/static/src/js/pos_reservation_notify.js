/** @odoo-module */

/**
 * TR Bridge — Notification POS (Odoo 19)
 *
 * Polling toutes les 10s via get_new_pending_reservations(since_iso).
 * Filtre sur create_date (pas startTime) → fonctionne quelle que soit
 * la date de la réservation (aujourd'hui, demain, etc.).
 */

import { Chrome } from "@point_of_sale/app/pos_app";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount } from "@odoo/owl";

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
// Patch Chrome — polling toutes les 10s sur create_date
// ─────────────────────────────────────────────────────────────
patch(Chrome.prototype, {
    setup() {
        super.setup(...arguments);

        const orm = useService("orm");
        const notification = useService("notification");

        let lastCheck = new Date().toISOString();
        let pollTimer = null;

        onMounted(() => {
            console.info("[TR BRIDGE] Polling nouvelles réservations actif");

            pollTimer = setInterval(async () => {
                try {
                    const checkFrom = lastCheck;
                    lastCheck = new Date().toISOString();

                    const newOnes = await orm.call(
                        "sale.order",
                        "get_new_pending_reservations",
                        [checkFrom]
                    );

                    for (const res of newOnes) {
                        const body = [
                            res.member || "Membre",
                            "→",
                            res.space  || "Espace",
                            res.start  ? "à " + res.start : "",
                        ].filter(Boolean).join(" ");

                        notification.add(body, {
                            title: "Nouvelle réservation",
                            type: "warning",
                            sticky: false,
                        });

                        playNotificationSound();
                        console.info("[TR BRIDGE] Nouvelle réservation:", res.uuid);
                    }
                } catch {
                    // Silencieux — retry au prochain cycle
                }
            }, 10_000);
        });

        onWillUnmount(() => {
            if (pollTimer) clearInterval(pollTimer);
        });
    },
});
