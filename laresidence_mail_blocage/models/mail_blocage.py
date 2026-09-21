# -*- coding: utf-8 -*-
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MOTIF = "Envoi bloque : cette base n'est pas autorisee a emettre des e-mails."


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def send(self, auto_commit=False, raise_exception=False):
        """Abandonne la file au lieu de la remettre au serveur.

        On ne leve pas d'exception : un envoi refuse ne doit pas interrompre
        la validation d'une facture ou la confirmation d'une commande.
        """
        if not self:
            return True
        _logger.warning(
            "Blocage e-mail : %s message(s) abandonne(s). Destinataires : %s",
            len(self), ', '.join(filter(None, self.mapped('email_to'))) or 'via destinataires lies',
        )
        self.write({'state': 'cancel', 'failure_reason': MOTIF})
        return True


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    def connect(self, *args, **kwargs):
        _logger.warning("Blocage e-mail : ouverture de connexion SMTP refusee.")
        raise UserError(_(MOTIF))

    def send_email(self, message, *args, **kwargs):
        _logger.warning(
            "Blocage e-mail : remise SMTP refusee pour %s.",
            message.get('To') if hasattr(message, 'get') else 'destinataire inconnu',
        )
        raise UserError(_(MOTIF))
