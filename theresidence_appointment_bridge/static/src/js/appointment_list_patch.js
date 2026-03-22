/** @odoo-module */

/**
 * Patch de la vue liste POS Appointments pour :
 * - Afficher le nom complet (espace — client) sans troncature
 * - Afficher la date en plus de l'heure
 */

// Injection CSS directe en fallback pour cibler les bons éléments au runtime
const style = document.createElement("style");
style.textContent = `
    /* Cible générique : tout élément de texte dans un item appointment */
    .o_appointment_booking_list .fw-bolder,
    .o_appointment_booking_list .text-truncate,
    .o_appointment_booking_list [class*="name"],
    .o_appointment_booking_list span.fw-bold,
    .o_pos_appointment [class*="name"],
    .o_pos_appointment .text-truncate {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        word-break: break-word !important;
        font-size: 11px !important;
        line-height: 1.4 !important;
    }
    /* Cartes flexibles en hauteur */
    .o_appointment_booking_list .card,
    .o_appointment_booking_list li,
    .o_appointment_booking_list [class*="item"] {
        height: auto !important;
        min-height: 0 !important;
    }
`;
document.head.appendChild(style);
