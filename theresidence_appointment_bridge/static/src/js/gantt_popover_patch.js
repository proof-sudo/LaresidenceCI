/** @odoo-module */

import { POSAppointmentBookingGanttRenderer } from "@pos_appointment/app/gantt_overrides/gantt_renderer";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

/**
 * Patch du renderer Gantt POS pour remplacer les boutons natifs
 * (Booked / Check In / No Show) par les actions TR custom :
 *   Réserver / Marquer arrivée / Libérer l'espace / Annuler
 *
 * Si l'événement n'est pas une réservation TR, les boutons natifs sont conservés.
 */
patch(POSAppointmentBookingGanttRenderer.prototype, {
    async getPopoverProps(pill) {
        const props = await super.getPopoverProps(...arguments);
        const { record } = pill;

        // Cherche le sale.order TR lié à ce calendar.event
        let saleOrders;
        try {
            saleOrders = await this.orm.searchRead(
                "sale.order",
                [
                    ["x_tr_calendar_event_id", "=", record.id],
                    ["x_tr_is_reservation", "=", true],
                ],
                ["x_tr_reservation_status", "order_line", "x_tr_pos_order_id"],
                { limit: 1 }
            );
        } catch (e) {
            return props;
        }

        if (!saleOrders || !saleOrders.length) {
            return props; // Pas une réservation TR → boutons natifs conservés
        }

        const status = saleOrders[0].x_tr_reservation_status;
        const hasLines = (saleOrders[0].order_line || []).length > 0;
        const alreadyLoaded = !!saleOrders[0].x_tr_pos_order_id;
        const calendarEventId = record.id;

        // Accès au service notification (disponible sur l'env OWL)
        const notification = this.env?.services?.notification;

        const doAction = async (action) => {
            try {
                await this.orm.call(
                    "sale.order",
                    "pos_action_from_calendar_event",
                    [calendarEventId, action]
                );
                this.model.fetchData();
                notification?.add(_t("Réservation mise à jour"), {
                    type: "success",
                    sticky: false,
                });
            } catch (e) {
                const msg = e?.data?.message || e?.message || _t("Erreur inconnue");
                console.error("[TR BRIDGE] Erreur action réservation:", msg);
                notification?.add(msg, {
                    title: _t("Erreur réservation"),
                    type: "danger",
                    sticky: false,
                });
            }
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
        // "Libérer" disponible depuis RESERVED ou ARRIVED (action_release accepte les deux)
        if (["RESERVED", "ARRIVED"].includes(status)) {
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

        // Bouton "Charger la commande" : visible si le sale.order a des lignes
        // et n'a pas encore été chargé dans le POS
        if (hasLines && !alreadyLoaded && !["COMPLETED", "CANCELLED"].includes(status)) {
            buttons.push({
                class: "btn btn-sm btn-warning mt-1",
                onClick: async () => {
                    try {
                        const result = await this.orm.call(
                            "sale.order",
                            "pos_load_reservation_to_pos",
                            [calendarEventId]
                        );
                        this.model.fetchData();
                        notification?.add(
                            _t("Commande %s chargée dans le POS", result.pos_order_name),
                            { type: "success", sticky: false }
                        );
                    } catch (e) {
                        const msg = e?.data?.message || e?.message || _t("Erreur inconnue");
                        console.error("[TR BRIDGE] Erreur chargement POS:", msg);
                        notification?.add(msg, {
                            title: _t("Erreur chargement POS"),
                            type: "danger",
                            sticky: false,
                        });
                    }
                },
                text: _t("Charger la commande"),
            });
        }

        if (alreadyLoaded) {
            buttons.push({
                class: "btn btn-sm btn-outline-secondary mt-1 disabled",
                onClick: () => {},
                text: _t("✓ Déjà chargée en POS"),
            });
        }

        props.buttons = buttons;
        return props;
    },
});
