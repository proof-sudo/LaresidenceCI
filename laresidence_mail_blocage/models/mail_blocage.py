# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_OUVERT = 'laresidence_mail_blocage.ouvert_jusqua'
MOTIF = "Envoi bloque : cette base n'est pas autorisee a emettre des e-mails."


class MailBlocage(models.AbstractModel):
    """Source unique de verite : les envois sont-ils ouverts a cet instant ?"""

    _name = 'laresidence.mail.blocage'
    _description = "Blocage des envois d'e-mails"

    @api.model
    def _ouvert_jusqua(self):
        """Renvoie l'echeance de la fenetre en cours, ou False."""
        valeur = self.env['ir.config_parameter'].sudo().get_param(PARAM_OUVERT)
        if not valeur:
            return False
        try:
            echeance = fields.Datetime.to_datetime(valeur)
        except (ValueError, TypeError):
            _logger.warning("Blocage e-mail : echeance illisible (%s), envois maintenus bloques.", valeur)
            return False
        if not echeance or echeance <= fields.Datetime.now():
            return False
        return echeance

    @api.model
    def _envois_ouverts(self):
        return bool(self._ouvert_jusqua())

    @api.model
    def _refermer(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM_OUVERT, '')


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def send(self, auto_commit=False, raise_exception=False):
        """Abandonne la file tant que les envois ne sont pas ouverts.

        On ne leve pas d'exception : un envoi refuse ne doit pas interrompre
        la validation d'une facture ou la confirmation d'une commande. Le
        message reste consultable, a l'etat « annule », motif a l'appui.
        """
        if not self:
            return True
        if self.env['laresidence.mail.blocage']._envois_ouverts():
            return super().send(auto_commit=auto_commit, raise_exception=raise_exception)
        _logger.warning(
            "Blocage e-mail : %s message(s) abandonne(s). Destinataires : %s",
            len(self),
            ', '.join(filter(None, self.mapped('email_to'))) or 'via destinataires lies',
        )
        self.write({'state': 'cancel', 'failure_reason': MOTIF})
        return True

    def action_laresidence_renvoyer(self):
        """Remet en file les messages selectionnes, si la fenetre est ouverte."""
        blocage = self.env['laresidence.mail.blocage']
        if not blocage._envois_ouverts():
            raise UserError(
                "Les envois sont bloques. Ouvrez d'abord une fenetre d'envoi "
                "depuis Parametres > Blocage des e-mails."
            )
        a_renvoyer = self.filtered(lambda m: m.state in ('cancel', 'exception'))
        if not a_renvoyer:
            return True
        a_renvoyer.write({'state': 'outgoing', 'failure_reason': False})
        _logger.warning(
            "Blocage e-mail : renvoi manuel de %s message(s) par %s.",
            len(a_renvoyer), self.env.user.login,
        )
        a_renvoyer.send()
        return True


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    def _connect__(self, *args, **kwargs):
        """N'ouvre aucune socket tant que les envois ne sont pas ouverts.

        Odoo se comporte deja ainsi en mode test : _connect__() renvoie None.
        On reprend exactement ce comportement plutot que de lever une erreur.
        """
        if not self.env['laresidence.mail.blocage']._envois_ouverts():
            _logger.warning("Blocage e-mail : ouverture de connexion SMTP refusee.")
            return None
        return super()._connect__(*args, **kwargs)

    def send_email(self, message, *args, **kwargs):
        """Couvre les envois qui ne passent pas par la file des messages."""
        if not self.env['laresidence.mail.blocage']._envois_ouverts():
            destinataire = message.get('To') if hasattr(message, 'get') else 'inconnu'
            _logger.warning("Blocage e-mail : remise SMTP refusee pour %s.", destinataire)
            return message['Message-Id'] if hasattr(message, '__getitem__') else False
        return super().send_email(message, *args, **kwargs)
