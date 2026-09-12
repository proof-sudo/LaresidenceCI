# -*- coding: utf-8 -*-
"""Suivi des écritures en base sur les objets de caisse.

Le journal alimenté par le front ne voit que ce qui passe par l'interface
caisse. Or une commande peut être créée, modifiée ou supprimée par bien
d'autres chemins : le back-office, un appel externe, un import, une tâche
planifiée. Ce module intercepte les écritures au niveau du modèle, là où tous
ces chemins se rejoignent — il n'existe aucun moyen de modifier un
enregistrement Odoo sans passer par ``create``, ``write`` ou ``unlink``.

Chaque écriture est enregistrée **champ par champ**, avec l'ancienne et la
nouvelle valeur, l'auteur, l'adresse IP, le navigateur et le chemin technique
par lequel l'appel est arrivé — ce dernier séparant sans ambiguïté une action
de caisse d'une intervention en back-office.
"""

import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Champs dont la réécriture n'apprend rien : ils changent à chaque
# enregistrement et noieraient le journal.
CHAMPS_IGNORES = {
    'write_date', 'write_uid', 'create_date', 'create_uid',
    '__last_update', 'message_ids', 'message_follower_ids',
    'message_main_attachment_id', 'access_token', 'display_name',
}

# Ce que l'on retient à la création, pour garder une trace lisible sans
# recopier l'intégralité de l'enregistrement.
# Modèles dont on ne suit qu'une sélection de champs. Tout suivre ferait du
# bruit — « res.users » est réécrit à chaque connexion — et noierait les
# changements qui comptent vraiment. Un modèle absent de ce dictionnaire est
# suivi intégralement : c'est le cas des objets de caisse.
CHAMPS_SURVEILLES = {
    'res.users': ['login', 'active', 'group_ids', 'groups_id', 'password', 'totp_secret'],
    'res.groups': ['name', 'user_ids', 'implied_ids'],
    'product.template': ['name', 'list_price', 'standard_price', 'active',
                         'available_in_pos', 'taxes_id', 'pos_categ_ids'],
    'product.product': ['lst_price', 'standard_price', 'active', 'default_code'],
    'pos.config': ['name', 'active', 'cash_control', 'module_pos_hr', 'iface_printbill',
                   'restrict_price_control', 'manual_discount', 'use_pricelist',
                   'pricelist_id', 'minimal_employee_ids', 'basic_employee_ids',
                   'advanced_employee_ids', 'auto_close_enabled', 'auto_close_time',
                   'auto_close_full'],
    'pos.payment.method': ['name', 'journal_id', 'is_cash_count', 'active',
                           'use_payment_terminal', 'split_transactions'],
    'account.journal': ['name', 'type', 'restrict_mode_hash_table', 'active'],
    'ir.config_parameter': ['key', 'value'],
    'ir.cron': ['name', 'active', 'code', 'interval_number', 'interval_type', 'model_id'],
    'hr.employee': ['name', 'pin', 'barcode', 'active', 'resource_calendar_id',
                    'department_id', 'job_id'],
    'resource.calendar': ['name', 'tz', 'hours_per_day', 'attendance_ids'],
    'res.device.log': ['revoked'],
    'ir.model.access': ['name', 'model_id', 'group_id', 'perm_read', 'perm_write',
                        'perm_create', 'perm_unlink', 'active'],
    'ir.rule': ['name', 'model_id', 'groups', 'domain_force', 'active'],
}

# Clés de paramètres dont la valeur ne doit jamais apparaître dans le journal.
CLES_SENSIBLES = ('pin', 'secret', 'token', 'password', 'hash', 'salt', 'key')

# Valeurs qui ne doivent jamais figurer dans le journal. On enregistre qu'elles
# ont changé, jamais ce qu'elles valent : un journal de sécurité qui recopie un
# code PIN devient lui-même le problème.
CHAMPS_SECRETS = {'password', 'new_password', 'totp_secret', 'pin', 'token',
                  'webhook_verify_token', 'app_secret'}

