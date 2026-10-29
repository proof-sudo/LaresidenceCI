# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_OUVERT = 'laresidence_mail_blocage.ouvert_jusqua'
DUREE_MAX_MINUTES = 60


class MailOuvertureWizard(models.TransientModel):
    _name = 'laresidence.mail.ouverture.wizard'
    _description = "Ouvrir temporairement les envois d'e-mails"

    duree = fields.Selection(
        [('5', "5 minutes"), ('15', "15 minutes"),
         ('30', "30 minutes"), ('60', "1 heure")],
        string="Durée", required=True, default='15',
        help="La fenêtre se referme toute seule à l'échéance. Une heure au maximum.")
    motif = fields.Char(
        string="Motif", required=True,
        help="Pourquoi les envois sont ouverts. Consigné dans l'historique.")
    ouvert_jusqua = fields.Datetime(
        string="Fenêtre en cours jusqu'à", compute='_compute_etat_courant')
    envois_ouverts = fields.Boolean(compute='_compute_etat_courant')

    @api.depends('duree')
    def _compute_etat_courant(self):
        echeance = self.env['laresidence.mail.blocage']._ouvert_jusqua()
        for fiche in self:
            fiche.ouvert_jusqua = echeance or False
            fiche.envois_ouverts = bool(echeance)

    def action_ouvrir(self):
        self.ensure_one()
        minutes = int(self.duree)
        if minutes > DUREE_MAX_MINUTES:
            raise UserError("Une fenêtre d'envoi ne peut pas dépasser une heure.")
        echeance = fields.Datetime.now() + timedelta(minutes=minutes)
        self.env['ir.config_parameter'].sudo().set_param(
            PARAM_OUVERT, fields.Datetime.to_string(echeance))
        self.env['laresidence.mail.ouverture'].create({
            'motif': self.motif,
            'date_fin': echeance,
            'duree_minutes': minutes,
        })
        _logger.warning(
            "Blocage e-mail : envois OUVERTS par %s jusqu'a %s — motif : %s",
            self.env.user.login, echeance, self.motif,
        )
        return {'type': 'ir.actions.act_window_close'}

    def action_refermer(self):
        self.ensure_one()
        self.env['laresidence.mail.blocage']._refermer()
        fenetres = self.env['laresidence.mail.ouverture'].search(
            [('date_fermeture', '=', False)])
        fenetres.write({'date_fermeture': fields.Datetime.now()})
        _logger.warning("Blocage e-mail : envois REFERMES par %s.", self.env.user.login)
        return {'type': 'ir.actions.act_window_close'}
