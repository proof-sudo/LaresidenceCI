/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
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
        posAudit.push(this, "cashier_change", commandeCourante(this), {
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
        await posAudit.flush(true);
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
        await posAudit.flush(true);
        return super.validateOrder(...arguments);
    },
});
