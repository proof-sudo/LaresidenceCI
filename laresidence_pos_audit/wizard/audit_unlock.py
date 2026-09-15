# -*- coding: utf-8 -*-
"""Demande du code d'accès, et réglages réservés à l'administrateur du journal."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.audit_access import ESSAIS_MAX, FENETRE_ESSAIS_MIN, PARAM_DUREE


class LaresidencePosAuditUnlock(models.TransientModel):
    _name = 'laresidence.pos.audit.unlock'
    _description = "Saisie du code d'accès au journal d'audit"

    # Le masquage à la saisie est un attribut de la vue (password="True"),
    # pas du champ : Odoo 19 le refuse ici.
    code = fields.Char(string="Code d'accès", required=True)
    motif = fields.Selection([
        ('consultation', "Consulter le journal"),
        ('desinstallation', "Autoriser la désinstallation du module"),
    ], string="Motif", default='consultation', required=True)
    message = fields.Char(string="Information", readonly=True,
                          default=lambda self: self._message_defaut())

    @api.model
    def _message_defaut(self):
        controle = self.env['laresidence.pos.audit.acces']
        restants = max(ESSAIS_MAX - controle._essais_recents(), 0)
        if restants <= 0:
            return ("Trop de tentatives infructueuses. Réessayez dans %s minutes. "
                    "Chaque tentative est enregistrée." % FENETRE_ESSAIS_MIN)
        return ("L'accès reste ouvert %s minutes après la saisie. "
                "Chaque tentative, réussie ou non, est enregistrée."
                % controle._duree_minutes())

    def action_valider(self):
        self.ensure_one()
        controle = self.env['laresidence.pos.audit.acces']

        if controle._essais_recents() >= ESSAIS_MAX:
            controle._journaliser_refus(
                'audit_unlock_failed',
                "Saisie refusée : trop de tentatives infructueuses sur les %s dernières minutes."
                % FENETRE_ESSAIS_MIN)
            raise UserError(_(
                "Trop de tentatives infructueuses. Réessayez dans %s minutes.",
                FENETRE_ESSAIS_MIN))

        if not controle._verifier_code(self.code):
            controle._journaliser_refus('audit_unlock_failed',
                                        "Code d'accès erroné (motif : %s)." % self.motif)
            raise UserError(_("Code incorrect. Cette tentative a été enregistrée."))

        controle._ouvrir_acces()

        if self.motif == 'desinstallation':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "Accès ouvert",
                    'message': "La désinstallation est autorisée pendant %s minutes."
                               % controle._duree_minutes(),
                    'type': 'warning',
                    'sticky': True,
                },
            }
        return self.env['ir.actions.act_window']._for_xml_id(
            'laresidence_pos_audit.action_laresidence_pos_audit')


class LaresidencePosAuditAccessConfig(models.TransientModel):
    """Qui peut consulter le journal, et sous quel code."""

    _name = 'laresidence.pos.audit.access'
    _description = "Réglages d'accès au journal d'audit"

    user_ids = fields.Many2many(
        'res.users', string="Personnes autorisées à consulter",
        default=lambda self: self._utilisateurs_actuels(),
        help="Ces personnes voient le menu du journal. Les autres n'en ont "
             "aucune trace. Toute modification de cette liste est elle-même "
             "inscrite dans le journal.")
    code_actuel = fields.Char(string="Code actuel",
                              help="À renseigner uniquement si un code est déjà défini.")
    code_nouveau = fields.Char(string="Nouveau code")
    duree_minutes = fields.Integer(
        string="Durée d'ouverture (minutes)",
        default=lambda self: self.env['laresidence.pos.audit.acces']._duree_minutes(),
        help="Temps pendant lequel l'accès reste ouvert après la saisie du code.")
    code_deja_defini = fields.Boolean(
        string="Un code est déjà défini", readonly=True,
        default=lambda self: self.env['laresidence.pos.audit.acces']._code_defini())

    @api.model
    def _utilisateurs_actuels(self):
        groupe = self.env.ref('laresidence_pos_audit.group_pos_audit_viewer',
                              raise_if_not_found=False)
        return [(6, 0, groupe.user_ids.ids)] if groupe else False

    def action_appliquer(self):
        self.ensure_one()
        controle = self.env['laresidence.pos.audit.acces']

        groupe = self.env.ref('laresidence_pos_audit.group_pos_audit_viewer',
                              raise_if_not_found=False)
        if groupe:
            avant = set(groupe.user_ids.ids)
            apres = set(self.user_ids.ids)
            if avant != apres:
                groupe.sudo().write({'user_ids': [(6, 0, list(apres))]})
                ajoutes = self.env['res.users'].browse(list(apres - avant)).mapped('name')
                retires = self.env['res.users'].browse(list(avant - apres)).mapped('name')
                details = []
                if ajoutes:
                    details.append("ajout : %s" % ", ".join(ajoutes))
                if retires:
                    details.append("retrait : %s" % ", ".join(retires))
                controle._journaliser(
                    'audit_access_changed',
                    "Liste des personnes autorisées modifiée — %s." % " ; ".join(details))

        if self.duree_minutes and self.duree_minutes > 0:
            self.env['ir.config_parameter'].sudo().set_param(
                PARAM_DUREE, str(int(self.duree_minutes)))

        if self.code_nouveau:
            controle._definir_code(self.code_nouveau, self.code_actuel)

        return {'type': 'ir.actions.act_window_close'}
