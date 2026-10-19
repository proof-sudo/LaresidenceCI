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
    _device: null,
    _localIp: null,

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
        this.collectLocalIp();
        this.timer = setInterval(() => this.flush(), FLUSH_INTERVAL_MS);
        window.addEventListener("pagehide", () => this._persist());
        window.addEventListener("online", () => this.flush());
    },

    /**
     * Adresse de l'appareil sur le réseau local.
     *
     * Le serveur ne voit que l'adresse publique du restaurant : derrière un
     * même routeur, toutes les tablettes lui sont identiques. Seul le
     * navigateur connaît l'adresse interne, et il ne la livre qu'en préparant
     * une négociation réseau.
     *
     * Les navigateurs récents remplacent souvent cette adresse par un nom en
     * .local, propre à l'appareil et stable : il ne donne pas l'adresse, mais
     * il distingue tout de même deux tablettes l'une de l'autre. Le relevé est
     * lancé une fois au démarrage et mis en cache.
     */
    async collectLocalIp() {
        if (this._localIp !== null) {
            return this._localIp;
        }
        try {
            if (typeof window.RTCPeerConnection !== "function") {
                return null;
            }
            const cnx = new window.RTCPeerConnection({ iceServers: [] });
            const adresses = new Set();
            cnx.createDataChannel("");
            cnx.onicecandidate = (evenement) => {
                const texte = evenement?.candidate?.candidate || "";
                const trouve = /((?:\d{1,3}\.){3}\d{1,3}|[0-9a-f]{1,4}(?::[0-9a-f]{1,4}){7}|[0-9a-f-]+\.local)/i.exec(texte);
                if (trouve) {
                    adresses.add(trouve[1]);
                }
            };
            cnx.setLocalDescription(await cnx.createOffer());
            await new Promise((r) => setTimeout(r, 1500));
            cnx.close();
            this._localIp = [...adresses].join(", ").slice(0, 128) || null;
        } catch {
            this._localIp = null;
        }
        return this._localIp;
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
            device_label: this.deviceInfo().resume,
            device_info: JSON.stringify(this.deviceInfo().detail),
            device_local_ip: this._localIp,
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

    /**
     * Relevé matériel du poste. Calculé une seule fois par session de caisse :
     * ces caractéristiques ne changent pas d'un événement à l'autre, et le
     * recalcul à chaque ligne serait du gaspillage.
     *
     * Le décalage horaire déclaré est conservé à part : confronté à l'heure du
     * serveur, il explique la plupart des « l'heure ne correspond pas ».
     */
    deviceInfo() {
        if (this._device) {
            return this._device;
        }
        const n = window.navigator || {};
        const e = window.screen || {};
        const lire = (f, repli = null) => {
            try {
                const v = f();
                return v === undefined ? repli : v;
            } catch {
                return repli;
            }
        };
        const detail = {
            plateforme: lire(() => n.userAgentData?.platform) || lire(() => n.platform),
            mobile: lire(() => n.userAgentData?.mobile),
            marques: lire(() => (n.userAgentData?.brands || []).map((b) => `${b.brand} ${b.version}`), []),
            ecran: lire(() => `${e.width}x${e.height}`),
            fenetre: lire(() => `${window.innerWidth}x${window.innerHeight}`),
            densite: lire(() => window.devicePixelRatio),
            langue: lire(() => n.language),
            fuseau: lire(() => Intl.DateTimeFormat().resolvedOptions().timeZone),
            decalage_utc_min: lire(() => -new Date().getTimezoneOffset()),
            tactile: lire(() => (n.maxTouchPoints || 0) > 0),
            coeurs: lire(() => n.hardwareConcurrency),
            memoire_go: lire(() => n.deviceMemory),
            en_ligne: lire(() => n.onLine),
        };
        const morceaux = [
            detail.plateforme,
            detail.tactile ? "tactile" : null,
            detail.ecran,
            detail.fuseau,
        ].filter(Boolean);
        this._device = { detail, resume: morceaux.join(" · ").slice(0, 128) };
        return this._device;
    },

    /**
     * Total TTC d'une commande. `getTotalWithTax()` n'existe pas en Odoo 19 —
     * le total vit dans le champ `amount_total`. Les autres noms sont laissés
     * en repli pour ne pas dépendre d'une seule version.
     */
    totalOf(order) {
        if (!order) {
            return 0;
        }
        try {
            for (const cle of ["amount_total", "priceIncl", "totalDue"]) {
                const v = order[cle];
                if (typeof v === "number" && !Number.isNaN(v)) {
                    return v;
                }
            }
            if (typeof order.getTotalWithTax === "function") {
                return order.getTotalWithTax() || 0;
            }
        } catch {
            /* un total illisible ne doit pas empêcher l'événement de partir */
        }
        return 0;
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

    /**
     * Envoi borné dans le temps.
     *
     * À la validation d'une commande, on veut que la trace parte avant que le
     * serveur ne réécrive l'employé et l'heure d'ouverture. Mais attendre le
     * réseau à cet instant précis, c'est faire patienter le serveur devant le
     * client. On laisse donc au plus le délai indiqué, puis on rend la main :
     * la file est de toute façon conservée dans le navigateur et repart au
     * cycle suivant, rien n'est perdu.
     */
    async flushBorne(delaiMax = 1500) {
        try {
            await Promise.race([
                this.flush(true),
                new Promise((resoudre) => setTimeout(resoudre, delaiMax)),
            ]);
        } catch {
            /* l'audit ne doit jamais retarder un encaissement */
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

// Démarrage au chargement du bundle : la file laissée par une session
// précédente repart dès l'ouverture de la caisse, sans attendre qu'une
// première action ait lieu. C'est ce qui rend un redémarrage de tablette
// inoffensif pour les événements en attente.
posAudit.ensure(null);