CHAMPS_CREATION = {
    'pos.order': ['pos_reference', 'tracking_number', 'session_id', 'employee_id',
                  'user_id', 'partner_id', 'table_id', 'amount_total', 'state', 'date_order'],
    'pos.order.line': ['order_id', 'product_id', 'qty', 'price_unit', 'discount',
                       'price_subtotal_incl'],
    'pos.payment': ['pos_order_id', 'payment_method_id', 'amount', 'payment_date',
                    'card_type', 'transaction_id'],
    'pos.session': ['name', 'config_id', 'user_id', 'state', 'start_at'],
    'res.device.log': ['user_id', 'platform', 'browser', 'device_type',
                       'ip_address', 'country', 'city', 'first_activity'],
}


class LaresidencePosAuditOrm(models.AbstractModel):
    """Mixin posé sur les modèles de caisse à surveiller."""

    _name = 'laresidence.pos.audit.orm'
    _description = "Suivi des écritures de caisse"

    # ------------------------------------------------------------------
    # Contexte de l'appel
    # ------------------------------------------------------------------
    @api.model
    def _laresidence_contexte_appel(self):
        return self.env['laresidence.pos.audit'].sudo()._contexte_requete()

    # ------------------------------------------------------------------
    # Sérialisation des valeurs
    # ------------------------------------------------------------------
    @api.model
    def _laresidence_lisible(self, champ, valeur):
        """Rend une valeur de champ lisible dans le journal."""
        if champ in CHAMPS_SECRETS:
            return "(valeur masquée)" if valeur else None
        # ir.config_parameter stocke tout dans un champ « value » : c'est la clé
        # qui dit si le contenu est sensible.
        if self._name == 'ir.config_parameter' and champ == 'value':
            try:
                cle = (self.key or '').lower()
            except Exception:
                cle = ''
            if any(motif in cle for motif in CLES_SENSIBLES):
                return "(valeur masquée)" if valeur else None
        if valeur is None or valeur is False:
            return None
        try:
            definition = self._fields.get(champ)
            if definition and definition.type == 'many2one':
                if isinstance(valeur, models.BaseModel):
                    return [valeur.id, valeur.display_name] if valeur else None
                if isinstance(valeur, (list, tuple)) and valeur:
                    return list(valeur[:2])
                if isinstance(valeur, int):
                    lie = self.env[definition.comodel_name].browse(valeur).exists()
                    return [valeur, lie.display_name] if lie else [valeur, None]
            if definition and definition.type in ('many2many', 'one2many'):
                if isinstance(valeur, models.BaseModel):
                    return valeur.ids
                return str(valeur)[:200]
            if isinstance(valeur, models.BaseModel):
                return valeur.ids
            if hasattr(valeur, 'isoformat'):
                return valeur.isoformat()
            if isinstance(valeur, (int, float, bool, str)):
                return valeur if not isinstance(valeur, str) else valeur[:200]
            return str(valeur)[:200]
        except Exception:
            return None

    @api.model
    def _laresidence_rattachement(self, enregistrement):
        """Rattache l'écriture à une commande, une session, une table."""
        infos = {}
        try:
            nom = self._name
            commande = None
            if nom == 'pos.order':
                commande = enregistrement
            elif nom == 'pos.order.line':
                commande = enregistrement.order_id
            elif nom == 'pos.payment':
                commande = enregistrement.pos_order_id
                infos['payment_method'] = enregistrement.payment_method_id.display_name or False
                infos['amount'] = enregistrement.amount or 0.0
            elif nom == 'pos.session':
                infos['session_id'] = enregistrement.id
                infos['config_id'] = enregistrement.config_id.id
            if commande:
                infos['order_reference'] = commande.pos_reference or False
                infos['tracking_number'] = commande.tracking_number or False
                infos['session_id'] = commande.session_id.id or False
                infos['config_id'] = commande.config_id.id or False
                infos['employee_id'] = commande.employee_id.id or False
                table = getattr(commande, 'table_id', False)
                if table:
                    infos['table_name'] = table.table_number or table.display_name
            if nom == 'pos.order.line':
                infos['product_id'] = enregistrement.product_id.id or False
                infos['product_name'] = enregistrement.full_product_name or \
                    enregistrement.product_id.display_name or False
                infos['quantity'] = enregistrement.qty or 0.0
                infos['amount'] = enregistrement.price_subtotal_incl or 0.0
        except Exception:
            pass
        return infos

    # ------------------------------------------------------------------
    # Dépôt dans le journal
    # ------------------------------------------------------------------
    @api.model
    def _laresidence_journaliser(self, event_type, enregistrement, changements=None, note=None):
        # Pendant l'installation ou la mise à jour d'un module, Odoo réécrit des
        # milliers de droits et de paramètres. Ce bruit de déploiement noierait
        # les gestes qui comptent, et ralentirait chaque mise à jour. Le registre
        # non prêt est le signal fiable de cette phase.
        if not self.env.registry.ready:
            return
        try:
            base = {
                'event_type': event_type,
                'server_datetime': fields.Datetime.now(),
                'user_id': self.env.user.id,
                'model_name': self._name,
                'res_id': enregistrement.id,
                'changes': json.dumps(changements, ensure_ascii=False, default=str)[:20000]
                           if changements else False,
                'note': (note or '')[:512] or False,
            }
            base.update(self._laresidence_contexte_appel())
            base.update(self._laresidence_rattachement(enregistrement))
            self.env['laresidence.pos.audit'].sudo().create([base])
        except Exception:
            # L'audit ne doit jamais empêcher un encaissement d'aboutir.
            _logger.exception("laresidence_pos_audit : journalisation impossible sur %s", self._name)

    # ------------------------------------------------------------------
    # Interception
    # ------------------------------------------------------------------
    @api.model
    def _laresidence_champs_creation(self):
        """Ce qu'on retient à la création d'un enregistrement.

        À défaut d'une liste dédiée, on reprend celle des champs surveillés en
        modification : une création qui n'enregistrerait rien du contenu créé
        ne renseigne personne — c'était le cas des articles, dont la création
        ne portait qu'un objet vide.
        """
        retenus = CHAMPS_CREATION.get(self._name)
        if retenus is None:
            retenus = CHAMPS_SURVEILLES.get(self._name)
        if retenus is None:
            retenus = [c for c in ('name', 'display_name', 'active') if c in self._fields]
        return [c for c in retenus if c in self._fields]

    @api.model_create_multi
    def create(self, vals_list):
        enregistrements = super().create(vals_list)
        retenus = self._laresidence_champs_creation()
        for enregistrement in enregistrements:
            valeurs = {champ: self._laresidence_lisible(champ, enregistrement[champ])
                       for champ in retenus}
            enregistrement._laresidence_journaliser('db_create', enregistrement, {'création': valeurs})
        return enregistrements

    def write(self, vals):
        retenus = CHAMPS_SURVEILLES.get(self._name)
        surveilles = [c for c in vals
                      if c not in CHAMPS_IGNORES and c in self._fields
                      and (retenus is None or c in retenus)]
        avant = {}
        if surveilles:
            for enregistrement in self:
                avant[enregistrement.id] = {
                    c: self._laresidence_lisible(c, enregistrement[c]) for c in surveilles
                }

        resultat = super().write(vals)

        if surveilles:
            for enregistrement in self:
                changements = {}
                for champ in surveilles:
                    ancienne = avant.get(enregistrement.id, {}).get(champ)
                    nouvelle = self._laresidence_lisible(champ, enregistrement[champ])
                    if ancienne != nouvelle:
                        changements[champ] = {'avant': ancienne, 'après': nouvelle}
                if changements:
                    enregistrement._laresidence_journaliser('db_write', enregistrement, changements)
        return resultat

    def unlink(self):
        retenus = self._laresidence_champs_creation()
        for enregistrement in self:
            valeurs = {c: self._laresidence_lisible(c, enregistrement[c])
                       for c in retenus}
            enregistrement._laresidence_journaliser(
                'db_unlink', enregistrement, {'supprimé': valeurs},
                note="Suppression définitive de l'enregistrement.")
        return super().unlink()


