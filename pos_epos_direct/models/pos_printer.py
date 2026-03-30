# -*- coding: utf-8 -*-
"""
pos_epos_direct — Impression ePOS directe sans IoT Box.

Deux types d'imprimantes sont ajoutés au modèle pos.printer :

  epos_direct         → Reçu client complet (après paiement)
  epos_direct_kitchen → Ticket de préparation pour cuisine / bar / toute station

L'impression passe par le serveur Odoo (HTTP ePOS depuis Python) afin d'éviter
la conversion html2canvas côté client, source principale de lenteur.
"""

import logging
import textwrap
import requests
import xml.etree.ElementTree as ET

from odoo import fields, models, api, _

_logger = logging.getLogger(__name__)

# ─── Constantes formatage ────────────────────────────────────────────────────

PAPER_COLS = 42        # Colonnes pour papier 80 mm (police normale)
SEPARATOR = '─' * PAPER_COLS
EPOS_NS = "http://www.epson-pos.com/schemas/2011/03/epos-print"

# ─── Helpers XML ─────────────────────────────────────────────────────────────

def _el(parent, tag, attrib=None, text=None):
    """Ajoute un élément fils et retourne l'élément créé."""
    el = ET.SubElement(parent, tag, **(attrib or {}))
    if text is not None:
        el.text = text
    return el

def _text(parent, content, **attrs):
    _el(parent, 'text', attrs, content)

def _feed(parent, lines=1):
    _el(parent, 'feed', {'line': str(lines)})

def _cut(parent):
    _el(parent, 'cut', {'type': 'feed'})

def _separator(parent):
    _text(parent, SEPARATOR + '\n')

def _lj_rj(left, right, width=PAPER_COLS):
    """Ligne avec texte à gauche et texte à droite, remplie d'espaces."""
    left, right = str(left), str(right)
    gap = width - len(left) - len(right)
    return left + (' ' * max(1, gap)) + right

