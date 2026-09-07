# -*- coding: utf-8 -*-
"""Tests de non-régression du connecteur FNE : certification et avoirs.

Aucun appel réseau : _request_fne est remplacé par un faux qui enregistre
le payload envoyé et renvoie une réponse DGI plausible.
"""
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.odoo_fne_connector.models.account_move_inherit import AccountMove as FneAccountMove


@tagged('post_install', '-at_install', 'fne')
class TestFneRefund(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_param('fne.api_key', 'TEST-KEY')
        icp.set_param('fne.mode', 'test')
        icp.set_param('fne.point_de_vente', 'PDV-TEST')
        icp.set_param('fne.establishment', 'ETAB-TEST')
        cls.tax18 = cls.env['account.tax'].create({
            'name': 'TVA 18%', 'amount': 18, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': cls.env.company.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Extra Event', 'type': 'service', 'list_price': 100,
        })

    # ------------------------------------------------------------------ helpers

    def _invoice(self, lines):
        """lines : liste de (prix unitaire, quantité), toutes sur le même produit."""
        inv = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id, 'quantity': qty, 'price_unit': price,
                'tax_ids': [(6, 0, self.tax18.ids)],
            }) for price, qty in lines],
        })
        inv.action_post()
        return inv

    def _sign(self, inv, item_ids):
        """Certifie la facture avec une fausse réponse DGI renvoyant item_ids (dans l'ordre)."""
        resp = {
            'reference': 'REF-%s' % inv.id, 'token': 'https://verif/%s' % inv.id,
            'id': 'FNE-%s' % inv.id,
            'invoice': {'id': 'FNE-%s' % inv.id, 'items': [{'id': i} for i in item_ids]},
        }
        with patch.object(FneAccountMove, '_request_fne', return_value=resp):
            inv._execute_fne_send()
        self.assertTrue(inv.fne_sent)
        self.assertEqual(inv.invoice_id_from_fne, 'FNE-%s' % inv.id)

    def _full_refund(self, inv):
        refund = inv._reverse_moves([{'date': fields.Date.today(), 'invoice_date': fields.Date.today()}], cancel=False)
        refund.action_post()
        return refund

    def _partial_refund(self, inv, lines):
        refund = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': inv.partner_id.id,
            'invoice_date': fields.Date.today(),
            'reversed_entry_id': inv.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id, 'quantity': qty, 'price_unit': price,
                'tax_ids': [(6, 0, self.tax18.ids)],
            }) for price, qty in lines],
        })
        refund.action_post()
        return refund

    def _certify_refund(self, refund):
        """Certifie l'avoir et renvoie le payload envoyé à la DGI (ou lève l'erreur métier)."""
        sent = {}

        def fake_request(move, method, url, headers, json_body=None, timeout=30):
            sent['method'], sent['url'], sent['body'] = method, url, json_body
            return {'reference': 'AV-%s' % refund.id, 'token': 'https://verif/av', 'warning': False, 'balance_funds': 10}

        with patch.object(FneAccountMove, '_request_fne', fake_request):
            refund._execute_fne_send()
        return sent

    # -------------------------------------------------------------------- tests

    def test_01_sign_maps_items_only_on_sent_lines(self):
        """Une ligne à 0 F n'est pas envoyée : les tickets DGI vont aux lignes réellement envoyées."""
        inv = self._invoice([(0, 1), (389900, 1), (108000, 1)])
        self._sign(inv, ['ITEM-A', 'ITEM-B'])
        lines = inv.invoice_line_ids.filtered('product_id').sorted('sequence')
        self.assertFalse(lines[0].fne_item_id, "la ligne à 0 F ne doit pas recevoir de ticket")
        self.assertEqual(lines[1].fne_item_id, 'ITEM-A')
        self.assertEqual(lines[2].fne_item_id, 'ITEM-B')

    def test_02_full_refund_duplicate_product_uses_distinct_items(self):
        """Cas INV/2026/00154 : même produit sur 2 lignes -> 2 tickets distincts, pas 2x le même."""
        inv = self._invoice([(389900, 1), (108000, 1)])
        self._sign(inv, ['ITEM-A', 'ITEM-B'])
        refund = self._full_refund(inv)
        sent = self._certify_refund(refund)
        self.assertIn('/external/invoices/FNE-%s/refund' % inv.id, sent['url'])
        self.assertEqual(sent['body']['items'], [
            {'id': 'ITEM-A', 'quantity': 1.0},
            {'id': 'ITEM-B', 'quantity': 1.0},
        ])
        self.assertTrue(refund.fne_sent)
        self.assertEqual(
            sorted(refund.invoice_line_ids.filtered('product_id').mapped('fne_refund_item_id')),
            ['ITEM-A', 'ITEM-B'],
        )

    def test_03_partial_refund_picks_line_with_same_price(self):
        inv = self._invoice([(389900, 1), (108000, 1)])
        self._sign(inv, ['ITEM-A', 'ITEM-B'])
        refund = self._partial_refund(inv, [(108000, 1)])
        sent = self._certify_refund(refund)
        self.assertEqual(sent['body']['items'], [{'id': 'ITEM-B', 'quantity': 1.0}])

    def test_04_partial_refund_quantity_on_multi_qty_line(self):
        inv = self._invoice([(5000, 3)])
        self._sign(inv, ['ITEM-A'])
        refund = self._partial_refund(inv, [(5000, 2)])
        sent = self._certify_refund(refund)
        self.assertEqual(sent['body']['items'], [{'id': 'ITEM-A', 'quantity': 2.0}])

    def test_05_refund_more_than_invoiced_is_blocked(self):
        inv = self._invoice([(5000, 2)])
        self._sign(inv, ['ITEM-A'])
        refund = self._partial_refund(inv, [(5000, 3)])
        with self.assertRaises(UserError):
            self._certify_refund(refund)
        self.assertFalse(refund.fne_sent)

    def test_06_cumulative_refunds_are_blocked(self):
        """Deux avoirs complets successifs : le second doit être refusé avant tout appel DGI."""
        inv = self._invoice([(389900, 1), (108000, 1)])
        self._sign(inv, ['ITEM-A', 'ITEM-B'])
        first = self._full_refund(inv)
        self._certify_refund(first)
        second = self._full_refund(inv)
        with self.assertRaises(UserError):
            self._certify_refund(second)
        self.assertFalse(second.fne_sent)

    def test_07_cumulative_partial_refunds_within_limit(self):
        """Deux avoirs partiels dont la somme ne dépasse pas la facture passent."""
        inv = self._invoice([(5000, 3)])
        self._sign(inv, ['ITEM-A'])
        self._certify_refund(self._partial_refund(inv, [(5000, 2)]))
        sent = self._certify_refund(self._partial_refund(inv, [(5000, 1)]))
        self.assertEqual(sent['body']['items'], [{'id': 'ITEM-A', 'quantity': 1.0}])
        with self.assertRaises(UserError):
            self._certify_refund(self._partial_refund(inv, [(5000, 1)]))

    def test_08_refund_without_origin_is_blocked(self):
        refund = self.env['account.move'].create({
            'move_type': 'out_refund', 'partner_id': self.partner_a.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {'product_id': self.product.id, 'quantity': 1, 'price_unit': 1000,
                                         'tax_ids': [(6, 0, self.tax18.ids)]})],
        })
        refund.action_post()
        with self.assertRaises(UserError):
            self._certify_refund(refund)
