# -*- coding: utf-8 -*-
"""Verrouillage de l'accès au journal et protection contre sa désinstallation.

Ce que ce dispositif fait, et ce qu'il ne fait pas — il vaut mieux le dire
clairement, car s'en remettre à une protection qu'on croit absolue est pire
que de ne pas en avoir.

Contre un employé, un responsable de salle ou un caissier, l'occultation est
complète : sans le droit de consultation, le menu n'existe pas et les
enregistrements sont hors de portée.

Contre un administrateur Odoo, aucune protection applicative ne tient : il
peut s'ajouter au groupe, réécrire les droits d'accès ou désinstaller le
module. Le but poursuivi ici est donc autre — rendre chacun de ces gestes
**délibéré et inscrit**. S'ajouter au groupe, modifier une règle d'accès,
saisir un code, tenter une désinstallation : tout est journalisé, dans une
chaîne d'empreintes qu'on ne peut pas retoucher en silence. On ne prétend pas
rendre le contournement impossible ; on le rend visible.

Le code n'est jamais conservé en clair : seule son empreinte salée l'est.
"""

import hashlib
import logging
import secrets

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

NOM_MODULE = 'laresidence_pos_audit'
PARAM_EMPREINTE = 'laresidence_pos_audit.pin_hash'
PARAM_SEL = 'laresidence_pos_audit.pin_salt'
PARAM_DUREE = 'laresidence_pos_audit.unlock_minutes'
DUREE_DEFAUT = 15
ESSAIS_MAX = 3
FENETRE_ESSAIS_MIN = 15


class LaresidencePosAuditSession(models.Model):
    """Déverrouillages en cours. Un modèle durable plutôt qu'une variable de
    session : un redémarrage du serveur ne doit pas rouvrir l'accès."""

    _name = 'laresidence.pos.audit.session'
    _description = "Accès déverrouillé au journal d'audit"
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string="Utilisateur", required=True,
                              ondelete='cascade', index=True)
    unlocked_until = fields.Datetime(string="Accès ouvert jusqu'à", required=True)

    # Odoo 19 ne reconnaît plus _sql_constraints : la contrainte ne se créait
    # tout simplement pas, et rien n'empêchait deux déverrouillages simultanés
    # pour le même utilisateur.
    _unique_user = models.Constraint(
        'unique(user_id)',
        "Un seul déverrouillage par utilisateur.",
    )


