/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

/**
 * Le caissier encaisse, il ne facture pas.
 *
 * Deux questions, dans cet ordre, au moment où il choisit un mode de paiement :
 * la première rattrape l'erreur de mode, qui ne se corrige ensuite qu'en
 * comptabilité ; la seconde note si le client veut une facture, sans rien
 * produire. La facture est faite plus tard, par qui de droit.
 *
 * La question de la facture n'est posée qu'une fois par commande : sur un
 * paiement en deux fois, on ne redemande pas.
 */

function demander(dialog, options) {
    return new Promise((resolve) => {
        dialog.add(ConfirmationDialog, {
            title: options.titre,
            body: options.corps,
            confirmLabel: options.oui,
            cancelLabel: options.non,
            confirm: () => resolve(true),
            cancel: () => resolve(false),
        });
    });
}

patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        const bonMode = await demander(this.dialog, {
            titre: _t("Confirmer le mode de paiement"),
            corps: _t("Le client règle bien par « %s » ?", paymentMethod.name),
            oui: _t("Oui, c'est ce mode"),
            non: _t("Non, revenir"),
        });
        if (!bonMode) {
            return false;
        }

        const commande = this.currentOrder;
        if (commande && !commande.laresidence_facture_demandee) {
            const veutFacture = await demander(this.dialog, {
                titre: _t("Facture"),
                corps: _t("Le client demande-t-il une facture FNE pour cette opération ?"),
                oui: _t("Oui, il en veut une"),
                non: _t("Passer"),
            });
            if (veutFacture) {
                commande.laresidence_facture_demandee = true;
            }
        }

        return await super.addNewPaymentLine(paymentMethod);
    },

    /**
     * Le bouton est retiré du gabarit ; ceci couvre le cas où un autre module
     * le réintroduirait ailleurs.
     */
    async toggleIsToInvoice() {
        this.notification.add(
            _t("La facture ne se fait plus en caisse. Répondez à la question posée au paiement : la commande sera reprise ensuite."),
            { type: "info" }
        );
    },
});