class PosOrder(models.Model):
    _name = 'pos.order'
    _inherit = ['pos.order', 'laresidence.pos.audit.orm']


class PosOrderLine(models.Model):
    _name = 'pos.order.line'
    _inherit = ['pos.order.line', 'laresidence.pos.audit.orm']


class PosPayment(models.Model):
    _name = 'pos.payment'
    _inherit = ['pos.payment', 'laresidence.pos.audit.orm']


class PosSession(models.Model):
    _name = 'pos.session'
    _inherit = ['pos.session', 'laresidence.pos.audit.orm']


# ---------------------------------------------------------------------------
# Modèles sensibles hors caisse
#
# Un enquêteur ne s'arrête pas aux commandes. Le prix d'un article modifié en
# plein service, un employé promu en droits avancés, un code PIN réattribué, un
# mode de paiement redirigé vers un autre journal, la tâche de purge du journal
# activée : ces gestes-là ne laissent aucune trace exploitable dans Odoo, et
# chacun peut précéder ou masquer un détournement.
# ---------------------------------------------------------------------------
class ProductTemplate(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'laresidence.pos.audit.orm']


class ProductProduct(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', 'laresidence.pos.audit.orm']


class PosConfig(models.Model):
    _name = 'pos.config'
    _inherit = ['pos.config', 'laresidence.pos.audit.orm']


class PosPaymentMethod(models.Model):
    _name = 'pos.payment.method'
    _inherit = ['pos.payment.method', 'laresidence.pos.audit.orm']


class AccountJournal(models.Model):
    _name = 'account.journal'
    _inherit = ['account.journal', 'laresidence.pos.audit.orm']


class IrConfigParameter(models.Model):
    _name = 'ir.config_parameter'
    _inherit = ['ir.config_parameter', 'laresidence.pos.audit.orm']


class IrCron(models.Model):
    _name = 'ir.cron'
    _inherit = ['ir.cron', 'laresidence.pos.audit.orm']


class ResGroups(models.Model):
    _name = 'res.groups'
    _inherit = ['res.groups', 'laresidence.pos.audit.orm']


class ResUsers(models.Model):
    _name = 'res.users'
    _inherit = ['res.users', 'laresidence.pos.audit.orm']


class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'laresidence.pos.audit.orm']


class ResourceCalendar(models.Model):
    _name = 'resource.calendar'
    _inherit = ['resource.calendar', 'laresidence.pos.audit.orm']


class IrModelAccess(models.Model):
    """Qui a le droit de lire quoi. Se donner accès à un modèle qu'on ne
    voyait pas est le geste qui précède la consultation."""

    _name = 'ir.model.access'
    _inherit = ['ir.model.access', 'laresidence.pos.audit.orm']


class IrRule(models.Model):
    _name = 'ir.rule'
    _inherit = ['ir.rule', 'laresidence.pos.audit.orm']


class ResDeviceLog(models.Model):
    """Chaque nouvelle session ouverte par un utilisateur crée une ligne ici,
    avec la plateforme, le navigateur, l'adresse IP publique, le pays et la
    ville. C'est la trace native des connexions abouties : la suivre revient à
    tenir un registre des sessions sans toucher à l'authentification."""

    _name = 'res.device.log'
    _inherit = ['res.device.log', 'laresidence.pos.audit.orm']
