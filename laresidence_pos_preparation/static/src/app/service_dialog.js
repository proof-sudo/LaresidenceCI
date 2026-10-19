/** @odoo-module */

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Écran de service : l'état réel de chaque plat, et le bouton qui ferme le
 * chronomètre. Le bouton reste inactif tant que la cuisine n'a pas marqué le
 * plat prêt — le même contrôle est refait côté serveur, parce qu'une tablette
 * qui a perdu le réseau peut envoyer une validation périmée.
 */
export class ServiceDialog extends Component {
    static template = "laresidence_pos_preparation.ServiceDialog";
    static components = { Dialog };
    static props = { lignes: Array, close: Function };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ statuts: {}, chargement: true, enCours: false });
        onWillStart(() => this.recharger());
    }

    get uuids() {
        return this.props.lignes.map((ligne) => ligne.uuid);
    }

    async recharger() {
        this.state.chargement = true;
        try {
            this.state.statuts = await this.orm.call(
                "pos.prep.state", "laresidence_statuts", [this.uuids]);
        } catch {
            this.notification.add(
                _t("Impossible de lire l'état de la préparation."), { type: "danger" });
        } finally {
            this.state.chargement = false;
        }
    }

    statut(ligne) {
        return this.state.statuts[ligne.uuid] || null;
    }

    libelle(ligne) {
        const etat = this.statut(ligne);
        if (!etat) {
            return _t("Pas de préparation");
        }
        if (etat.servi) {
            return _t("Servi");
        }
        return `${etat.etape} · ${etat.depuis} min`;
    }

    classeEtat(ligne) {
        const etat = this.statut(ligne);
        if (!etat) {
            return "text-muted";
        }
        if (etat.servi) {
            return "text-success fw-bold";
        }
        if (etat.seuil && etat.depuis > etat.seuil) {
            return "text-danger fw-bold";
        }
        return "text-body";
    }

    peutServir(ligne) {
        const etat = this.statut(ligne);
        return Boolean(etat && etat.pret && !etat.servi);
    }

    peutForcer(ligne) {
        const etat = this.statut(ligne);
        return Boolean(etat && !etat.pret && !etat.servi);
    }

    get lignesServables() {
        return this.props.lignes.filter((ligne) => this.peutServir(ligne));
    }

    async servir(lignes, forcer = false) {
        const uuids = lignes.map((ligne) => ligne.uuid);
        if (!uuids.length || this.state.enCours) {
            return;
        }
        this.state.enCours = true;
        try {
            const resultat = await this.orm.call(
                "pos.prep.state", "laresidence_marquer_servi", [uuids, forcer]);
            const servis = (resultat && resultat.servis) || [];
            const refuses = (resultat && resultat.refuses) || [];
            if (servis.length) {
                this.notification.add(
                    _t("%s plat(s) déclaré(s) servis.", servis.length), { type: "success" });
            }
            // Un refus n'est pas une erreur : la cuisine n'a pas fini. On le
            // dit sans bloquer le reste du lot, qui lui est bien passé.
            for (const refus of refuses) {
                this.notification.add(refus.motif, { type: "warning" });
            }
            await this.recharger();
        } catch (erreur) {
            this.notification.add(
                (erreur && erreur.data && erreur.data.message) ||
                _t("Le service n'a pas pu être enregistré."), { type: "danger" });
        } finally {
            this.state.enCours = false;
        }
    }

    forcer(ligne) {
        const etat = this.statut(ligne);
        this.dialog.add(ConfirmationDialog, {
            title: _t("Plat non marqué prêt"),
            body: _t(
                "La cuisine n'a pas marqué « %(plat)s » prêt : il est encore à l'étape " +
                "« %(etape)s ».\n\nSi vous l'avez réellement servi, confirmez : la " +
                "validation sera enregistrée comme faite sans passage au passe, et le " +
                "temps mesuré sera approximatif.",
                { plat: ligne.getFullProductName ? ligne.getFullProductName() : "", etape: (etat && etat.etape) || "" }),
            confirmLabel: _t("Oui, il a été servi"),
            cancelLabel: _t("Annuler"),
            confirm: () => this.servir([ligne], true),
            cancel: () => {},
        });
    }
}
