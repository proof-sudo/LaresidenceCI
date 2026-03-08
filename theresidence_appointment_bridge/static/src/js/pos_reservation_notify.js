/** @odoo-module */

/**
 * TR Bridge — Notification POS (Odoo 19) par polling ORM
 *
 * Le bus WebSocket d'Odoo.com ne dispatche pas les canaux string custom
 * sans autorisation serveur explicite. On utilise donc un polling ORM
 * (même mécanisme que ReservationScreen.js) : toutes les 10s on compare
 * les réservations PENDING du jour avec celles déjà vues.
 *
 * Python (_notify_pos_new_reservation) reste actif comme tentative rapide,
 * le polling sert de filet de sécurité garanti.
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

function formatTime(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

// ─────────────────────────────────────────────────────────────
// Patch Chrome — polling toutes les 10s
// ─────────────────────────────────────────────────────────────
patch(Chrome.prototype, {
    setup() {
        super.setup(...arguments);

        const orm = useService("orm");
        const notification = useService("notification");

        let seenIds = new Set();
        let pollTimer = null;

        onMounted(async () => {
            // Snapshot initial : on mémorise les réservations existantes
            // pour ne PAS notifier celles qui étaient déjà là au démarrage.
            try {
                const existing = await orm.call("sale.order", "get_pos_reservations", ["today"]);
                for (const r of existing) seenIds.add(r.id);
                console.info(`[TR BRIDGE] Polling actif — ${seenIds.size} réservation(s) connue(s)`);
            } catch (e) {
                console.warn("[TR BRIDGE] Snapshot initial échoué:", e);
            }

            // Polling toutes les 10 secondes
            pollTimer = setInterval(async () => {
                try {
                    const current = await orm.call("sale.order", "get_pos_reservations", ["today"]);

                    // Nouvelles réservations PENDING non encore vues
                    const newOnes = current.filter(
                        (r) => !seenIds.has(r.id) && r.status === "PENDING"
                    );

                    // Marquer toutes comme vues (même les non-PENDING)
                    for (const r of current) seenIds.add(r.id);

                    for (const res of newOnes) {
                        const member = [res.memberFirstName, res.memberLastName]
                            .filter(Boolean).join(" ") || "Membre";
                        const body = `${member} → ${res.spaceName || "Espace"}${
                            res.startTime ? " à " + formatTime(res.startTime) : ""
                        }`;

                        notification.add(body, {
                            title: "Nouvelle réservation",
                            type: "warning",
                            sticky: false,
                        });

                        playNotificationSound();
                        console.info("[TR BRIDGE] Nouvelle réservation détectée:", res.id);
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
