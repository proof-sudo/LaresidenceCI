# -*- coding: utf-8 -*-
"""
pos_epos_direct — Impression ePOS directe sans IoT Box.

Architecture : Python génère le XML ESC/POS et retourne (xml, ip) au navigateur.
Le navigateur envoie le XML directement à l'imprimante sur le réseau local.
Latence : ~2ms (réseau local) au lieu du round-trip cloud.
"""

import logging
import textwrap
import xml.etree.ElementTree as ET

from odoo import fields, models, api, _

_logger = logging.getLogger(__name__)

# ─── Constantes formatage ────────────────────────────────────────────────────

PAPER_COLS = 42
SEPARATOR = '─' * PAPER_COLS
EPOS_NS = "http://www.epson-pos.com/schemas/2011/03/epos-print"

# ─── Helpers XML ─────────────────────────────────────────────────────────────

def _el(parent, tag, attrib=None, text=None):
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

    # ── Points d'entrée — retournent (xml, ip) au navigateur ─────────────────

    @api.model
    def _get_epos_receipt_xml(self, printer_id, order_id):
        """
        Génère le XML ESC/POS du reçu client et le retourne au navigateur.
        Le navigateur envoie ensuite le XML directement à l'imprimante.
        Retourne {'success': bool, 'xml': str, 'ip': str} ou {'success': False, 'message': str}.
        """
        printer = self.browse(printer_id)
        ok, err = printer._check_ready()
        if not ok:
            return {'success': False, 'message': err}

        order = self.env['pos.order'].browse(order_id)
        if not order.exists():
            return {'success': False, 'message': _("Commande introuvable (id=%s).") % order_id}

        xml_str = printer._build_receipt_xml(order)
        return {'success': True, 'xml': xml_str, 'ip': printer.epson_printer_ip.strip()}

    @api.model
    def _get_epos_kitchen_xml(self, printer_id, order_id):
        """
        Génère le XML ESC/POS du ticket cuisine et le retourne au navigateur.
        Retourne {'success': True, 'xml': None} si aucune ligne pour cette station.
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
            return {'success': True, 'xml': None, 'ip': None}

        return {'success': True, 'xml': xml_str, 'ip': printer.epson_printer_ip.strip()}

    # ── Validation ───────────────────────────────────────────────────────────

    def _check_ready(self):
        if not self.exists():
            return False, _("Imprimante introuvable.")
        if not self.epson_printer_ip:
            return False, _("Adresse IP de l'imprimante non configurée.")
        return True, None

    # ── Génération XML reçu CLIENT ────────────────────────────────────────────

    def _build_receipt_xml(self, order):
        company  = order.company_id
        currency = order.currency_id

        def fmt(amount):
            return currency.format(amount) if currency else '%.2f' % amount

        root = ET.Element('epos-print', xmlns=EPOS_NS)

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

        for line in order.lines:
            name = (line.product_id.name or '')
            price_line = fmt(line.price_subtotal_incl)

            if len(name) > PAPER_COLS - len(price_line) - 1:
                max_len = PAPER_COLS - len(price_line) - 2
                name = name[:max_len]

            _text(root, _lj_rj(name, price_line) + '\n', em='true')

            qty_str = '%.4g' % line.qty
            unit_str = '  %s × %s' % (qty_str, fmt(line.price_unit))
            _text(root, unit_str + '\n')

            if line.discount:
                _text(root, '  Remise: %.0f%%\n' % line.discount)

            if hasattr(line, 'note') and line.note:
                for note_line in textwrap.wrap('  ↳ ' + line.note, PAPER_COLS):
                    _text(root, note_line + '\n')

        _separator(root)

        if order.amount_tax:
            subtotal_ht = order.amount_total - order.amount_tax
            _text(root, _lj_rj('Sous-total HT:', fmt(subtotal_ht)) + '\n')
            _text(root, _lj_rj('TVA:', fmt(order.amount_tax)) + '\n')

        total_left  = 'TOTAL'
        total_right = fmt(order.amount_total)
        _text(root,
              ' ' + _lj_rj(total_left, total_right, PAPER_COLS - 2) + '\n',
              em='true', width='2', height='2')

        _separator(root)

        for pay in order.payment_ids:
            _text(root,
                  _lj_rj(pay.payment_method_id.name, fmt(pay.amount)) + '\n')

        change = getattr(order, 'amount_return', 0) or 0
        if change > 0:
            _text(root, _lj_rj('Monnaie rendue:', fmt(change)) + '\n')

        _separator(root)

        _text(root, _center('Merci de votre visite !') + '\n', align='center')
        _text(root, _center('Bonne journée') + '\n', align='center')

        _feed(root, 3)
        _cut(root)

        return '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(root, encoding='unicode')

    # ── Génération XML ticket CUISINE / BAR ───────────────────────────────────

    def _build_kitchen_xml(self, order):
        cat_ids = set(self.product_categories_ids.ids)

        if cat_ids:
            lines = order.lines.filtered(
                lambda l: bool(l.product_id.pos_categ_ids & self.product_categories_ids)
            )
        else:
            lines = order.lines

        if not lines:
            return None

        root = ET.Element('epos-print', xmlns=EPOS_NS)

        station_name = self.name.upper()
        _text(root, _center('=== ' + station_name + ' ===') + '\n',
              align='center', em='true', width='2', height='2')

        _feed(root, 1)

        date_str = (order.date_order.strftime('%H:%M')
                    if order.date_order else '')

        if hasattr(order, 'table_id') and order.table_id:
            _text(root, _center('TABLE: ' + order.table_id.name) + '\n',
                  align='center', em='true', width='2', height='2')

        _text(root, _lj_rj(order.name or '', date_str) + '\n')

        if hasattr(order, 'employee_id') and order.employee_id:
            _text(root, _center(order.employee_id.name) + '\n', align='center')

        _separator(root)

        for line in lines:
            name = line.product_id.name or ''
            qty  = '%.4g' % line.qty

            qty_display = '[×%s]' % qty
            _text(root,
                  _lj_rj(qty_display, '') + '\n',
                  em='true', width='2', height='2')
            for chunk in textwrap.wrap(name, PAPER_COLS):
                _text(root, '  ' + chunk + '\n', em='true')

            if hasattr(line, 'attribute_value_ids') and line.attribute_value_ids:
                variants = ', '.join(line.attribute_value_ids.mapped('name'))
                _text(root, '  → ' + variants + '\n')

            if hasattr(line, 'note') and line.note:
                for note_line in textwrap.wrap('  !! ' + line.note.upper(), PAPER_COLS):
                    _text(root, note_line + '\n', em='true')

            _feed(root, 1)

        _separator(root)

        if hasattr(order, 'note') and order.note:
            _text(root, 'NOTE:\n', em='true')
            for note_line in textwrap.wrap(order.note, PAPER_COLS):
                _text(root, '  ' + note_line + '\n')
            _separator(root)

        _feed(root, 3)
        _cut(root)

        return '<?xml version="1.0" encoding="utf-8"?>' + ET.tostring(root, encoding='unicode')
