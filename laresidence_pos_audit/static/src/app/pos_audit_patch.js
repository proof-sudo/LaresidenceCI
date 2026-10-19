/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { posAudit } from "./audit_service";

/**
 * Chaque patch se contente d'observer : il appelle le comportement d'origine et
 * dépose un événement. Aucun ne modifie le résultat, aucun ne peut faire échouer
 * l'action observée (`posAudit.push` avale ses propres erreurs).
 *
 * Les points d'accroche ont été relevés sur l'instance elle-même plutôt que
 * supposés — trois d'entre eux ne sont pas là où on les attendrait :
 *
 *   - `removeOrderline` appartient au modèle de commande (PosOrder), pas au
 *     magasin ;
 *   - la validation du paiement passe par `PaymentScreen.validateOrder` ; la
 *     classe OrderPaymentValidation qui porte `finalizeValidation` existe mais
 *     n'est pas exportée par son module, donc inatteignable depuis ici ;
 *   - `clickPrintBill` est sur les boutons d'action, pas sur le magasin.
 *
 * Un patch dont la méthode cible a disparu est ignoré avec un avertissement,
 * pour qu'une évolution d'Odoo dégrade l'audit au lieu d'empêcher la caisse
 * de démarrer.
 */

function patchSi(classe, nom, implementation) {
    if (!classe || !classe.prototype) {
        console.warn(`laresidence_pos_audit : classe absente pour ${nom}, audit partiel sur ce point.`);
        return;
    }
    if (typeof classe.prototype[nom] !== "function") {
        console.warn(`laresidence_pos_audit : méthode ${nom} absente, audit partiel sur ce point.`);
        return;
    }
    patch(classe.prototype, implementation);
}

const commandeCourante = (store) =>
    (store && typeof store.getOrder === "function" ? store.getOrder() : null) || null;

// ---------------------------------------------------------------------------
// Ouverture et lignes
// ---------------------------------------------------------------------------
patchSi(PosStore, "createNewOrder", {
    createNewOrder(data = {}) {
        const order = super.createNewOrder(...arguments);
        posAudit.push(this, "order_open", order, {
            note: "Ouverture d'une nouvelle commande.",
        });
        return order;
    },
});

patchSi(PosStore, "addLineToCurrentOrder", {
    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        const line = await super.addLineToCurrentOrder(...arguments);
        posAudit.push(this, "line_add", commandeCourante(this), posAudit.lineInfo(line));
        return line;
    },
});

// `this` est ici la commande elle-même : le magasin vient du cache du service.
patchSi(PosOrder, "removeOrderline", {
    removeOrderline(line) {
        // Déposé avant l'appel : après, la ligne n'existe plus.
        posAudit.push(null, "line_remove", this, posAudit.lineInfo(line));
        return super.removeOrderline(...arguments);
    },
});

// ---------------------------------------------------------------------------
// Caissier
// ---------------------------------------------------------------------------
patchSi(PosStore, "setCashier", {
    setCashier(employee) {
        const precedent = posAudit.cashierOf(this);
        const resultat = super.setCashier(...arguments);
        const courant = posAudit.cashierOf(this);
        // Sans caissier précédent, il s'agit d'une prise de poste, pas d'une
        // relève : la distinction compte pour reconstituer qui tenait la caisse.
        posAudit.push(this, precedent ? "cashier_change" : "login", commandeCourante(this), {
            employee_id: courant?.id || employee?.id || null,
            old_value: precedent?.name || null,
            new_value: courant?.name || employee?.name || null,
        });
        return resultat;
    },
});

patchSi(PosStore, "checkPreviousLoggedCashier", {
    checkPreviousLoggedCashier() {
        const resultat = super.checkPreviousLoggedCashier(...arguments);
        const courant = posAudit.cashierOf(this);
        if (courant) {
            posAudit.push(this, "cashier_restore", null, {
                employee_id: courant.id,
                new_value: courant.name,
                note: "Caissier restauré depuis la mémoire du navigateur, sans saisie du code.",
            });
        }
        return resultat;
    },
});

// ---------------------------------------------------------------------------
// Table et transfert
// ---------------------------------------------------------------------------
patchSi(PosStore, "setTable", {
    async setTable(table, orderUuid = null) {
        const avant = commandeCourante(this);
        const precedente = avant?.table_id?.table_number ?? null;
        const resultat = await super.setTable(...arguments);
        posAudit.push(this, "table_set", commandeCourante(this), {
            old_value: precedente,
            new_value: table?.table_number ?? null,
        });
        return resultat;
    },
});

patchSi(PosStore, "transferOrder", {
    transferOrder(order) {
        posAudit.push(this, "order_transfer", order, {
            note: "Transfert de la commande vers une autre table.",
        });
        return super.transferOrder(...arguments);
    },
});

patchSi(PosStore, "deleteOrders", {
    async deleteOrders(orders, serverIds = [], ignoreChange = false) {
        for (const order of orders || []) {
            posAudit.push(this, "order_delete", order, {
                amount: posAudit.totalOf(order),
                note: "Suppression de la commande depuis la caisse.",
            });
        }
        await posAudit.flushBorne(1500);
        return super.deleteOrders(...arguments);
    },
});