class LaresidencePosAuditAcces(models.AbstractModel):
    """Règles d'accès, code et protection de la désinstallation."""

    _name = 'laresidence.pos.audit.acces'
    _description = "Contrôle d'accès au journal d'audit"

    # ------------------------------------------------------------------
    # Code
    # ------------------------------------------------------------------
    @api.model
    def _empreinte(self, code, sel):
        return hashlib.sha256(('%s|%s' % (sel, code)).encode('utf-8')).hexdigest()

    @api.model
    def _code_defini(self):
        return bool(self.env['ir.config_parameter'].sudo().get_param(PARAM_EMPREINTE))

    @api.model
    def _verifier_code(self, code):
        parametres = self.env['ir.config_parameter'].sudo()
        empreinte = parametres.get_param(PARAM_EMPREINTE)
        sel = parametres.get_param(PARAM_SEL)
        if not empreinte or not sel:
            # Aucun code défini : l'accès reste ouvert aux membres du groupe,
            # sans quoi le module deviendrait inutilisable à l'installation.
            return True
        return secrets.compare_digest(self._empreinte(code or '', sel), empreinte)

    @api.model
    def _definir_code(self, nouveau, actuel=None):
        if not self.env.user.has_group('laresidence_pos_audit.group_pos_audit_officer'):
            raise UserError(_("Vous n'avez pas le droit de définir le code du journal."))
        parametres = self.env['ir.config_parameter'].sudo()
        if self._code_defini() and not self._verifier_code(actuel):
            self._journaliser_refus('audit_unlock_failed',
                                    "Tentative de changement du code refusée : code actuel erroné.")
            raise UserError(_("Le code actuel ne correspond pas."))
        if not nouveau or len(str(nouveau).strip()) < 4:
            raise UserError(_("Le code doit comporter au moins quatre caractères."))
        sel = secrets.token_hex(16)
        parametres.set_param(PARAM_SEL, sel)
        parametres.set_param(PARAM_EMPREINTE, self._empreinte(str(nouveau).strip(), sel))
        self._journaliser('audit_access_changed',
                          "Code d'accès au journal défini ou modifié.")
        return True

    # ------------------------------------------------------------------
    # Déverrouillage
    # ------------------------------------------------------------------
    @api.model
    def _duree_minutes(self):
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(PARAM_DUREE, DUREE_DEFAUT))
        except (TypeError, ValueError):
            return DUREE_DEFAUT

    @api.model
    def _acces_ouvert(self):
        session = self.env['laresidence.pos.audit.session'].sudo().search(
            [('user_id', '=', self.env.user.id)], limit=1)
        return bool(session and session.unlocked_until
                    and session.unlocked_until > fields.Datetime.now())

    @api.model
    def _ouvrir_acces(self):
        modele = self.env['laresidence.pos.audit.session'].sudo()
        jusqua = fields.Datetime.add(fields.Datetime.now(), minutes=self._duree_minutes())
        session = modele.search([('user_id', '=', self.env.user.id)], limit=1)
        if session:
            session.write({'unlocked_until': jusqua})
        else:
            modele.create({'user_id': self.env.user.id, 'unlocked_until': jusqua})
        self._journaliser('audit_unlock',
                          "Accès au journal ouvert pour %s minutes." % self._duree_minutes())

    @api.model
    def _essais_recents(self):
        limite = fields.Datetime.subtract(fields.Datetime.now(), minutes=FENETRE_ESSAIS_MIN)
        return self.env['laresidence.pos.audit'].sudo().search_count([
            ('event_type', '=', 'audit_unlock_failed'),
            ('user_id', '=', self.env.user.id),
            ('server_datetime', '>=', limite),
        ])

    # ------------------------------------------------------------------
    # Journalisation
    # ------------------------------------------------------------------
    @api.model
    def _valeurs_trace(self, type_evenement, message):
        valeurs = {
            'event_type': type_evenement,
            'server_datetime': fields.Datetime.now(),
            'user_id': self.env.user.id,
            'note': (message or '')[:512],
        }
        valeurs.update(self.env['laresidence.pos.audit'].sudo()._contexte_requete())
        return valeurs

    @api.model
    def _journaliser(self, type_evenement, message):
        try:
            self.env['laresidence.pos.audit'].sudo().create(
                [self._valeurs_trace(type_evenement, message)])
        except Exception:
            _logger.exception("laresidence_pos_audit : journalisation d'accès impossible")

    @api.model
    def _journaliser_refus(self, type_evenement, message):
        """Écrit dans une transaction séparée.

        Un refus se termine par une exception, et l'annulation qui suit
        emporterait une trace écrite dans la transaction courante — c'est-à-dire
        exactement celle qu'il faut conserver. Les tentatives infructueuses
        seraient invisibles, et le blocage après plusieurs essais ne se
        déclencherait jamais.
        """
        try:
            valeurs = self._valeurs_trace(type_evenement, message)
            with self.env.registry.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, self.env.context)
                env['laresidence.pos.audit'].create([valeurs])
                cr.commit()
        except Exception:
            _logger.exception("laresidence_pos_audit : trace de refus impossible")

    # ------------------------------------------------------------------
    # Point d'entrée du menu
    # ------------------------------------------------------------------
    @api.model
    def action_ouvrir_journal(self):
        """Renvoie la liste si l'accès est ouvert, sinon la demande de code."""
        if not self.env.user.has_group('laresidence_pos_audit.group_pos_audit_viewer'):
            raise UserError(_("Vous n'avez pas accès au journal d'audit."))
        if self._acces_ouvert() or not self._code_defini():
            return self.env['ir.actions.act_window']._for_xml_id(
                'laresidence_pos_audit.action_laresidence_pos_audit')
        return {
            'type': 'ir.actions.act_window',
            'name': "Accès au journal d'audit",
            'res_model': 'laresidence.pos.audit.unlock',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_motif': 'consultation'},
        }


class IrModuleModule(models.Model):
    """Le module ne se désinstalle pas sans que le code soit saisi.

    Un administrateur déterminé y parviendra tout de même — en ligne de
    commande, par exemple. Mais la tentative bloquée est enregistrée, et la
    chaîne d'empreintes s'arrête net à la désinstallation : l'interruption
    elle-même devient une information.
    """

    _inherit = 'ir.module.module'

    def _laresidence_verifier_deverrouillage(self):
        concernes = self.filtered(lambda m: m.name == NOM_MODULE)
        if not concernes:
            return
        controle = self.env['laresidence.pos.audit.acces']
        if not controle._code_defini() or controle._acces_ouvert():
            return
        controle._journaliser_refus(
            'audit_uninstall_blocked',
            "Tentative de désinstallation du journal d'audit, refusée faute de code.")
        raise UserError(_(
            "Le journal d'audit ne peut pas être désinstallé sans saisir le code d'accès.\n\n"
            "Ouvrez d'abord le journal et saisissez le code, puis recommencez. "
            "Cette tentative a été enregistrée."))

    def button_uninstall(self):
        self._laresidence_verifier_deverrouillage()
        return super().button_uninstall()

    def button_immediate_uninstall(self):
        self._laresidence_verifier_deverrouillage()
        return super().button_immediate_uninstall()
