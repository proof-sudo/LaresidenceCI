import logging
import requests
from odoo import models, api, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Codes TVA reconnus par la FNE (ordre : du plus spécifique au plus général)
FNE_TVA_CODES = ['TVAD', 'TVAC', 'TVAB', 'TVA']


def _detect_fne_vat_code(tax):
    """Retourne le code TVA FNE correspondant à une taxe Odoo, ou None.

    Stratégie (par priorité) :
    1. Code FNE explicite dans le nom ou le groupe (TVA/TVAB/TVAC/TVAD)
    2. Marqueur VAT/TVA présent → mapping par taux + suffixe du nom
       - 18 %          → TVA
       - 9 %           → TVAB
       - 0 % + LEG/LEGAL → TVAD  (exonération légale)
       - 0 % autres    → TVAC  (exonération convention / générique)
    """
    group_name = (tax.tax_group_id.name or '').upper() if tax.tax_group_id else ''
    tax_name = (tax.name or '').upper()
    combined = group_name + ' ' + tax_name

    # Priorité 1 : code FNE explicite dans le nom / groupe
    for code in FNE_TVA_CODES:
        if code in combined:
            return code

    # Priorité 2 : groupe ou nom contient VAT ou TVA
    if 'VAT' not in combined and 'TVA' not in combined:
        return None

    rate = float(tax.amount or 0)
    if rate == 18.0:
        return 'TVA'
    if rate == 9.0:
        return 'TVAB'
    if rate == 0.0:
        if 'LEG' in tax_name or 'LEGAL' in tax_name:
            return 'TVAD'
        return 'TVAC'

    return None

PAYMENT_METHOD_MAPPING = {
    'card': 'card',
    'cheque': 'check',
    'check': 'check',
    'espece': 'cash',
    'cash': 'cash',
    'mobile_money': 'mobile-money',
    'mobile-money': 'mobile-money',
    'virement': 'transfer',
    'transfer': 'transfer',
    'deferred': 'deferred',
    'a_terme': 'deferred',
    'a terme': 'deferred',
}


def _clean_str(val):
    if isinstance(val, str):
        return val.encode("utf-8", errors="ignore").decode("utf-8")
    return val


def _truncate(s, n=255):
    s = _clean_str(s) or ""
    return s.replace('\n', ' ').replace('\r', ' ')[:n]


def _normalize_uom(val):
    if not val:
        return "pcs"
    val_lower = val.lower().strip()
    mapping = {
        'unité': 'pcs', 'unite': 'pcs', 'unité(s)': 'pcs', 'unites': 'pcs',
        'u': 'pcs', 'unit': 'pcs', 'units': 'pcs', 'piece': 'pcs', 'pièce': 'pcs',
        'kg': 'kg', 'kilogramme': 'kg', 'kilo': 'kg',
        'litre': 'l', 'litres': 'l',
        'mètre': 'm', 'metre': 'm',
        'heure': 'h', 'heures': 'h', 'forfait': 'h',
        'set': 'set', 'lot': 'set',
    }
    for key, fne_val in mapping.items():
        if key in val_lower:
            return fne_val
    clean = ''.join(c for c in val if c.isalnum())
    return clean[:10] if clean else "pcs"


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    fne_item_id = fields.Char(string="Item ID FNE", copy=False)