// ---------------------------------------------------------------------------
// Impressions
// ---------------------------------------------------------------------------
patchSi(PosStore, "printReceipt", {
    async printReceipt(opts = {}) {
        const order = opts?.order || commandeCourante(this);
        posAudit.push(this, "print_receipt", order, {
            amount: posAudit.totalOf(order),
        });
        return super.printReceipt(...arguments);
    },
});

patchSi(ControlButtons, "clickPrintBill", {
    async clickPrintBill() {
        const order = commandeCourante(this.pos);
        posAudit.push(this.pos, "print_bill", order, {
            amount: posAudit.totalOf(order),
            note: "Impression de l'addition présentée au client.",
        });
        return super.clickPrintBill(...arguments);
    },
});

// ---------------------------------------------------------------------------
// Validation — seul point où l'on attend la fin de l'envoi
// ---------------------------------------------------------------------------
patchSi(PaymentScreen, "validateOrder", {
    async validateOrder(isForceValidate = false) {
        const order = this.currentOrder || null;
        posAudit.push(this.pos, "validate", order, {
            amount: posAudit.totalOf(order),
            note: "Validation du paiement et clôture de la commande.",
        });
        // La commande est sur le point d'être réécrite côté serveur — employé
        // et date d'ouverture écrasés. On s'assure que le journal est parti
        // avant que l'information d'origine ne disparaisse.
        await posAudit.flushBorne(1500);
        return super.validateOrder(...arguments);
    },
});

// ===========================================================================
// Modifications de ligne
//
// Patchées sur le modèle de ligne plutôt que sur les écrans : quantité, prix,
// remise et note passent toutes par ces quatre méthodes, quel que soit le
// bouton, le pavé numérique ou le raccourci qui les déclenche. Un seul point
// d'accroche couvre donc tous les chemins.
// ===========================================================================
patchSi(PosOrderline, "setQuantity", {
    setQuantity(quantity, keep_price) {
        const avant = this.qty;
        const resultat = super.setQuantity(...arguments);
        if (String(avant) !== String(this.qty)) {
            posAudit.push(null, "line_qty", this.order_id, Object.assign(
                posAudit.lineInfo(this), { old_value: avant, new_value: this.qty }));
        }
        return resultat;
    },
});

patchSi(PosOrderline, "setUnitPrice", {
    setUnitPrice(price) {
        const avant = this.price_unit;
        const resultat = super.setUnitPrice(...arguments);
        if (String(avant) !== String(this.price_unit)) {
            posAudit.push(null, "line_price", this.order_id, Object.assign(
                posAudit.lineInfo(this), { old_value: avant, new_value: this.price_unit }));
        }
        return resultat;
    },
});

patchSi(PosOrderline, "setDiscount", {
    setDiscount(discount) {
        const avant = this.discount;
        const resultat = super.setDiscount(...arguments);
        if (String(avant) !== String(this.discount)) {
            posAudit.push(null, "line_discount", this.order_id, Object.assign(
                posAudit.lineInfo(this), { old_value: avant, new_value: this.discount }));
        }
        return resultat;
    },
});

patchSi(PosOrderline, "setCustomerNote", {
    setCustomerNote(note) {
        const avant = this.customer_note;
        const resultat = super.setCustomerNote(...arguments);
        posAudit.push(null, "line_note", this.order_id, Object.assign(
            posAudit.lineInfo(this), { old_value: avant, new_value: note }));
        return resultat;
    },
});

// ===========================================================================
// Paiements — qui a encaissé, comment, pour quel montant
// ===========================================================================
patchSi(PaymentScreen, "addNewPaymentLine", {
    addNewPaymentLine(paymentMethod) {
        const resultat = super.addNewPaymentLine(...arguments);
        const order = this.currentOrder || null;
        posAudit.push(this.pos, "payment_add", order, {
            payment_method: paymentMethod?.name ?? null,
            amount: posAudit.totalOf(order),
            new_value: paymentMethod?.name ?? null,
            note: "Ajout d'une ligne de paiement.",
        });
        return resultat;
    },
});

patchSi(PaymentScreen, "deletePaymentLine", {
    deletePaymentLine(uuid) {
        const order = this.currentOrder || null;
        let ligne = null;
        try {
            ligne = (order?.payment_ids || []).find((p) => p.uuid === uuid) || null;
        } catch {
            ligne = null;
        }
        posAudit.push(this.pos, "payment_remove", order, {
            payment_method: ligne?.payment_method_id?.name ?? null,
            amount: ligne?.amount ?? 0,
            old_value: ligne?.payment_method_id?.name ?? null,
            note: "Retrait d'une ligne de paiement avant validation.",
        });
        return super.deletePaymentLine(...arguments);
    },
});