def _center(text, width=PAPER_COLS):
    text = str(text)
    pad = max(0, (width - len(text)) // 2)
    return ' ' * pad + text


# ─── Modèle ──────────────────────────────────────────────────────────────────

class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    printer_type = fields.Selection(
        selection_add=[
            ('epos_direct',         'Epson ePOS Direct — Reçu client (Rapide)'),
            ('epos_direct_kitchen', 'Epson ePOS Direct — Ticket Cuisine / Bar'),
        ],
        ondelete={
            'epos_direct':         'set default',
            'epos_direct_kitchen': 'set default',
        },
    )

    # ── Chargement données POS ────────────────────────────────────────────────

    @api.model
    def _load_pos_data_fields(self, config):
        result = super()._load_pos_data_fields(config)
        for field in ('epson_printer_ip', 'product_categories_ids'):
            if field not in result:
                result.append(field)
        return result

    # ── Points d'entrée appelés depuis le frontend JS ─────────────────────────

    @api.model
    def _send_epos_receipt(self, printer_id, order_id):
        """
        Génère et envoie le reçu CLIENT complet à l'imprimante.
        Appelé par EposDirectPrinter.printReceipt() (JS).
        Retourne {'success': bool, 'message': str}.
        """
        printer = self.browse(printer_id)
        ok, err = printer._check_ready()
        if not ok:
            return {'success': False, 'message': err}

        order = self.env['pos.order'].browse(order_id)
        if not order.exists():
            return {'success': False, 'message': _("Commande introuvable (id=%s).") % order_id}

        xml_str = printer._build_receipt_xml(order)
        return printer._post_to_printer(xml_str)

    @api.model
    def _send_epos_kitchen_ticket(self, printer_id, order_id):
        """
        Génère et envoie le ticket CUISINE/BAR filtré par les catégories
        configurées sur l'imprimante.
        Appelé par EposDirectKitchenPrinter.printReceipt() (JS).
        Retourne {'success': bool, 'message': str}.
        """
        printer = self.browse(printer_id)
        ok, err = printer._check_ready()
        if not ok:
            return {'success': False, 'message': err}

        order = self.env['pos.order'].browse(order_id)
        if not order.exists():
            return {'success': False, 'message': _("Commande introuvable (id=%s).") % order_id}

        xml_str = printer._build_kitchen_xml(order)
        if not xml_str:
            # Aucune ligne ne correspond aux catégories de cette imprimante
            return {'success': True, 'message': 'nothing_to_print'}

        return printer._post_to_printer(xml_str)

    # ── Validation ───────────────────────────────────────────────────────────

    def _check_ready(self):
        if not self.exists():
            return False, _("Imprimante introuvable.")
        if not self.epson_printer_ip:
            return False, _("Adresse IP de l'imprimante non configurée.")
        return True, None

    # ── Envoi HTTP vers l'imprimante ─────────────────────────────────────────

    def _post_to_printer(self, xml_str):
        """Envoie le XML ePOS à l'imprimante et retourne le résultat."""
        ip = self.epson_printer_ip.strip()
        if not ip.startswith(('http://', 'https://')):
            ip = 'http://' + ip
        url = ip.rstrip('/') + '/cgi-bin/epos/service.cgi'

        try:
            resp = requests.post(
                url,
                data=xml_str.encode('utf-8'),
                headers={
                    'Content-Type': 'text/xml; charset=utf-8',
                    'If-Modified-Since': 'Thu, 01 Jan 1970 00:00:00 GMT',
                },
                timeout=8,
            )
        except requests.exceptions.ConnectionError:
            msg = _("Impossible de joindre l'imprimante (%s).") % self.epson_printer_ip
            _logger.warning("ePOS ConnectionError — %s", self.name)
            return {'success': False, 'message': msg}
        except requests.exceptions.Timeout:
            _logger.warning("ePOS Timeout — %s", self.name)
            return {'success': False, 'message': _("Délai d'attente dépassé pour l'imprimante.")}
        except Exception as exc:
            _logger.exception("ePOS inattendu — %s", self.name)
            return {'success': False, 'message': str(exc)}

        if resp.status_code != 200:
            return {'success': False, 'message': _("Erreur HTTP %s") % resp.status_code}

        # Analyse de la réponse XML Epson
        try:
            root = ET.fromstring(resp.text)
            ns = {'e': EPOS_NS}
            response_el = root.find('.//e:response', ns)
            if response_el is not None and response_el.get('success') == 'false':
                code   = response_el.get('code', '?')
                status = response_el.get('status', '?')
                _logger.warning("ePOS erreur imprimante — code=%s status=%s", code, status)
                return {'success': False, 'message': _("Erreur imprimante: %s") % code}
        except ET.ParseError:
            pass  # Certains firmware Epson ne renvoient pas de XML valide

        return {'success': True, 'message': 'OK'}

    # ── Génération XML reçu CLIENT ────────────────────────────────────────────

    def _build_receipt_xml(self, order):
        """Construit le XML ePOS du reçu client complet."""
        company  = order.company_id
        currency = order.currency_id

        def fmt(amount):
            return currency.format(amount) if currency else '%.2f' % amount

        root = ET.Element('epos-print', xmlns=EPOS_NS)

        # ── En-tête société ───────────────────────────────────────────────────
        _text(root, _center(company.name or '') + '\n',
              align='center', em='true', width='2', height='2')

        if company.street:
            _text(root, _center(company.street) + '\n', align='center')
        if company.city:
            _text(root, _center(company.city) + '\n', align='center')
        if company.phone:
            _text(root, _center('Tél: ' + company.phone) + '\n', align='center')
        if company.vat:
            _text(root, _center('TVA: ' + company.vat) + '\n', align='center')

        _separator(root)

        # ── Informations commande ─────────────────────────────────────────────
        _text(root, _lj_rj('Reçu:', order.name or '') + '\n')
        date_str = (order.date_order.strftime('%d/%m/%Y %H:%M')
                    if order.date_order else '')
        _text(root, _lj_rj('Date:', date_str) + '\n')

        if hasattr(order, 'table_id') and order.table_id:
            _text(root, _lj_rj('Table:', order.table_id.name) + '\n')

        employee = (order.employee_id.name
                    if hasattr(order, 'employee_id') and order.employee_id
                    else None)
        if employee:
            _text(root, _lj_rj('Caissier:', employee) + '\n')

        if order.partner_id:
            _text(root, _lj_rj('Client:', order.partner_id.name[:20]) + '\n')

        _separator(root)

        # ── Lignes de commande ────────────────────────────────────────────────
        for line in order.lines:
            name = (line.product_id.name or '')
            price_line = fmt(line.price_subtotal_incl)

            # Nom + prix sur une ligne (avec wrapping si nom long)
            if len(name) > PAPER_COLS - len(price_line) - 1:
                # Nom trop long : on tronque proprement
                max_len = PAPER_COLS - len(price_line) - 2
                name = name[:max_len]

            _text(root, _lj_rj(name, price_line) + '\n', em='true')

            # Quantité × prix unitaire
            qty_str = '%.4g' % line.qty
            unit_str = '  %s × %s' % (qty_str, fmt(line.price_unit))
            _text(root, unit_str + '\n')

            # Remise
            if line.discount:
                _text(root, '  Remise: %.0f%%\n' % line.discount)

            # Note de ligne
            if hasattr(line, 'note') and line.note:
                for note_line in textwrap.wrap('  ↳ ' + line.note, PAPER_COLS):
                    _text(root, note_line + '\n')

        _separator(root)

        # ── Totaux ────────────────────────────────────────────────────────────
        if order.amount_tax:
            subtotal_ht = order.amount_total - order.amount_tax
            _text(root, _lj_rj('Sous-total HT:', fmt(subtotal_ht)) + '\n')
            _text(root, _lj_rj('TVA:', fmt(order.amount_tax)) + '\n')

        # Total en double hauteur (effet visuel)
        total_left  = 'TOTAL'
        total_right = fmt(order.amount_total)
        _text(root,
              ' ' + _lj_rj(total_left, total_right, PAPER_COLS - 2) + '\n',
              em='true', width='2', height='2')

        _separator(root)

        # ── Paiements ─────────────────────────────────────────────────────────
        for pay in order.payment_ids:
            _text(root,
                  _lj_rj(pay.payment_method_id.name, fmt(pay.amount)) + '\n')

        change = getattr(order, 'amount_return', 0) or 0
        if change > 0:
            _text(root, _lj_rj('Monnaie rendue:', fmt(change)) + '\n')

        _separator(root)

        # ── Pied de page ──────────────────────────────────────────────────────
        _text(root, _center('Merci de votre visite !') + '\n', align='center')
        _text(root, _center('Bonne journée') + '\n', align='center')

        _feed(root, 3)
        _cut(root)

        return '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(root, encoding='unicode')

    # ── Génération XML ticket CUISINE / BAR ───────────────────────────────────

    def _build_kitchen_xml(self, order):
        """
        Construit le XML ePOS du ticket de préparation.
        Filtre les lignes selon les catégories configurées sur l'imprimante.
        Retourne None si aucune ligne ne correspond.
        """
        # Récupérer les catégories de cette imprimante
        cat_ids = set(self.product_categories_ids.ids)

        # Filtrer les lignes de commande
        if cat_ids:
            lines = order.lines.filtered(
                lambda l: bool(l.product_id.pos_categ_ids & self.product_categories_ids)
            )
        else:
            # Si aucune catégorie configurée → imprime tout
            lines = order.lines

        if not lines:
            return None

        root = ET.Element('epos-print', xmlns=EPOS_NS)

        # ── Station (nom de l'imprimante = nom de la station) ─────────────────
        station_name = self.name.upper()
        _text(root, _center('=== ' + station_name + ' ===') + '\n',
              align='center', em='true', width='2', height='2')

        _feed(root, 1)

        # ── Informations commande ─────────────────────────────────────────────
        date_str = (order.date_order.strftime('%H:%M')
                    if order.date_order else '')

        if hasattr(order, 'table_id') and order.table_id:
            _text(root, _center('TABLE: ' + order.table_id.name) + '\n',
                  align='center', em='true', width='2', height='2')

        _text(root, _lj_rj(order.name or '', date_str) + '\n')

        if hasattr(order, 'employee_id') and order.employee_id:
            _text(root, _center(order.employee_id.name) + '\n', align='center')

        _separator(root)

        # ── Articles (sans prix — grande police) ──────────────────────────────
        for line in lines:
            name = line.product_id.name or ''
            qty  = '%.4g' % line.qty

            # Quantité en gros à gauche, nom à droite
            qty_display = '[×%s]' % qty
            _text(root,
                  _lj_rj(qty_display, '') + '\n',
                  em='true', width='2', height='2')
            # Nom du produit (normal width pour tenir sur la ligne)
            for chunk in textwrap.wrap(name, PAPER_COLS):
                _text(root, '  ' + chunk + '\n', em='true')

            # Variante / options
            if hasattr(line, 'attribute_value_ids') and line.attribute_value_ids:
                variants = ', '.join(line.attribute_value_ids.mapped('name'))
                _text(root, '  → ' + variants + '\n')

            # Note de ligne
            if hasattr(line, 'note') and line.note:
                for note_line in textwrap.wrap('  !! ' + line.note.upper(), PAPER_COLS):
                    _text(root, note_line + '\n', em='true')

            _feed(root, 1)

        _separator(root)

        # ── Note globale de commande ───────────────────────────────────────────
        if hasattr(order, 'note') and order.note:
            _text(root, 'NOTE:\n', em='true')
            for note_line in textwrap.wrap(order.note, PAPER_COLS):
                _text(root, '  ' + note_line + '\n')
            _separator(root)

        _feed(root, 3)
        _cut(root)

        return '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(root, encoding='unicode')
