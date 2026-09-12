# -*- coding: utf-8 -*-
"""Journal d'audit immuable du Point de Vente.

Toute la valeur du modèle tient dans deux propriétés :

1. **L'horodatage fait foi côté serveur.** ``server_datetime`` est posé par
   PostgreSQL au moment de l'insertion ; la tablette ne peut pas l'influencer.
   L'heure annoncée par la tablette est conservée séparément dans
   ``client_datetime`` et l'écart entre les deux est calculé, ce qui rend les
   dérives d'horloge visibles au lieu de les laisser polluer les données.

2. **Les enregistrements ne peuvent plus être modifiés ni supprimés.**
   ``write`` et ``unlink`` lèvent une erreur pour tous les profils, y compris
   l'administrateur. La seule voie de suppression est la purge de rétention
   ci-dessous, qui est volontairement explicite, désactivée par défaut, et
   laisse elle-même une trace dans le journal.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_RETENTION = 'laresidence_pos_audit.retention_days'


class LaresidencePosAudit(models.Model):
    _name = 'laresidence.pos.audit'
    _description = "Journal d'audit du Point de Vente"
    _order = 'server_datetime desc, id desc'
    _rec_name = 'display_label'

    EVENT_TYPES = [
        ('order_open', "Ouverture de commande"),
        ('line_add', "Ajout de ligne"),
        ('line_remove', "Retrait de ligne"),
        ('line_qty', "Modification de quantité"),
        ('line_price', "Modification de prix"),
        ('line_discount', "Remise"),
        ('cashier_change', "Changement de caissier"),
        ('cashier_restore', "Reconnexion caissier sans code"),
        ('table_set', "Affectation de table"),
        ('order_transfer', "Transfert de commande"),
        ('print_bill', "Impression de l'addition"),
        ('print_receipt', "Impression du reçu"),
        ('validate', "Validation"),
        ('order_delete', "Suppression de commande"),
        ('session_start', "Ouverture de session POS"),
        ('audit_purge', "Purge du journal"),
    ]

    # --- Horodatage -------------------------------------------------------
    server_datetime = fields.Datetime(
        string="Horodatage serveur", required=True, index=True, readonly=True,
        default=fields.Datetime.now,
        help="Posé par le serveur à la réception. C'est cette heure qui fait foi.")
    client_datetime = fields.Datetime(
        string="Horodatage tablette", readonly=True,
        help="Heure annoncée par l'appareil. Fournie à titre de comparaison uniquement.")
    clock_skew = fields.Integer(
        string="Écart d'horloge (s)", compute='_compute_clock_skew', store=True, readonly=True,
        help="Écart entre l'heure de la tablette et celle du serveur, en secondes. "
             "Un écart important signale une horloge d'appareil mal réglée.")

    # --- Contexte ---------------------------------------------------------
    event_type = fields.Selection(EVENT_TYPES, string="Événement", required=True, index=True, readonly=True)
    device_identifier = fields.Char(
        string="Appareil", index=True, readonly=True,
        help="Numéro d'appareil attribué par Odoo, déduit de la référence de commande.")
    browser_id = fields.Char(
        string="Poste (navigateur)", index=True, readonly=True,
        help="Identifiant stable généré et conservé par le navigateur de la tablette. "
             "Contrairement au numéro d'appareil, il survit au changement de session "
             "et désigne physiquement le même poste.")
    config_id = fields.Many2one('pos.config', string="Point de vente", ondelete='set null', index=True, readonly=True)
    session_id = fields.Many2one('pos.session', string="Session", ondelete='set null', index=True, readonly=True)
    employee_id = fields.Many2one('hr.employee', string="Caissier", ondelete='set null', index=True, readonly=True)
    user_id = fields.Many2one('res.users', string="Utilisateur technique", ondelete='set null', readonly=True,
                              help="Compte Odoo ayant émis la requête. Renseigné par le serveur, "
                                   "il ne peut pas être falsifié par la tablette.")
    ip_address = fields.Char(string="Adresse IP", readonly=True)

    # --- Objet concerné ---------------------------------------------------
    order_uuid = fields.Char(string="UUID commande", index=True, readonly=True)
    order_reference = fields.Char(string="Référence commande", index=True, readonly=True)
    tracking_number = fields.Char(string="N° d'appel", readonly=True)
    table_name = fields.Char(string="Table", readonly=True)
    product_id = fields.Many2one('product.product', string="Article", ondelete='set null', readonly=True)
    product_name = fields.Char(
        string="Article (libellé d'origine)", readonly=True,
        help="Nom de l'article au moment de l'événement. Un renommage ultérieur "
             "de la fiche article ne réécrit pas cet historique.")
    quantity = fields.Float(string="Quantité", readonly=True)
    amount = fields.Float(string="Montant", readonly=True)
    old_value = fields.Char(string="Ancienne valeur", readonly=True)
    new_value = fields.Char(string="Nouvelle valeur", readonly=True)
    note = fields.Char(string="Détail", readonly=True)

    display_label = fields.Char(string="Libellé", compute='_compute_display_label')
    order_id = fields.Many2one('pos.order', string="Commande", compute='_compute_order_id',
                               search='_search_order_id', readonly=True, store=False)

    _sql_constraints = []

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------
    @api.depends('server_datetime', 'client_datetime')
    def _compute_clock_skew(self):
        for rec in self:
            if rec.server_datetime and rec.client_datetime:
                rec.clock_skew = int((rec.client_datetime - rec.server_datetime).total_seconds())
            else:
                rec.clock_skew = 0

    @api.depends('event_type', 'order_reference', 'product_name', 'employee_id')
    def _compute_display_label(self):
        labels = dict(self.EVENT_TYPES)
        for rec in self:
            bits = [labels.get(rec.event_type, rec.event_type or '')]
            if rec.order_reference:
                bits.append(rec.order_reference)
            if rec.product_name:
                bits.append(rec.product_name)
            rec.display_label = ' · '.join(bits)

    def _compute_order_id(self):
        """Résolution paresseuse : le journal ne stocke pas de lien vers la
        commande, pour n'avoir jamais besoin de réécrire une ligne d'audit."""
        refs = [r.order_reference for r in self if r.order_reference]
        mapping = {}
        if refs:
            orders = self.env['pos.order'].search([('pos_reference', 'in', refs)])
            mapping = {o.pos_reference: o.id for o in orders}
        for rec in self:
            rec.order_id = mapping.get(rec.order_reference, False)

    def _search_order_id(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise UserError(_("Filtre non pris en charge sur la commande."))
        ids = value if isinstance(value, (list, tuple)) else [value]
        orders = self.env['pos.order'].browse([i for i in ids if isinstance(i, int)])
        refs = [r for r in orders.mapped('pos_reference') if r]
        negative = operator in ('!=', 'not in')
        return [('order_reference', 'not in' if negative else 'in', refs or [False])]

    # ------------------------------------------------------------------
    # Immuabilité
    # ------------------------------------------------------------------
    def write(self, vals):
        raise UserError(_(
            "Le journal d'audit du Point de Vente ne peut pas être modifié. "
            "C'est cette garantie qui lui donne sa valeur de preuve."))

    def unlink(self):
        raise UserError(_(
            "Le journal d'audit du Point de Vente ne peut pas être supprimé ligne à ligne. "
            "Seule la purge de rétention, désactivée par défaut, peut retirer "
            "des enregistrements anciens — et elle laisse elle-même une trace."))

    # ------------------------------------------------------------------
    # Écriture (appelée en sudo depuis le contrôleur)
    # ------------------------------------------------------------------
    @api.model
    def log_events(self, events, ip_address=None, user_id=None):
        """Insère un lot d'événements. Retourne le nombre de lignes écrites.

        Les champs de confiance (horodatage serveur, utilisateur, IP) sont
        posés ici et jamais lus depuis la charge utile envoyée par la tablette.
        """
        if not events:
            return 0

        valid_types = {code for code, _label in self.EVENT_TYPES}
        now = fields.Datetime.now()
        rows = []

        for ev in events:
            if not isinstance(ev, dict):
                continue
            event_type = ev.get('event_type')
            if event_type not in valid_types:
                _logger.warning("laresidence_pos_audit : type d'événement inconnu ignoré (%s)", event_type)
                continue
            rows.append({
                'event_type': event_type,
                'server_datetime': now,
                'client_datetime': self._parse_client_dt(ev.get('client_datetime')),
                'device_identifier': self._trim(ev.get('device_identifier'), 32),
                'browser_id': self._trim(ev.get('browser_id'), 64),
                'config_id': self._as_id(ev.get('config_id')),
                'session_id': self._as_id(ev.get('session_id')),
                'employee_id': self._as_id(ev.get('employee_id')),
                'user_id': user_id or self.env.user.id,
                'ip_address': self._trim(ip_address, 64),
                'order_uuid': self._trim(ev.get('order_uuid')),
                'order_reference': self._trim(ev.get('order_reference')),
                'tracking_number': self._trim(ev.get('tracking_number'), 32),
                'table_name': self._trim(ev.get('table_name'), 128),
                'product_id': self._as_id(ev.get('product_id')),
                'product_name': self._trim(ev.get('product_name'), 256),
                'quantity': self._as_float(ev.get('quantity')),
                'amount': self._as_float(ev.get('amount')),
                'old_value': self._trim(ev.get('old_value'), 256),
                'new_value': self._trim(ev.get('new_value'), 256),
                'note': self._trim(ev.get('note'), 512),
            })

        if not rows:
            return 0
        self.sudo().create(rows)
        return len(rows)

    # ------------------------------------------------------------------
    # Utilitaires de normalisation
    # ------------------------------------------------------------------
    @staticmethod
    def _trim(value, length=128):
        if value in (None, False, ''):
            return False
        return str(value)[:length]

    @staticmethod
    def _as_id(value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return False
        return value if value > 0 else False

    @staticmethod
    def _as_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_client_dt(value):
        """Accepte un ISO 8601 ou un timestamp en millisecondes."""
        if not value:
            return False
        try:
            if isinstance(value, (int, float)):
                return fields.Datetime.to_datetime(
                    __import__('datetime').datetime.utcfromtimestamp(value / 1000.0))
            return fields.Datetime.to_datetime(str(value).replace('T', ' ').replace('Z', '')[:19])
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Purge de rétention (désactivée par défaut)
    # ------------------------------------------------------------------
    @api.model
    def _cron_purge(self):
        param = self.env['ir.config_parameter'].sudo().get_param(PARAM_RETENTION, '0')
        try:
            days = int(param)
        except (TypeError, ValueError):
            days = 0
        if days <= 0:
            return False

        self.env.cr.execute(
            "DELETE FROM laresidence_pos_audit "
            "WHERE server_datetime < (now() at time zone 'UTC') - interval '%s days' "
            "AND event_type != 'audit_purge'",
            (days,))
        deleted = self.env.cr.rowcount
        if deleted:
            self.sudo().create([{
                'event_type': 'audit_purge',
                'server_datetime': fields.Datetime.now(),
                'user_id': self.env.user.id,
                'note': "Purge de rétention : %s enregistrement(s) de plus de %s jours supprimé(s)."
                        % (deleted, days),
            }])
            _logger.info("laresidence_pos_audit : purge de %s enregistrements (rétention %s jours)", deleted, days)
        return deleted
