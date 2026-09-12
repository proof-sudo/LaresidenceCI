/** @odoo-module **/

/**
 * Collecte des événements du Point de Vente.
 *
 * Trois exigences ont guidé l'implémentation :
 *
 * 1. **Ne jamais gêner le service.** L'envoi est asynchrone et ignoré en cas
 *    d'échec réseau ; aucun appel d'audit n'est attendu par l'interface, à la
 *    seule exception de la validation d'une commande, où l'on force un vidage
 *    de la file avant de rendre la main.
 *
 * 2. **Ne rien perdre lors d'un redémarrage de tablette.** La file est
 *    recopiée dans le stockage local du navigateur à chaque modification, et
 *    relue au démarrage suivant. C'est précisément le scénario qui a fait
 *    perdre l'information lors de l'incident de la table 130.
 *
 * 3. **Ne pas se fier à l'horloge de l'appareil.** L'heure envoyée est
 *    conservée telle quelle par le serveur, à côté de son propre horodatage,
 *    pour rendre l'écart mesurable au lieu de l'ignorer.
 */

const ENDPOINT = "/laresidence/pos_audit/log";
const STORAGE_QUEUE = "laresidence_pos_audit_queue";
const STORAGE_BROWSER = "laresidence_pos_audit_browser_id";
const FLUSH_INTERVAL_MS = 5000;
const FLUSH_THRESHOLD = 25;
const MAX_BATCH = 200;
const MAX_QUEUE = 1000;

/**
 * Déduit le numéro d'appareil de la référence de commande.
 * Format Odoo 19 : `<AA><appareil>-<config>-<numéro>` — « 266-1-000010 »
 * correspond à l'année 26, appareil 6, point de vente 1, commande 10.
 */
function deviceFromReference(reference) {
    if (typeof reference !== "string") {
        return null;
    }
    const head = reference.split("-")[0];
    if (!head || head.length < 3) {
        return null;
    }
    return head.slice(2);
}

function safeGet(key) {
    try {
        return window.localStorage.getItem(key);
    } catch {
        return null;
    }
}

function safeSet(key, value) {
    try {
        window.localStorage.setItem(key, value);
    } catch {
        /* stockage indisponible (navigation privée, quota) : on continue en mémoire */
    }
}

export const posAudit = {
    pos: null,
    queue: [],
    timer: null,
    sending: false,
    deviceCache: null,
    started: false,

    // ------------------------------------------------------------------
    // Cycle de vie
    // ------------------------------------------------------------------
    ensure(pos) {
        if (pos && !this.pos) {
            this.pos = pos;
        }
        if (this.started) {
            return;
        }
        this.started = true;
        this._restore();
        this.timer = setInterval(() => this.flush(), FLUSH_INTERVAL_MS);
        window.addEventListener("pagehide", () => this._persist());
        window.addEventListener("online", () => this.flush());
    },

    browserId() {
        let id = safeGet(STORAGE_BROWSER);
        if (!id) {
            id = (window.crypto?.randomUUID?.() || String(Date.now()) + Math.random().toString(16).slice(2));
            safeSet(STORAGE_BROWSER, id);
        }
        return id;
    },

    // ------------------------------------------------------------------
    // Production d'événements
    // ------------------------------------------------------------------
    cashierOf(pos) {
        const store = pos || this.pos;
        if (!store) {
            return null;
        }
        try {
            return (typeof store.getCashier === "function" ? store.getCashier() : null) || store.cashier || null;
        } catch {
            return null;
        }
    },

    context(pos, order) {
        const store = pos || this.pos;
        const cashier = this.cashierOf(store);
        const reference = order?.pos_reference || order?.name || null;
        const device = deviceFromReference(reference);
        if (device) {
            this.deviceCache = device;
        }
        let tableName = null;
        try {
            tableName = order?.table_id?.table_number ?? null;
        } catch {
            tableName = null;
        }
        return {
            client_datetime: new Date().toISOString().slice(0, 19).replace("T", " "),
            device_identifier: device || this.deviceCache || null,
            browser_id: this.browserId(),
            config_id: store?.config?.id || null,
            session_id: store?.session?.id || store?.pos_session?.id || null,
            employee_id: cashier?.id || null,
            order_uuid: order?.uuid || null,
            order_reference: reference,
            tracking_number: order?.tracking_number || null,
            table_name: tableName,
        };
    },

    push(pos, eventType, order, extra = {}) {
        try {
            this.ensure(pos);
            const event = Object.assign(
                { event_type: eventType },
                this.context(pos, order),
                extra || {}
            );
            this.queue.push(event);
            if (this.queue.length > MAX_QUEUE) {
                this.queue = this.queue.slice(-MAX_QUEUE);
            }
            this._persist();
            if (this.queue.length >= FLUSH_THRESHOLD) {
                this.flush();
            }
        } catch {
            /* l'audit ne doit jamais interrompre le service */
        }
    },

    lineInfo(line) {
        if (!line) {
            return {};
        }
        try {
            return {
                product_id: line.product_id?.id || null,
                product_name: line.full_product_name || line.product_id?.display_name || null,
                quantity: line.qty ?? line.quantity ?? 0,
                amount: line.price_unit ?? 0,
            };
        } catch {
            return {};
        }
    },

    // ------------------------------------------------------------------
    // Transmission
    // ------------------------------------------------------------------
    async flush(force = false) {
        if (this.sending || !this.queue.length) {
            return;
        }
        this.sending = true;
        const batch = this.queue.splice(0, MAX_BATCH);
        try {
            const response = await fetch(ENDPOINT, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: { events: batch },
                }),
            });
            const payload = await response.json();
            if (!payload?.result?.success) {
                throw new Error("audit refusé par le serveur");
            }
            this._persist();
        } catch {
            // On remet le lot en tête de file : il repartira au prochain cycle.
            this.queue = batch.concat(this.queue).slice(-MAX_QUEUE);
            this._persist();
        } finally {
            this.sending = false;
        }
        if (force && this.queue.length) {
            await this.flush(false);
        }
    },

    // ------------------------------------------------------------------
    // Persistance locale
    // ------------------------------------------------------------------
    _persist() {
        safeSet(STORAGE_QUEUE, JSON.stringify(this.queue));
    },

    _restore() {
        const raw = safeGet(STORAGE_QUEUE);
        if (!raw) {
            return;
        }
        try {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed) && parsed.length) {
                this.queue = parsed.concat(this.queue).slice(-MAX_QUEUE);
            }
        } catch {
            safeSet(STORAGE_QUEUE, "[]");
        }
    },
};
