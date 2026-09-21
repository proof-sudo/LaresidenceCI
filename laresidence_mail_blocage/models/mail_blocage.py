# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)

MOTIF = "Envoi bloque : cette base n'est pas autorisee a emettre des e-mails."


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def send(self, auto_commit=False, raise_exception=False):
        """Abandonne la file au lieu de la remettre au serveur.

        On ne leve pas d'exception : un envoi refuse ne doit pas interrompre
        la validation d'une facture ou la confirmation d'une commande. Le
        message reste consultable, a l'etat « annule », motif a l'appui.
        """
        if not self:
            return True
        _logger.warning(
            "Blocage e-mail : %s message(s) abandonne(s). Destinataires : %s",
            len(self),
            ', '.join(filter(None, self.mapped('email_to'))) or 'via destinataires lies',
        )
        self.write({'state': 'cancel', 'failure_reason': MOTIF})
        return True


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    @classmethod
    def _disable_send(cls):
        """Coupe la remise SMTP par le point prevu par le framework.

        Odoo verifie cette methode dans _connect__() et dans send_email() :
        aucune connexion n'est ouverte et aucun message n'est remis. Elle
        couvre donc les envois qui ne passent pas par la file des messages,
        sans lever d'exception nulle part.
        """
        return True
