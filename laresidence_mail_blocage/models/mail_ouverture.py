# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MailOuverture(models.Model):
    """Journal des fenetres pendant lesquelles les envois ont ete autorises."""

    _name = 'laresidence.mail.ouverture'
    _description = "Fenetre d'envoi autorisee"
    _order = 'date_debut desc'
    _rec_name = 'motif'

    motif = fields.Char(string="Motif", required=True, readonly=True)
    user_id = fields.Many2one(
        'res.users', string="Ouverte par", required=True, readonly=True,
        default=lambda self: self.env.user)
    date_debut = fields.Datetime(
        string="Ouverte le", required=True, readonly=True,
        default=fields.Datetime.now)
    date_fin = fields.Datetime(string="Refermeture prevue", required=True, readonly=True)
    date_fermeture = fields.Datetime(string="Refermee le", readonly=True)
    duree_minutes = fields.Integer(string="Durée (minutes)", readonly=True)
    etat = fields.Selection(
        [('ouverte', "Ouverte"), ('fermee', "Refermée")],
        string="État", compute='_compute_etat')

    @api.depends('date_fin', 'date_fermeture')
    def _compute_etat(self):
        maintenant = fields.Datetime.now()
        for fenetre in self:
            fermee = fenetre.date_fermeture or (fenetre.date_fin and fenetre.date_fin <= maintenant)
            fenetre.etat = 'fermee' if fermee else 'ouverte'

    def action_refermer(self):
        """Referme immediatement la fenetre, sans attendre l'echeance."""
        self.env['laresidence.mail.blocage']._refermer()
        self.filtered(lambda f: not f.date_fermeture).write({
            'date_fermeture': fields.Datetime.now(),
        })
        return True
