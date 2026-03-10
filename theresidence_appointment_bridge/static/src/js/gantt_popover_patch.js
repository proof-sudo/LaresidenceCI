/** @odoo-module */

import { POSAppointmentBookingGanttRenderer } from "@pos_appointment/app/gantt_overrides/gantt_renderer";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

/**
 * Patch du renderer Gantt POS pour remplacer les boutons natifs
 * (Booked / Check In / No Show) par les actions TR custom
 * (Réserver / Marquer arrivée / Libérer l'espace / Annuler).
 *
 * Déclenchement : l'utilisateur clique sur un événement dans la vue
 * POS > Appointments > Gantt.
 */
patch(POSAppointmentBookingGanttRenderer.prototype, {
    async getPopoverProps(pill) {
        const props = await super.getPopoverProps(...arguments);
        const { record } = pill;

        // Cherche le sale.order lié à ce calendar.event
        let saleOrders;
        try {
            saleOrders = await this.orm.searchRead(
                "sale.order",
                [
                    ["x_tr_calendar_event_id", "=", record.id],
                    ["x_tr_is_reservation", "=", true],
                ],
                ["x_tr_reservation_status"],
                { limit: 1 }
            );
        } catch (e) {
            // Pas une réservation TR → boutons natifs
            return props;
        }

        if (!saleOrders || !saleOrders.length) {
            return props;
        }

        const status = saleOrders[0].x_tr_reservation_status;
        const calendarEventId = record.id;

        const doAction = async (action) => {
            await this.orm.call(
                "sale.order",
                "pos_action_from_calendar_event",
                [calendarEventId, action]
            );
            this.model.fetchData();
        };

        const buttons = [
            {
                class: "btn btn-sm btn-secondary me-1",
                onClick: () => this.props.openDialog({ resId: record.id }),
                text: _t("Voir"),
            },
        ];

        if (status === "PENDING") {
            buttons.push({
                class: "btn btn-sm btn-primary me-1",
                onClick: () => doAction("reserve"),
                text: _t("Réserver"),
            });
        }
        if (status === "RESERVED") {
            buttons.push({
                class: "btn btn-sm btn-success me-1",
                onClick: () => doAction("arrive"),
                text: _t("Marquer arrivée"),
            });
        }
        if (status === "ARRIVED") {
            buttons.push({
                class: "btn btn-sm btn-info me-1",
                onClick: () => doAction("release"),
                text: _t("Libérer l'espace"),
            });
        }
        if (!["COMPLETED", "CANCELLED"].includes(status)) {
            buttons.push({
                class: "btn btn-sm btn-danger",
                onClick: () => doAction("cancel"),
                text: _t("Annuler"),
            });
        }

        props.buttons = buttons;
        return props;
    },
});
