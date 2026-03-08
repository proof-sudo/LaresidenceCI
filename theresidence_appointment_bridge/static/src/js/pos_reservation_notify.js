odoo.define('theresidence_appointment_bridge.pos_notifications', function(require){
    "use strict";

    const Registries = require('point_of_sale.Registries');

    const PosNotificationMixin = (Component) => {
        class PosNotification extends Component {
            mounted() {
                const bus = this.env.pos.bus;
                bus.add_channel('tr_new_reservation');

                bus.on('tr_new_reservation', this, (message) => {
                    console.log('[POS] Nouvelle réservation', message);

                    // Toast simple
                    alert(`Nouvelle réservation\nMembre: ${message.member}\nEspace: ${message.space}\nHeure: ${message.start}`);

                    // Audio
                    try {
                        const audio = new Audio("/theresidence_appointment_bridge/static/src/sounds/ding.mp3");
                        audio.play();
                    } catch(e){
                        console.warn('Impossible de jouer le son', e);
                    }
                });
            }
        }
        return PosNotification;
    };

    Registries.Component.add(PosNotificationMixin);

    return PosNotificationMixin;
});