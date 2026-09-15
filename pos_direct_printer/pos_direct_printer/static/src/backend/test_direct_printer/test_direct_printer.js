import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

export class TestDirectPrinter extends Component {
    static template = "pos_direct_printer.TestDirectPrinterButton";
    static props = { ...standardWidgetProps };

    setup() {
        this.notification = useService("notification");
    }

    async onClick() {
        const data = this.props.record.data;
        // Support both pos.printer fields and pos.config fields
        const ip = data.escpos_printer_ip || data.escpos_receipt_printer_ip;
        const port = data.escpos_printer_port || data.escpos_receipt_printer_port || 9100;

        if (!ip || ip === "0.0.0.0") {
            this.notification.add(
                _t("Please configure a valid IP address first."),
                { type: "danger" }
            );
            return;
        }

        try {
            const result = await rpc("/pos_direct_printer/test", {
                printer_ip: ip,
                printer_port: port,
            });
            if (result.success) {
                this.notification.add(
                    _t("Test receipt printed successfully!"),
                    { type: "success" }
                );
            } else {
                this.notification.add(
                    _t("Print failed: %s", result.error || "Unknown error"),
                    { type: "warning" }
                );
            }
        } catch {
            this.notification.add(
                _t("Failed to reach the printer. Check IP and port."),
                { type: "danger" }
            );
        }
    }
}

registry.category("view_widgets").add("pos_direct_printer_test", {
    component: TestDirectPrinter,
});
