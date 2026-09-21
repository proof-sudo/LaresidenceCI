/** @odoo-module */

/**
 * Enrichit les cartes de la vue liste POS Appointments :
 * - Nom complet sans troncature (espace — client splitté en 2 lignes labelisées)
 * - Date et heure planifiées avec petits libellés
 *
 * Stratégie :
 *   1. Charge les calendar.event du jour via RPC (une seule fois)
 *   2. MutationObserver détecte les cartes dès leur apparition dans le DOM
 *   3. Restructure le contenu de chaque carte avec labels stylisés
 */

// ─── Données chargées une fois ─────────────────────────────────────────────
/** Map  name → { start, stop }  pour lookup rapide */
const eventMap = new Map();
let dataLoaded = false;

async function loadEventData() {
    if (dataLoaded) return;
    dataLoaded = true;
    try {
        const resp = await fetch("/web/dataset/call_kw", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                id: 1,
                method: "call",
                params: {
                    model: "calendar.event",
                    method: "search_read",
                    args: [[["appointment_type_id", "!=", false]]],
                    kwargs: {
                        fields: ["name", "start", "stop"],
                        limit: 500,
                        context: {},
                    },
                },
            }),
        });
        const data = await resp.json();
        if (data.result) {
            data.result.forEach((ev) => eventMap.set(ev.name, ev));
        }
    } catch (e) {
        console.warn("[TR BRIDGE] Impossible de charger les calendar.events :", e);
    }
}

// ─── Formatage ──────────────────────────────────────────────────────────────
/**
 * Odoo renvoie les Datetime en JSON sous la forme "YYYY-MM-DD HH:MM:SS" (espace, pas 'T', pas 'Z').
 * new Date("YYYY-MM-DD HH:MM:SS") est interprété en HEURE LOCALE par les navigateurs,
 * ce qui décale la date si le serveur est en UTC et le client dans un autre fuseau.
 * On normalise en remplaçant l'espace par 'T' et en ajoutant 'Z' (UTC explicite).
 */
function parseOdooDatetime(str) {
    if (!str) return null;
    // Déjà UTC explicite (se termine par Z ou +HH:MM)
    if (/Z$|[+-]\d{2}:\d{2}$/.test(str)) return new Date(str);
    // Format Odoo "YYYY-MM-DD HH:MM:SS" ou ISO sans fuseau "YYYY-MM-DDTHH:MM:SS"
    return new Date(str.replace(" ", "T") + "Z");
}

function formatDate(isoStr) {
    if (!isoStr) return "";
    const d = parseOdooDatetime(isoStr);
    if (!d || isNaN(d)) return "";
    return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

function formatTime(isoStr) {
    if (!isoStr) return "";
    const d = parseOdooDatetime(isoStr);
    if (!d || isNaN(d)) return "";
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

// ─── Injection HTML dans un élément ─────────────────────────────────────────
const ENHANCED_ATTR = "data-tr-enhanced";

function enhanceElement(el) {
    if (el.getAttribute(ENHANCED_ATTR)) return;
    const text = el.textContent.trim();
    if (!text.includes(" — ")) return;

    const [space, client] = text.split(" — ");
    const ev = eventMap.get(text);

    let dateHtml = "";
    if (ev) {
        const date = formatDate(ev.start);
        const start = formatTime(ev.start);
        const stop = formatTime(ev.stop);
        dateHtml = `<div class="tr-row"><span class="tr-lbl">Prévu</span><span class="tr-val">${date} · ${start}${stop ? " – " + stop : ""}</span></div>`;
    }

    el.setAttribute(ENHANCED_ATTR, "1");
    el.style.setProperty("white-space", "normal", "important");
    el.style.setProperty("overflow", "visible", "important");
    el.style.setProperty("text-overflow", "unset", "important");
    el.style.setProperty("height", "auto", "important");

    el.innerHTML = `
        <div class="tr-row"><span class="tr-lbl">Espace</span><span class="tr-val">${space.trim()}</span></div>
        <div class="tr-row"><span class="tr-lbl">Client</span><span class="tr-val">${(client || "").trim()}</span></div>
        ${dateHtml}
    `;

    // Libère aussi les parents qui pourraient clipper le contenu
    let p = el.parentElement;
    for (let i = 0; i < 4 && p; i++, p = p.parentElement) {
        const cs = window.getComputedStyle(p);
        if (cs.overflow === "hidden" || (cs.height && parseInt(cs.height) < 60)) {
            p.style.setProperty("overflow", "visible", "important");
            p.style.setProperty("height", "auto", "important");
            p.style.setProperty("max-height", "none", "important");
        }
    }
}

// ─── MutationObserver ────────────────────────────────────────────────────────
function scanNode(root) {
    root.querySelectorAll("*").forEach((el) => {
        // Fixe la troncature CSS native
        const cs = window.getComputedStyle(el);
        if (cs.textOverflow === "ellipsis") {
            el.style.setProperty("text-overflow", "unset", "important");
            el.style.setProperty("white-space", "normal", "important");
            el.style.setProperty("overflow", "visible", "important");
        }
        // Enrichit les éléments contenant "Space — Client"
        if (el.children.length === 0) {
            enhanceElement(el);
        }
    });
}

const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
            if (node.nodeType === 1) {
                // Charge les données lazily au premier rendu d'une carte
                loadEventData().then(() => scanNode(node));
            }
        }
    }
});

function startObserver() {
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
    } else {
        document.addEventListener("DOMContentLoaded", () => {
            observer.observe(document.body, { childList: true, subtree: true });
        });
    }
}

startObserver();
