/** @odoo-module */

/**
 * MutationObserver : dès qu'un élément avec text-overflow:ellipsis
 * apparaît dans la vue POS Appointments, on supprime la troncature
 * et on réduit la police pour afficher le nom complet (espace — client).
 */

function fixTruncatedElements(root) {
    root.querySelectorAll("*").forEach((el) => {
        const computed = window.getComputedStyle(el);
        if (computed.textOverflow === "ellipsis" || computed.overflow === "hidden") {
            el.style.setProperty("text-overflow", "unset", "important");
            el.style.setProperty("overflow", "visible", "important");
            el.style.setProperty("white-space", "normal", "important");
            el.style.setProperty("word-break", "break-word", "important");
            el.style.setProperty("font-size", "11px", "important");
            el.style.setProperty("line-height", "1.4", "important");
            // Remonte sur le parent pour libérer la hauteur fixe si besoin
            const parent = el.parentElement;
            if (parent) {
                const ps = window.getComputedStyle(parent);
                if (ps.overflow === "hidden" || ps.height.endsWith("px")) {
                    parent.style.setProperty("overflow", "visible", "important");
                    parent.style.setProperty("height", "auto", "important");
                }
            }
        }
    });
}

const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
            if (node.nodeType === 1) {
                fixTruncatedElements(node);
            }
        }
    }
});

observer.observe(document.body, { childList: true, subtree: true });