class AccountMove(models.Model):
    _inherit = 'account.move'

    fne_sent = fields.Boolean(string="Certifier la facture", default=False, copy=False)
    fne_reference_dgi = fields.Char(string="Référence DGI", readonly=True, copy=False)
    fne_verification_url = fields.Char(string="Lien vérification DGI", readonly=True, copy=False)
    invoice_id_from_fne = fields.Char(string="ID FNE", readonly=True, copy=False)
    fne_warning = fields.Boolean(string="Avertissement FNE", readonly=True, copy=False)
    fne_balance_sticker = fields.Integer(string="Solde sticker FNE", readonly=True, copy=False)
    fne_mode = fields.Char(compute='_compute_fne_mode', string="Mode FNE")
    modes_paiement = fields.Selection(
        selection=[
            ('mobile_money', 'Mobile Money'),
            ('espece', 'Espèces'),
            ('virement', 'Virement Bancaire'),
            ('cheque', 'Chèque'),
            ('deferred', 'A terme'),
            ('card', 'Carte Bancaire'),
        ],
        string="Methode de paiement",
        default='cheque',
        help="Sélectionnez le mode de paiement pour la facture.",
    )

    def _compute_fne_mode(self):
        mode = self.env['ir.config_parameter'].sudo().get_param('fne.mode', default='test')
        for record in self:
            record.fne_mode = mode

    # ------------------------------------------------------------------
    # Config helper (évite la duplication api_key/url dans tout le module)
    # ------------------------------------------------------------------

    def _get_fne_config(self):
        """Lit, valide et retourne (api_key, mode, base_url)."""
        config = self.env['ir.config_parameter'].sudo()
        api_key = config.get_param('fne.api_key', default='').strip()
        mode = (config.get_param('fne.mode', default='test') or 'test').lower().strip()

        if not api_key:
            raise UserError(_(
                "La clé API FNE n'est pas configurée.\n\n"
                "Veuillez configurer le module FNE dans :\n"
                "Configuration > Paramètres > Section FNE"
            ))

        if mode == 'prod':
            base_url = config.get_param('fne.prod_url', default='https://www.services.fne.dgi.gouv.ci/ws')
        else:
            base_url = config.get_param('fne.test_url', default='http://54.247.95.108/ws')

        if not base_url or not base_url.strip():
            raise UserError(_(
                "L'URL de l'API FNE n'est pas configurée pour le mode '%s'.\n\n"
                "Veuillez configurer le module FNE dans :\n"
                "Configuration > Paramètres > Section FNE"
            ) % mode)

        base_url = base_url.strip()
        _logger.info("[FNE] Config chargée : mode=%s url=%s key=***%s",
                     mode, base_url, api_key[-4:] if len(api_key) > 4 else '***')
        return api_key, mode, base_url

    # ------------------------------------------------------------------
    # Détection du template client
    # ------------------------------------------------------------------

    def _detect_template(self):
        """Retourne le template FNE (B2B/B2C/B2F/B2G).

        Priorité : templateFne défini manuellement sur le partenaire,
        puis détection automatique par pays/NIF/statut gouvernemental.
        """
        partner = self.partner_id
        if partner.templateFne:
            return partner.templateFne.upper()
        if getattr(partner, 'x_is_government', False):
            return "B2G"
        if (partner.country_id and partner.country_id.code
                and partner.country_id.code != (self.company_id.country_id.code or "CI")):
            return "B2F"
        if partner.vat:
            return "B2B"
        return "B2C"

    # ------------------------------------------------------------------
    # Taxes : lecture depuis les lignes de commande
    # ------------------------------------------------------------------

    def _classify_taxes(self, line):
        """Classifie les taxes d'une ligne en codes TVA FNE et taxes personnalisées.

        Retourne (fne_taxes, custom_taxes) :
        - fne_taxes   : ex. ['TVA'] ou ['TVAB']
        - custom_taxes: ex. [{"name": "City Tax", "amount": 2.1}]

        Délègue la détection à _detect_fne_vat_code() qui gère
        les noms anglais (VAT 18%) et français (TVA), ainsi que le mapping par taux.
        """
        fne_taxes = []
        custom_taxes_map = {}
        for tax in line.tax_ids:
            fne_code = _detect_fne_vat_code(tax)
            if fne_code:
                if fne_code not in fne_taxes:
                    fne_taxes.append(fne_code)
            else:
                key = (tax.name, tax.amount)
                custom_taxes_map[key] = {
                    "name": _truncate(tax.name, 50),
                    "amount": float(tax.amount),
                }
        return fne_taxes, list(custom_taxes_map.values())

    def _compute_currency_block(self):
        if self.currency_id and self.currency_id != self.company_currency_id:
            rate = self.company_currency_id._get_conversion_rate(
                self.company_currency_id, self.currency_id, self.company_id,
                self.invoice_date or fields.Date.context_today(self),
            ) or 0.0
            return self.currency_id.name or "", float(rate)
        return "", 0.0

    # ------------------------------------------------------------------
    # Construction du payload
    # ------------------------------------------------------------------

    def _build_items(self):
        """Construit les lignes d'articles pour le payload FNE.

        - Taxes TVA lues depuis line.tax_ids (codes TVA/TVAB/TVAC/TVAD)
        - Taxes non-TVA placées en customTaxes par ligne (GRA, AIRSI, etc.)
        """
        items = []
        for line in self.invoice_line_ids.filtered(lambda l: l.product_id):
            qty = float(line.quantity or 0)
            amount = float(line.price_unit or 0)

            if qty <= 0 or amount <= 0:
                _logger.info("[FNE] Ligne ignorée (qty=%s, amount=%s) : %s", qty, amount, line.name)
                continue

            uom = _normalize_uom(line.product_uom_id.name if line.product_uom_id else "")
            fne_taxes, custom_taxes = self._classify_taxes(line)

            _logger.info("[FNE] Ligne '%s' : uom=%s taxes=%s custom=%s",
                         line.name, uom, fne_taxes, custom_taxes)

            item = {
                "description": _truncate(line.name or line.product_id.display_name or "Ligne", 255),
                "quantity": qty,
                "amount": amount,
                "measurementUnit": uom,
            }
            if fne_taxes:
                item["taxes"] = fne_taxes
            if custom_taxes:
                item["customTaxes"] = custom_taxes
            if line.product_id.default_code:
                item["reference"] = _clean_str(line.product_id.default_code)
            if float(line.discount or 0) > 0:
                item["discount"] = float(line.discount)
            items.append(item)
        return items

    def _get_payment_method(self):
        odoo_method = self.modes_paiement or 'cheque'
        fne_method = PAYMENT_METHOD_MAPPING.get(odoo_method, 'check')
        _logger.info("[FNE] Payment method : %s -> %s", odoo_method, fne_method)
        return fne_method

    def _get_client_info(self):
        partner = self.partner_id
        raw_phone = partner.phone or partner.mobile or ""
        client_phone = ''.join(filter(str.isdigit, raw_phone))
        client_email = (partner.email or "").strip() or (self.company_id.email or "").strip() or "noreply@entreprise.ci"
        return {
            "clientCompanyName": _truncate(partner.name or "Client"),
            "clientPhone": client_phone,
            "clientEmail": client_email,
            "clientNcc": _truncate(partner.vat or ""),
        }

    def _prepare_base_payload(self, invoice_type):
        """Construit le payload complet pour l'API FNE.

        Seules les factures de vente (invoiceType='sale') sont certifiées.
        Les factures d'achat sont déclarées par le fournisseur de son côté.
        Taxes TVA et customTaxes portés par chaque item (doc DGI Mai 2025).
        """
        config = self.env['ir.config_parameter'].sudo()
        point_de_vente = config.get_param('fne.point_de_vente', default='').strip()
        establishment = config.get_param('fne.establishment', default='').strip()
        footer = config.get_param('fne.footer', default='Merci pour votre confiance').strip()

        if not point_de_vente:
            raise UserError(_(
                "Le point de vente n'est pas configuré pour le FNE.\n\n"
                "Veuillez le renseigner dans :\n"
                "Configuration > Paramètres > Section FNE > Point de Vente"
            ))
        if not establishment:
            establishment = self.company_id.name or "ENTREPRISE"
            _logger.warning("[FNE] Établissement non configuré, utilisation du nom de société : %s", establishment)

        items = self._build_items()
        template = self._detect_template()
        foreign_currency, foreign_rate = self._compute_currency_block()
        payment_method = self._get_payment_method()
        client_info = self._get_client_info()

        payload = {
            "invoiceType": invoice_type,
            "paymentMethod": payment_method,
            "template": template,
            "clientCompanyName": client_info["clientCompanyName"],
            "clientPhone": client_info["clientPhone"],
            "clientEmail": client_info["clientEmail"],
            "clientNcc": client_info["clientNcc"],
            "pointOfSale": point_de_vente,
            "establishment": _truncate(establishment, 100),
            "items": items,
            "footer": footer,
        }
        payload["foreignCurrency"] = foreign_currency or ""
        payload["foreignCurrencyRate"] = foreign_rate if foreign_currency else 0

        _logger.info(
            "[FNE] Payload %s : type=%s method=%s template=%s client=%s amount=%s items=%d",
            self.name, invoice_type, payment_method, template,
            client_info["clientCompanyName"], self.amount_total, len(items),
        )
        return payload

    # ------------------------------------------------------------------
    # Requêtes HTTP
    # ------------------------------------------------------------------

    def _request_fne(self, method, url, headers, json_body=None, timeout=30):
        """Effectue une requête HTTP vers l'API FNE."""
        try:
            resp = requests.request(method, url, headers=headers, json=json_body, timeout=timeout)
            try:
                data = resp.json()
            except ValueError:
                data = {"raw_response": _truncate(resp.text, 200)}
            if resp.status_code in (200, 201):
                return data
            raise UserError(_("FNE %s %s : %s - %s") % (method, url, resp.status_code, data))
        except requests.RequestException as e:
            raise UserError(_("Erreur réseau FNE %s %s : %s") % (method, url, str(e)))

    # ------------------------------------------------------------------
    # Application de la réponse DGI
    # ------------------------------------------------------------------

    def _apply_sign_success(self, data):
        """Applique la réponse de certification FNE sur la facture."""
        self.fne_sent = True
        self.fne_reference_dgi = data.get("reference") or False
        self.fne_verification_url = data.get("token") or False
        self.fne_warning = bool(data.get("warning"))
        self.fne_balance_sticker = int(data.get("balance_sticker") or 0)
        self.invoice_id_from_fne = (
            data.get("id")
            or data.get("invoice", {}).get("id")
            or self.invoice_id_from_fne
        )
        _logger.info("[FNE] Facture %s certifiée : ref=%s id=%s",
                     self.name, self.fne_reference_dgi, self.invoice_id_from_fne)

        # Mapper les fne_item_id retournés par la DGI sur les lignes Odoo (par index)
        fne_items = data.get("invoice", {}).get("items", [])
        odoo_lines = list(self.invoice_line_ids.filtered(lambda l: l.product_id))
        for i, fne_item in enumerate(fne_items):
            fne_item_id = fne_item.get("id")
            if not fne_item_id:
                continue
            try:
                odoo_lines[i].fne_item_id = fne_item_id
            except IndexError:
                _logger.warning("[FNE] Pas assez de lignes Odoo pour mapper l'item %d de %s", i, self.name)

    def _post_refund_to_fne(self, headers, base_url):
        """Envoie un avoir (credit note) à la DGI."""
        self.ensure_one()

        if not self.reversed_entry_id:
            raise UserError(_(
                "Le champ 'Origin' est manquant sur l'avoir %s. "
                "Impossible de trouver la facture originale."
            ) % self.name)

        origin = self.reversed_entry_id
        if origin.move_type not in ('out_invoice', 'in_invoice'):
            raise UserError(_(
                "Facture d'origine introuvable (numéro %s) pour l'avoir %s"
            ) % (self.invoice_origin, self.name))

        if not origin.invoice_id_from_fne:
            raise UserError(_(
                "ID FNE de la facture d'origine manquant pour l'avoir %s"
            ) % self.name)

        _logger.info("[FNE] REFUND %s -> origine %s (id_fne=%s)",
                     self.name, origin.name, origin.invoice_id_from_fne)

        origin_lines_map = {
            line.product_id.id: line
            for line in origin.invoice_line_ids.filtered(lambda l: l.product_id and l.fne_item_id)
        }

        items = []
        for line in self.invoice_line_ids.filtered(lambda l: l.product_id):
            qty = abs(line.quantity or 0)
            if qty <= 0:
                continue
            orig_line = origin_lines_map.get(line.product_id.id)
            if not orig_line or not orig_line.fne_item_id:
                raise UserError(_(
                    "ID FNE manquant pour le produit '%s' sur l'avoir %s."
                ) % (line.product_id.display_name or line.name or '', self.name))
            items.append({"id": orig_line.fne_item_id, "quantity": float(qty)})

        if not items:
            raise UserError(_("Aucune ligne valable pour le refund FNE."))

        endpoint = base_url.rstrip('/') + f"/external/invoices/{origin.invoice_id_from_fne}/refund"
        data = self._request_fne("POST", endpoint, headers, json_body={"items": items})

        self.fne_sent = True
        self.fne_reference_dgi = data.get("reference") or False
        self.fne_verification_url = data.get("token") or False
        self.fne_warning = bool(data.get("warning"))
        self.fne_balance_sticker = int(data.get("balance_sticker") or 0)
        _logger.info("[FNE] Avoir %s certifié : %s", self.name, data)
        return data

    # ------------------------------------------------------------------
    # Actions utilisateur
    # ------------------------------------------------------------------

    def action_send_to_fne(self):
        """Ouvre le wizard de confirmation avant la certification FNE.

        Appelé depuis le bouton "Créer FNE" (formulaire) et l'action serveur (liste).
        L'envoi réel vers l'API n'est déclenché qu'après confirmation dans le wizard.
        """
        to_send = self.filtered(
            lambda m: m.move_type in ('out_invoice', 'out_refund') and not m.fne_sent
        )
        if not to_send:
            raise UserError(_("Aucune facture éligible à la certification (déjà certifiées ou type non géré)."))

        wizard = self.env['fne.confirm.wizard'].create({
            'invoice_ids': [(6, 0, to_send.ids)],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fne.confirm.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _execute_fne_send(self):
        """Envoie effectivement la/les factures à la DGI via l'API FNE.

        Méthode interne appelée uniquement après confirmation (wizard)
        ou automatiquement via action_post si fne_auto_send est activé.
        """
        api_key, _mode, base_url = self._get_fne_config()
        headers = {
            'Authorization': f"Bearer {api_key}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        endpoint_sign = base_url.rstrip('/') + "/external/invoices/sign"

        for inv in self:
            if inv.fne_sent:
                _logger.info("[FNE] %s déjà certifiée, ignorée.", inv.name)
                continue
            try:
                if inv.move_type == 'out_invoice':
                    payload = inv._prepare_base_payload("sale")
                    data = inv._request_fne("POST", endpoint_sign, headers, json_body=payload)
                    inv._apply_sign_success(data)

                elif inv.move_type == 'out_refund':
                    inv._post_refund_to_fne(headers, base_url)

                else:
                    # Factures d'achat : fournisseur déclare de son côté
                    _logger.info("[FNE] %s ignorée (type %s non géré).", inv.name, inv.move_type)

            except UserError:
                raise
            except Exception:
                _logger.exception("[FNE] Exception non gérée lors de l'envoi de %s", inv.name)
                raise


    def action_open_fne_link(self):
        """Ouvre le lien de vérification DGI dans un nouvel onglet."""
        self.ensure_one()
        if not self.fne_verification_url:
            raise UserError(_("Aucun lien de vérification DGI n'est disponible pour cette facture."))
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': self.fne_verification_url,
        }
