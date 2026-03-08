odoo.define('theresidence_appointment_bridge.pos_notifications_toast', function(require){
    "use strict";

    const Registries = require('point_of_sale.Registries');
    const PosGlobalState = require('point_of_sale.PosGlobalState');

    const PosGlobalStateNotifications = (superClass) => class extends superClass {
        setup() {
            super.setup?.();

            // ── Abonnement au canal tr_new_reservation ──
            this.env.bus_service.addChannel('tr_new_reservation');

            this.env.bus_service.on('tr_new_reservation', this, (message) => {
                console.log("[POS] Nouvelle réservation :", message);

                // ── Création toast flottant ──
                const toast = document.createElement('div');
                toast.style.position = 'fixed';
                toast.style.bottom = '20px';
                toast.style.right = '20px';
                toast.style.background = '#fffae6';
                toast.style.border = '1px solid #f1c40f';
                toast.style.padding = '15px 20px';
                toast.style.borderRadius = '8px';
                toast.style.boxShadow = '0 4px 6px rgba(0,0,0,0.2)';
                toast.style.zIndex = 9999;
                toast.style.fontFamily = 'Arial, sans-serif';
                toast.style.color = '#333';
                toast.style.whiteSpace = 'pre-line';
                toast.innerText = `📌 Nouvelle réservation\nMembre: ${message.member}\nEspace: ${message.space}\nHeure: ${message.start}`;

                document.body.appendChild(toast);

                setTimeout(() => {
                    toast.remove();
                }, 5000);

                // ── Lecture audio intégré en base64 ──
                try {
                    const audioData = "data:audio/mp3;base64,//uQxAA..."; // Remplace par ton base64 réel
                    const audio = new Audio(audioData);
                    audio.play().catch(err => console.warn('Impossible de jouer le son POS', err));
                } catch(e) {
                    console.warn('Erreur audio POS', e);
                }
            });
        }
    };

    Registries.Component.extend(PosGlobalState, PosGlobalStateNotifications);
});