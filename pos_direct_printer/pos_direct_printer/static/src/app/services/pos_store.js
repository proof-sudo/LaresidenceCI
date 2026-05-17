import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { DirectNetworkPrinter } from "@pos_direct_printer/app/utils/printer/direct_network_printer";
import { RetryPrintPopup } from "@point_of_sale/app/components/popups/retry_print_popup/retry_print_popup";

function orderPrintContext(order) {
    return {
        order_name: order?.getName?.() || order?.name || "",
        table_name: order?.table_id?.getName?.() || "",
    };
}

patch(PosStore.prototype, {
    // Handle preparation printers (kitchen orders)
    createPrinter(config) {
        if (config.printer_type === "network_escpos") {
            return new DirectNetworkPrinter({
                ip: config.escpos_printer_ip,
                port: config.escpos_printer_port,
            });
        }
        return super.createPrinter(...arguments);
    },

    // Handle receipt printer + build printer lookup map for mirror resolution
    async setup(env, deps) {
        await super.setup(...arguments);
        if (this.config.escpos_receipt_printer_ip) {
            this.hardwareProxy.printer = new DirectNetworkPrinter({
                ip: this.config.escpos_receipt_printer_ip,
                port: this.config.escpos_receipt_printer_port || 9100,
            });
        }
        // Build lookup map: printer record ID → HWPrinter instance
        this._printerById = {};
        for (const hwPrinter of this.unwatched.printers) {
            if (hwPrinter.config?.id) {
                this._printerById[hwPrinter.config.id] = hwPrinter;
            }
        }
    },

    // Inject order/table context before receipt printing
    async printReceipt(opts = {}) {
        const order = opts.order || this.getOrder();
        const printer = this.hardwareProxy?.printer;
        if (printer instanceof DirectNetworkPrinter) {
            printer._printContext = orderPrintContext(order);
        }
        return super.printReceipt(opts);
    },

    /**
     * Build an array of print jobs for a primary printer.
     * Each job is { printer: HWPrinter, label: string }.
     *
     * - Primary printer appears once (copies handled by pos_print_copies).
     * - Each mirror printer appears once.
     */
    _buildPrintJobs(primaryPrinter) {
        const jobs = [];

        // One job for the primary printer — copies managed by pos_print_copies
        jobs.push({
            printer: primaryPrinter,
            label: primaryPrinter.config.name,
        });

        // One job per mirror printer
        const duplicateIds = primaryPrinter.config.duplicate_printer_ids || [];
        for (const dupId of duplicateIds) {
            const dupHW = this._printerById?.[dupId];
            if (dupHW) {
                jobs.push({
                    printer: dupHW,
                    label: dupHW.config.name + " (miroir)",
                });
            }
        }

        return jobs;
    },

    /**
     * Override printChanges to support mirror printers.
     *
     * Cannot call super.printChanges() because the mirror logic must
     * wrap the innermost printOrderChanges call. Replicates the base loop
     * with an additional inner loop over _buildPrintJobs().
     *
     * Note: print_copies is handled by pos_print_copies which patches
     * printOrderChanges — no copy loop needed here.
     */
    async printChanges(order, orderChange, reprint = false, printers = this.unwatched.printers) {
        const ctx = orderPrintContext(order);
        let isPrinted = false;
        const unsuccessfulPrints = [];
        const retryPrinters = new Set();

        for (const printer of printers) {
            // Inject context on primary printer
            if (printer instanceof DirectNetworkPrinter) {
                printer._printContext = ctx;
            }

            const jobs = this._buildPrintJobs(printer);

            for (const change of orderChange) {
                // Always use the PRIMARY printer's categories for filtering
                const { orderData, changes } = this.generateOrderChange(
                    order,
                    change,
                    printer.config.product_categories_ids,
                    reprint
                );

                const receiptsData = await this.generateReceiptsDataToPrint(
                    orderData,
                    changes,
                    change
                );

                for (const data of receiptsData) {
                    for (const job of jobs) {
                        // Inject context on mirror printers
                        if (job.printer instanceof DirectNetworkPrinter) {
                            job.printer._printContext = ctx;
                        }

                        const result = await this.printOrderChanges(data, job.printer);

                        if (result.successful) {
                            isPrinted = true;
                        }

                        if (!result.successful) {
                            retryPrinters.add(printer);
                            unsuccessfulPrints.push(
                                job.label + ": " + result.message.body
                            );
                        } else if (result.warningCode) {
                            this.displayPrinterWarning(result, job.label);
                        }
                    }
                }
            }
        }

        if (unsuccessfulPrints.length) {
            const failedReceipts = unsuccessfulPrints.join("\n");
            this.dialog.add(RetryPrintPopup, {
                message: failedReceipts,
                canRetry: true,
                retry: () => {
                    this.printChanges(order, orderChange, reprint, retryPrinters);
                },
            });
        }

        return isPrinted;
    },
});
