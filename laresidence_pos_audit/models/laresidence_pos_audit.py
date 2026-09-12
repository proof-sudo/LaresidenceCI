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

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_RETENTION = 'laresidence_pos_audit.retention_days'


class LaresidencePosAudit(models.Model):
    _name = 'laresidence.pos.audit'
    _description = "Journal d'audit du Point de Vente"
    _order = 'server_datetime desc, id desc'

    EVENT_TYPES = [
        ('session_open', "Ouverture de session"),
        ('login', "Connexion caissier"),
        ('logout', "Déconnexion caissier"),
        ('order_open', "Ouverture de commande"),
        ('line_add', "Ajout de ligne"),
        ('line_remove', "Retrait de ligne"),
        ('line_qty', "Modification de quantité"),
        ('line_price', "Modification de prix"),
        ('line_discount', "Remise"),
        ('line_note', "Note de ligne"),
        ('payment_add', "Ajout d'un paiement"),
        ('payment_remove', "Retrait d'un paiement"),
        ('payment_amount', "Montant de paiement modifié"),
        ('partner_set', "Client rattaché"),
        ('guests_set', "Nombre de couverts"),
        ('pricelist_set', "Changement de tarif"),
        ('fiscal_position_set', "Changement de position fiscale"),
        ('note_set', "Note de commande"),
        ('invoice_toggle', "Facturation demandée ou annulée"),
        ('kitchen_send', "Envoi en préparation"),
        ('order_split', "Division de l'addition"),
        ('reprint', "Réimpression d'un ticket"),
        ('refund', "Remboursement"),
        ('cashier_change', "Changement de caissier"),
        ('cashier_restore', "Reconnexion caissier sans code"),
        ('table_set', "Affectation de table"),
        ('order_transfer', "Transfert de commande"),
        ('print_bill', "Impression de l'addition"),
        ('print_receipt', "Impression du reçu"),
        ('validate', "Validation"),
        ('order_delete', "Suppression de commande"),
        ('session_start', "Ouverture de session POS"),
        ('db_create', "Création (base)"),
        ('db_write', "Modification (base)"),
        ('db_unlink', "Suppression (base)"),
        ('audit_read', "Consultation du journal"),
        ('auth_success', "Connexion réussie"),
        ('auth_failure', "Échec de connexion"),
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
    user_agent = fields.Char(
        string="Navigateur", readonly=True,
        help="Chaîne d'identification du navigateur, relevée côté serveur : "
             "elle distingue une tablette iPad d'un poste Windows.")
    origin = fields.Selection([
        ('pos', "Interface caisse"),
        ('backend', "Back-office ou appel externe"),
        ('system', "Traitement automatique"),
    ], string="Origine", index=True, readonly=True,
        help="D'où vient l'action. « Traitement automatique » désigne une tâche "
             "planifiée ou une intervention hors interface.")
    sequence_no = fields.Integer(
        string="N° d'ordre", index=True, readonly=True, copy=False,
        help="Numéro continu. Un trou dans la suite signale une suppression.")
    previous_hash = fields.Char(
        string="Empreinte précédente", readonly=True, copy=False, index=True)
    record_hash = fields.Char(
        string="Empreinte", readonly=True, copy=False, index=True,
        help="Empreinte du contenu de cette ligne et de celle qui la précède. "
             "Modifier ou supprimer une ligne, même directement en base, rompt "
             "la chaîne et devient détectable.")

    session_fingerprint = fields.Char(
        string="Empreinte de session", index=True, readonly=True,
        help="Empreinte de l'identifiant de session, relevée côté serveur. "
             "Elle relie les actions d'une même connexion sans jamais exposer "
             "l'identifiant lui-même, qui serait réutilisable par un tiers.")
    device_id = fields.Many2one(
        'res.device', string="Appareil connecté", ondelete='set null', readonly=True,
        help="Appareil enregistré par Odoo pour cette session : plateforme, "
             "navigateur, adresse IP publique, pays et ville.")
    ip_chain = fields.Char(
        string="Chaîne d'adresses IP", readonly=True,
        help="Adresses traversées, relais compris. La dernière est celle vue "
             "par le serveur, la première celle annoncée par le client.")
    device_local_ip = fields.Char(
        string="Adresse locale de l'appareil", readonly=True,
        help="Adresse de l'appareil sur le réseau du restaurant. Elle distingue "
             "deux tablettes qui partagent la même adresse publique. Les "
             "navigateurs récents peuvent renvoyer un nom en .local à la place : "
             "il reste propre à l'appareil et suffit à les différencier.")

    device_label = fields.Char(
        string="Appareil (résumé)", index=True, readonly=True,
        help="Description courte du poste : type de matériel, taille d'écran, "
             "fuseau horaire. Permet de reconnaître une tablette d'un coup d'œil.")
    device_info = fields.Text(
        string="Appareil (détail)", readonly=True,
        help="Relevé technique complet du poste au moment de l'action : "
             "plateforme, écran, langue, fuseau, décalage horaire déclaré, "
             "tactile, mémoire, état du réseau.")
    origin_path = fields.Char(
        string="Chemin d'appel", readonly=True,
        help="Adresse technique par laquelle l'action est arrivée. Elle sépare "
             "sans ambiguïté une action de caisse d'une modification faite "
             "depuis le back-office.")

    model_name = fields.Char(string="Modèle concerné", index=True, readonly=True)
    res_id = fields.Integer(string="Identifiant de l'enregistrement", index=True, readonly=True)
    changes = fields.Text(
        string="Valeurs modifiées", readonly=True,
        help="Détail champ par champ : ancienne valeur puis nouvelle valeur.")
    payment_method = fields.Char(string="Mode de paiement", readonly=True)

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

    @api.depends('event_type', 'order_reference', 'product_name')
    def _compute_display_name(self):
        labels = dict(self.EVENT_TYPES)
        for rec in self:
            bits = [labels.get(rec.event_type, rec.event_type or '')]
            if rec.order_reference:
                bits.append(rec.order_reference)
            rec.display_name = ' · '.join(bits)

    @api.depends('event_type', 'order_reference', 'product_name')
    def _compute_display_label(self):
        labels = dict(self.EVENT_TYPES)
        for rec in self:
            bits = [labels.get(rec.event_type, rec.event_type or '')]
            if rec.order_reference:
                bits.append(rec.order_reference)
            if rec.product_name:
                bits.append(rec.product_name)
            rec.display_label = ' · '.join(bits)

    @api.depends('order_reference')
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
    # Contexte de la requête — relevé côté serveur
    # ------------------------------------------------------------------
    @api.model
    def contexte_requete(self):
        """Tout ce que le serveur sait de l'appel, sans rien demander au client.

        L'identifiant de session n'est jamais stocké tel quel : il servirait à
        usurper la session de son propriétaire. Seule son empreinte est
        conservée, ce qui permet de relier les actions d'une même connexion et
        de retrouver l'appareil correspondant, sans rien exposer d'utilisable.
        """
        infos = {
            'origin': 'system', 'origin_path': False, 'ip_address': False,
            'ip_chain': False, 'user_agent': False, 'session_fingerprint': False,
            'device_id': False,
        }
        try:
            from odoo.http import request
            if not request:
                return infos

            chemin = request.httprequest.path or ''
            entetes = request.httprequest.headers
            infos['origin_path'] = chemin[:128]
            infos['ip_address'] = request.httprequest.remote_addr
            infos['user_agent'] = str(entetes.get('User-Agent') or '')[:256]

            # Chaîne complète : un relais intermédiaire ne doit pas pouvoir
            # masquer l'adresse réelle de l'appareil.
            transmises = entetes.get('X-Forwarded-For') or ''
            chaine = [p.strip() for p in transmises.split(',') if p.strip()]
            if request.httprequest.remote_addr:
                chaine.append(request.httprequest.remote_addr)
            infos['ip_chain'] = " → ".join(dict.fromkeys(chaine))[:256] or False

            identifiant = getattr(request.session, 'sid', None)
            if identifiant:
                empreinte = hashlib.sha256(str(identifiant).encode('utf-8')).hexdigest()[:32]
                infos['session_fingerprint'] = empreinte
                appareil = self.env['res.device'].sudo().search(
                    [('session_identifier', '=', identifiant)], limit=1)
                if appareil:
                    infos['device_id'] = appareil.id

            referent = entetes.get('Referer') or ''
            vient_de_la_caisse = (
                chemin.startswith('/pos/')
                or chemin.startswith('/laresidence/pos_audit')
                or '/sync_from_ui' in chemin
                or '/pos/ui' in referent
            )
            infos['origin'] = 'pos' if vient_de_la_caisse else 'backend'
        except Exception:
            _logger.debug("laresidence_pos_audit : contexte de requête indisponible")
        return infos

    # ------------------------------------------------------------------
    # Chaînage par empreinte
    # ------------------------------------------------------------------
    # Le blocage de write() et unlink() ne vaut que dans l'application. Un accès
    # direct à la base contourne l'ORM et ne laisse aucune trace. Chaque ligne
    # porte donc l'empreinte de son propre contenu combinée à celle de la ligne
    # qui la précède : retirer, insérer ou retoucher une ligne rompt la chaîne à
    # partir de ce point, et le contrôle d'intégrité le désigne. C'est le même
    # principe que l'inaltérabilité des factures dans Odoo.

    CHAMPS_EMPREINTE = [
        'sequence_no', 'event_type', 'server_datetime', 'client_datetime',
        'user_id', 'employee_id', 'device_identifier', 'browser_id',
        'session_fingerprint', 'ip_address', 'ip_chain', 'device_local_ip',
        'origin', 'origin_path', 'model_name', 'res_id',
        'order_reference', 'order_uuid', 'tracking_number', 'table_name',
        'product_id', 'product_name', 'quantity', 'amount',
        'payment_method', 'old_value', 'new_value', 'changes', 'note',
    ]

    def _contenu_empreinte(self):
        """Représentation canonique et stable d'une ligne."""
        self.ensure_one()
        valeurs = {}
        for champ in self.CHAMPS_EMPREINTE:
            valeur = self[champ]
            if isinstance(valeur, models.BaseModel):
                valeur = valeur.id or 0
            elif hasattr(valeur, 'isoformat'):
                valeur = valeur.isoformat()
            valeurs[champ] = valeur if valeur not in (False, None) else None
        valeurs['previous_hash'] = self.previous_hash or ''
        return json.dumps(valeurs, sort_keys=True, ensure_ascii=False, default=str)

    def _calculer_empreinte(self):
        self.ensure_one()
        return hashlib.sha256(self._contenu_empreinte().encode('utf-8')).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        enregistrements = super().create(vals_list)
        # Verrou le temps de la transaction : deux écritures simultanées ne
        # peuvent pas se voir attribuer le même prédécesseur.
        self.env.cr.execute("SELECT pg_advisory_xact_lock(%s)", (4815162342,))
        self.env.cr.execute(
            "SELECT sequence_no, record_hash FROM laresidence_pos_audit "
            "WHERE sequence_no IS NOT NULL ORDER BY sequence_no DESC LIMIT 1")
        ligne = self.env.cr.fetchone()
        numero = (ligne[0] if ligne else 0)
        precedente = (ligne[1] if ligne else '') or ''
        for enregistrement in enregistrements:
            numero += 1
            self.env.cr.execute(
                "UPDATE laresidence_pos_audit SET sequence_no = %s, previous_hash = %s "
                "WHERE id = %s", (numero, precedente, enregistrement.id))
            enregistrement.invalidate_recordset(['sequence_no', 'previous_hash'])
            empreinte = enregistrement._calculer_empreinte()
            self.env.cr.execute(
                "UPDATE laresidence_pos_audit SET record_hash = %s WHERE id = %s",
                (empreinte, enregistrement.id))
            enregistrement.invalidate_recordset(['record_hash'])
            precedente = empreinte
        return enregistrements

    @api.model
    def verifier_integrite(self, limite=None):
        """Recalcule la chaîne et signale la première anomalie.

        Retourne un état lisible : nombre de lignes contrôlées, trous dans la
        numérotation, et première ligne dont l'empreinte ne correspond plus.
        """
        domaine = [('sequence_no', '!=', False)]
        lignes = self.sudo().search(domaine, order='sequence_no asc', limit=limite or 0)
        attendu_precedent = ''
        attendu_numero = None
        trous = []
        rupture = None

        for ligne in lignes:
            if attendu_numero is not None and ligne.sequence_no != attendu_numero:
                trous.append((attendu_numero, ligne.sequence_no))
            attendu_numero = ligne.sequence_no + 1

            if rupture is None:
                if (ligne.previous_hash or '') != attendu_precedent:
                    rupture = (ligne.id, ligne.sequence_no, "chaînage rompu")
                elif ligne._calculer_empreinte() != (ligne.record_hash or ''):
                    rupture = (ligne.id, ligne.sequence_no, "contenu modifié")
            attendu_precedent = ligne.record_hash or ''

        return {
            'controlees': len(lignes),
            'trous': trous,
            'rupture': rupture,
            'intacte': not trous and rupture is None,
        }

    def action_verifier_integrite(self):
        etat = self.verifier_integrite()
        if etat['intacte']:
            titre = "Journal intact"
            corps = ("%s ligne(s) contrôlées. La numérotation est continue et "
                     "chaque empreinte correspond à son contenu." % etat['controlees'])
            genre = 'success'
        else:
            titre = "Anomalie détectée"
            morceaux = ["%s ligne(s) contrôlées." % etat['controlees']]
            if etat['trous']:
                morceaux.append("Numérotation interrompue : %s." % ", ".join(
                    "entre %s et %s" % (a - 1, b) for a, b in etat['trous'][:5]))
            if etat['rupture']:
                morceaux.append("Première anomalie au n° %s (%s)."
                                % (etat['rupture'][1], etat['rupture'][2]))
            corps = "\n".join(morceaux)
            genre = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': titre, 'message': corps, 'type': genre, 'sticky': True},
        }

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
    # Consultation du journal
    # ------------------------------------------------------------------
    # Savoir qui a consulté les traces fait partie des traces. La lecture est
    # notée une fois par utilisateur et par quart d'heure : noter chaque
    # rafraîchissement d'écran remplirait le journal de son propre reflet.
    DELAI_NOTE_LECTURE = 900

    @api.model
    def web_search_read(self, domain=None, specification=None, **kwargs):
        resultat = super().web_search_read(domain=domain, specification=specification, **kwargs)
        try:
            self._noter_consultation(len(resultat.get('records', [])) if resultat else 0)
        except Exception:
            _logger.debug("laresidence_pos_audit : consultation non notée")
        return resultat

    @api.model
    def _noter_consultation(self, nombre):
        if self.env.context.get('laresidence_audit_interne'):
            return
        limite = fields.Datetime.now() - timedelta(seconds=self.DELAI_NOTE_LECTURE)
        deja = self.sudo().with_context(laresidence_audit_interne=True).search_count([
            ('event_type', '=', 'audit_read'),
            ('user_id', '=', self.env.user.id),
            ('server_datetime', '>=', limite),
        ])
        if deja:
            return
        valeurs = {
            'event_type': 'audit_read',
            'server_datetime': fields.Datetime.now(),
            'user_id': self.env.user.id,
            'note': "Consultation du journal d'audit (%s ligne(s) affichées)." % nombre,
        }
        valeurs.update(self.contexte_requete())
        self.sudo().with_context(laresidence_audit_interne=True).create([valeurs])

    # ------------------------------------------------------------------
    # Écriture (appelée en sudo depuis le contrôleur)
    # ------------------------------------------------------------------
    @api.model
    def log_events(self, events, ip_address=None, user_id=None, user_agent=None,
                   origin_path=None, session_fingerprint=None, ip_chain=None):
        """Insère un lot d'événements. Retourne le nombre de lignes écrites.

        Les champs de confiance (horodatage serveur, utilisateur, IP) sont
        posés ici et jamais lus depuis la charge utile envoyée par la tablette.
        """
        if not events:
            return 0

        valid_types = {code for code, _label in self.EVENT_TYPES}
        now = fields.Datetime.now()
        contexte = self.contexte_requete()
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
                'session_fingerprint': contexte.get('session_fingerprint'),
                'device_id': contexte.get('device_id'),
                'client_datetime': self._parse_client_dt(ev.get('client_datetime')),
                'device_identifier': self._trim(ev.get('device_identifier'), 32),
                'browser_id': self._trim(ev.get('browser_id'), 64),
                'config_id': self._as_id(ev.get('config_id')),
                'session_id': self._as_id(ev.get('session_id')),
                'employee_id': self._as_id(ev.get('employee_id')),
                'user_id': user_id or self.env.user.id,
                'ip_address': self._trim(ip_address or contexte.get('ip_address'), 64),
                'user_agent': self._trim(user_agent or contexte.get('user_agent'), 256),
                'origin': 'pos',
                'origin_path': self._trim(origin_path or contexte.get('origin_path'), 128),
                'ip_chain': self._trim(ip_chain or contexte.get('ip_chain'), 256),
                'payment_method': self._trim(ev.get('payment_method'), 128),
                'device_label': self._trim(ev.get('device_label'), 128),
                'device_info': self._trim(ev.get('device_info'), 4000),
                'device_local_ip': self._trim(ev.get('device_local_ip'), 128),
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
                horodatage = datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
                return horodatage.replace(tzinfo=None)
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
