/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { OrderPaymentValidation } from "@point_of_sale/app/utils/order_payment_validation";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { posAudit } from "./audit_service";

/**
 * Chaque patch se contente d'observer : il appelle le comportement d'origine et
 * dépose un événement. Aucun ne modifie le résultat, aucun ne peut faire échouer
 * l'action observée (`posAudit.push` avale ses propres erreurs).
 *
 * Les méthodes dont la présence dépend d'un module tiers (table, transfert,
 * caissier) ne sont patchées que si elles existent réellement, pour que le
 * module reste installable si l'une de ces dépendances évolue.
 */

function patchIfExists(prototype, name, implementation) {
    if (typeof prototype[name] === "function") {
        patch(prototype, implementation);
    } else {
        console.warn(`laresidence_pos_audit : méthode ${name} absente, audit partiel sur ce point.`);
    }
}

// ---------------------------------------------------------------------------
// Ouverture, lignes, validation
// ---------------------------------------------------------------------------
patch(PosStore.prototype, {
    createNewOrder(data = {}) {
        const order = super.createNewOrder(...arguments);
        posAudit.push(this, "order_open", order, {
            note: "Ouverture d'une nouvelle commande.",
        });
        return order;
    },

    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        const line = await super.addLineToCurrentOrder(...arguments);
        const order = typeof this.getOrder === "function" ? this.getOrder() : null;
        posAudit.push(this, "line_add", order, posAudit.lineInfo(line));
        return line;
    },
});

patchIfExists(PosStore.prototype, "removeOrderline", {
    removeOrderline(line) {
        // Déposé avant l'appel : après, la ligne n'existe plus.
        const order = typeof this.getOrder === "function" ? this.getOrder() : null;
        posAudit.push(this, "line_remove", order, posAudit.lineInfo(line));
        return super.removeOrderline(...arguments);
    },
});

// ---------------------------------------------------------------------------
// Caissier
// ---------------------------------------------------------------------------
patchIfExists(PosStore.prototype, "setCashier", {
    setCashier(employee) {
        const previous = posAudit.cashierOf(this);
        const result = super.setCashier(...arguments);
        const current = posAudit.cashierOf(this);
        const order = typeof this.getOrder === "function" ? this.getOrder() : null;
        posAudit.push(this, "cashier_change", order, {
            employee_id: current?.id || employee?.id || null,
            old_value: previous?.name || null,
            new_value: current?.name || employee?.name || null,
        });
        return result;
    },
});

patchIfExists(PosStore.prototype, "checkPreviousLoggedCashier", {
    checkPreviousLoggedCashier() {
        const result = super.checkPreviousLoggedCashier(...arguments);
        const current = posAudit.cashierOf(this);
        if (current) {
            posAudit.push(this, "cashier_restore", null, {
                employee_id: current.id,
                new_value: current.name,
                note: "Caissier restauré depuis la mémoire du navigateur, sans saisie du code.",
            });
        }
        return result;
    },
});

// ---------------------------------------------------------------------------
// Table et transfert
// ---------------------------------------------------------------------------
patchIfExists(PosStore.prototype, "setTable", {
    async setTable(table, orderUuid = null) {
        const before = typeof this.getOrder === "function" ? this.getOrder() : null;
        const previous = before?.table_id?.table_number ?? null;
        const result = await super.setTable(...arguments);
        const order = typeof this.getOrder === "function" ? this.getOrder() : null;
        posAudit.push(this, "table_set", order, {
            old_value: previous,
            new_value: table?.table_number ?? null,
        });
        return result;
    },
});

patchIfExists(PosStore.prototype, "transferOrder", {
    transferOrder(order) {
        posAudit.push(this, "order_transfer", order, {
            note: "Transfert de la commande vers une autre table.",
        });
        return super.transferOrder(...arguments);
    },
});

patchIfExists(PosStore.prototype, "deleteOrders", {
    async deleteOrders(orders, serverIds = [], ignoreChange = false) {
        for (const order of orders || []) {
            posAudit.push(this, "order_delete", order, {
                amount: order?.getTotalWithTax?.() ?? 0,
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
patchIfExists(PosStore.prototype, "printReceipt", {
    async printReceipt(opts = {}) {
        const order = opts?.order || (typeof this.getOrder === "function" ? this.getOrder() : null);
        posAudit.push(this, "print_receipt", order, {
            amount: order?.getTotalWithTax?.() ?? 0,
        });
        return super.printReceipt(...arguments);
    },
});

patchIfExists(ControlButtons.prototype, "clickPrintBill", {
    async clickPrintBill() {
        const order = this.pos?.getOrder?.() || null;
        posAudit.push(this.pos, "print_bill", order, {
            amount: order?.getTotalWithTax?.() ?? 0,
            note: "Impression de l'addition présentée au client.",
        });
        return super.clickPrintBill(...arguments);
    },
});

// ---------------------------------------------------------------------------
// Validation — seul point où l'on attend la fin de l'envoi
// ---------------------------------------------------------------------------
patchIfExists(OrderPaymentValidation.prototype, "finalizeValidation", {
    async finalizeValidation() {
        const order = this.order || null;
        const store = this.pos || posAudit.pos;
        posAudit.push(store, "validate", order, {
            amount: order?.getTotalWithTax?.() ?? 0,
            note: "Validation du paiement et clôture de la commande.",
        });
        // La commande est sur le point d'être réécrite côté serveur
        // (employé et date d'ouverture écrasés) : on s'assure que le journal
        // est parti avant que l'information d'origine ne disparaisse.
        await posAudit.flush(true);
        return super.finalizeValidation(...arguments);
    },
});
