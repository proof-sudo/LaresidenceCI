/** @odoo-module */

import { patch } from "@web/core/utils/patch";
// Chemin relevé sur l'instance, pas supposé : le module est bien
// app/screens/..., et non app/components/screens/..., qui est le chemin du
// fichier d'un autre module. C'est ce genre d'écart qui fait qu'un patch ne
// se charge jamais, sans la moindre erreur visible.
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { ServiceDialog } from "./service_dialog";

patch(ControlButtons.prototype, {
    /**
     * Ouvre l'écran de service pour la commande en cours.
     *
     * Aucun modèle de préparation n'est chargé au démarrage de la caisse :
     * l'état est demandé au serveur à l'ouverture de cet écran. La caisse
     * démarre donc exactement comme avant.
     */
    onClickLaresidenceService() {
        const commande = this.currentOrder;
        const lignes = commande ? commande.getOrderlines() : [];
        this.dialog.add(ServiceDialog, { lignes });
    },
});