patchSi(PaymentScreen, "updateSelectedPaymentline", {
    updateSelectedPaymentline(amount = false) {
        const ligne = this.selectedPaymentLine || null;
        const avant = ligne?.amount ?? null;
        const resultat = super.updateSelectedPaymentline(...arguments);
        const apres = this.selectedPaymentLine?.amount ?? null;
        if (String(avant) !== String(apres)) {
            posAudit.push(this.pos, "payment_amount", this.currentOrder || null, {
                payment_method: ligne?.payment_method_id?.name ?? null,
                amount: apres ?? 0,
                old_value: avant,
                new_value: apres,
            });
        }
        return resultat;
    },
});

patchSi(PaymentScreen, "toggleIsToInvoice", {
    toggleIsToInvoice() {
        const order = this.currentOrder || null;
        const avant = order?.to_invoice ?? null;
        const resultat = super.toggleIsToInvoice(...arguments);
        posAudit.push(this.pos, "invoice_toggle", order, {
            old_value: avant,
            new_value: order?.to_invoice ?? null,
        });
        return resultat;
    },
});

// ===========================================================================
// Commande : client, couverts, tarif, notes
// ===========================================================================
patchSi(PosOrder, "setPartner", {
    setPartner(partner) {
        const avant = this.partner_id?.name ?? null;
        const resultat = super.setPartner(...arguments);
        posAudit.push(null, "partner_set", this, {
            old_value: avant,
            new_value: this.partner_id?.name ?? null,
        });
        return resultat;
    },
});

patchSi(PosOrder, "setCustomerCount", {
    setCustomerCount(count) {
        const avant = this.customer_count;
        const resultat = super.setCustomerCount(...arguments);
        posAudit.push(null, "guests_set", this, { old_value: avant, new_value: count });
        return resultat;
    },
});

patchSi(PosOrder, "setPricelist", {
    setPricelist(pricelist) {
        const avant = this.pricelist_id?.display_name ?? null;
        const resultat = super.setPricelist(...arguments);
        posAudit.push(null, "pricelist_set", this, {
            old_value: avant,
            new_value: this.pricelist_id?.display_name ?? null,
            note: "Changement de liste de prix sur une commande en cours.",
        });
        return resultat;
    },
});

patchSi(PosOrder, "setGeneralCustomerNote", {
    setGeneralCustomerNote(note) {
        const avant = this.general_customer_note;
        const resultat = super.setGeneralCustomerNote(...arguments);
        posAudit.push(null, "note_set", this, { old_value: avant, new_value: note });
        return resultat;
    },
});

patchSi(PosOrder, "setInternalNote", {
    setInternalNote(note) {
        const avant = this.internal_note;
        const resultat = super.setInternalNote(...arguments);
        posAudit.push(null, "note_set", this, {
            old_value: avant, new_value: note, note: "Note interne.",
        });
        return resultat;
    },
});

// ===========================================================================
// Cuisine, réimpression, remboursement, connexion
// ===========================================================================
patchSi(PosStore, "sendOrderInPreparation", {
    async sendOrderInPreparation(o, opts = {}) {
        posAudit.push(this, "kitchen_send", o, {
            amount: posAudit.totalOf(o),
            note: "Envoi des lignes vers les écrans de préparation.",
        });
        return super.sendOrderInPreparation(...arguments);
    },
});

patchSi(PosStore, "reprintOrder", {
    async reprintOrder() {
        const order = commandeCourante(this);
        posAudit.push(this, "reprint", order, {
            amount: posAudit.totalOf(order),
            note: "Réimpression d'un ticket déjà émis.",
        });
        return super.reprintOrder(...arguments);
    },
});

patchSi(PosStore, "showLoginScreen", {
    showLoginScreen() {
        const courant = posAudit.cashierOf(this);
        posAudit.push(this, "logout", null, {
            employee_id: courant?.id || null,
            old_value: courant?.name || null,
            note: "Retour à l'écran de connexion.",
        });
        return super.showLoginScreen(...arguments);
    },
});

patchSi(ControlButtons, "clickRefund", {
    async clickRefund() {
        const order = commandeCourante(this.pos);
        posAudit.push(this.pos, "refund", order, {
            amount: posAudit.totalOf(order),
            note: "Ouverture d'un remboursement.",
        });
        return super.clickRefund(...arguments);
    },
});

patchSi(ControlButtons, "clickFiscalPosition", {
    async clickFiscalPosition() {
        const order = commandeCourante(this.pos);
        const avant = order?.fiscal_position_id?.display_name ?? null;
        const resultat = await super.clickFiscalPosition(...arguments);
        posAudit.push(this.pos, "fiscal_position_set", commandeCourante(this.pos), {
            old_value: avant,
            new_value: commandeCourante(this.pos)?.fiscal_position_id?.display_name ?? null,
        });
        return resultat;
    },
});

patchSi(ControlButtons, "openSplitPage", {
    async openSplitPage() {
        const order = commandeCourante(this.pos);
        posAudit.push(this.pos, "order_split", order, {
            amount: posAudit.totalOf(order),
            note: "Division de l'addition entre plusieurs paiements.",
        });
        return super.openSplitPage(...arguments);
    },
});
