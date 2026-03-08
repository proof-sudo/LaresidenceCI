odoo.define('theresidence_appointment_bridge.pos_notifications', function (require) {
    "use strict";

    const { Gui } = require('point_of_sale.Gui');
    const PosGlobalState = require('point_of_sale.PosGlobalState');

    function playSound() {
        // On joue le fichier .wave au lieu du mp3
        const audio = new Audio('/theresidence_appointment_bridge/static/src/sounds/new_reservation.wav');
        audio.play().catch(() => {});
    }

    function showToast(msg) {
        Gui.showPopup('Toast', {
            title: "Nouvelle réservation",
            body: `Espace: ${msg.space}\nMembre: ${msg.member}\nHeure: ${msg.start}`,
        });
        playSound();
    }

    // On attend que le bus soit prêt
    PosGlobalState.on('change:bus', function (bus) {
        if (bus) {
            bus.on('tr_new_reservation', showToast);
        }
    });
});