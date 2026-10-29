import { rpc } from "@web/core/network/rpc";
import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { _t } from "@web/core/l10n/translation";

export class DirectNetworkPrinter extends BasePrinter {
    setup({ ip, port }) {
        super.setup(...arguments);
        this.ip = ip;
        this.port = port || 9100;
        this._printContext = {};
    }

    async sendPrintingJob(img) {
        const ctx = this._printContext || {};
        try {
            const result = await rpc("/pos_direct_printer/print", {
                printer_ip: this.ip,
                printer_port: this.port,
                image: img,
                order_name: ctx.order_name || "",
                table_name: ctx.table_name || "",
            });
            if (result.success) {
                return { result: true };
            }
            return {
                result: false,
                canRetry: true,
                error: result.error,
            };
        } catch {
            return { result: false };
        }
    }

    openCashbox() {
        return rpc("/pos_direct_printer/print", {
            printer_ip: this.ip,
            printer_port: this.port,
            image: "",
            open_cashbox: true,
        });
    }

    getActionError() {
        return {
            successful: false,
            canRetry: true,
            message: {
                title: _t("Connection to printer failed"),
                body: _t(
                    "Could not reach the printer at %s:%s. Check that it is powered on and connected to the network.",
                    this.ip,
                    this.port
                ),
            },
        };
    }

    getResultsError(printResult) {
        return {
            successful: false,
            canRetry: true,
            message: {
                title: _t("Printing failed"),
                body: printResult?.error
                    ? _t("Error: %s", printResult.error)
                    : _t("The printer did not respond. Check it is online."),
            },
        };
    }
}
