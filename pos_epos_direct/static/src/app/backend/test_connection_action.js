/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, xml } from "@odoo/owl";

class TestEposConnectionAction extends Component {
    static template = xml`
        <div class="d-flex align-items-center justify-content-center h-100">
            <i class="fa fa-spinner fa-spin fa-2x me-3"/>
            <span>Test de connexion en cours...</span>
        </div>`;
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.actionService = useService("action");
        onMounted(() => this._runTest());
    }

    async _runTest() {
        const { ip, xml_test } = this.props.action.params;
        const base = (ip.startsWith("http") ? ip : "http://" + ip).replace(/\/$/, "");
        const url = base + "/cgi-bin/epos/service.cgi";
        try {
            const resp = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "text/xml; charset=utf-8",
                    "If-Modified-Since": "Thu, 01 Jan 1970 00:00:00 GMT",
                },
                body: xml_test,
            });
            if (resp.ok) {
                this.notification.add("Connexion réussie — ticket de test imprimé.", {
                    type: "success",
                    sticky: false,
                });
            } else {
                this.notification.add(`Erreur imprimante : HTTP ${resp.status}`, {
                    type: "danger",
                    sticky: true,
                });
            }
        } catch (e) {
            this.notification.add(`Imprimante inaccessible (${ip}) : ${e.message}`, {
                type: "danger",
                sticky: true,
            });
        }
        this.actionService.doAction({ type: "ir.actions.act_window_close" });
    }
}

registry.category("actions").add("pos_epos_test_connection", TestEposConnectionAction);
