from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import uuid
import logging

_logger = logging.getLogger(__name__)


class MobileOrder(models.Model):
    _name = "mobile.order"
    _description = "Pré-commande Mobile"
    _order = "date_order desc"
    _rec_name = "name"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ─── Identification ───────────────────────────────────────────────────────

    name = fields.Char(
        string="Référence",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nouveau')
    )
    x_tr_uuid = fields.Char(
        string='UUID Mobile',
        copy=False,
        index=True,
        readonly=True
    )
    x_tr_qr_token = fields.Char(
        string='Token QR',
        copy=False,
        readonly=True
    )

    # ─── Client & Membre ──────────────────────────────────────────────────────

    partner_id = fields.Many2one('res.partner', string="Client")
    x_tr_member_id = fields.Many2one(
        'res.partner',
        string='Membre',
        domain=[('x_tr_is_member', '=', True)]
    )

    # ─── Commande ─────────────────────────────────────────────────────────────

    date_order = fields.Datetime(
        string="Date commande",
        default=fields.Datetime.now,
        required=True
    )
    x_tr_order_mode = fields.Selection([
        ('PICKUP',   'Retrait'),
        ('DELIVERY', 'Livraison'),
        ('DINE_IN',  'Sur place'),
    ], string='Mode', default='PICKUP', required=True)
    x_tr_delivery_address = fields.Text(string='Adresse de livraison')
    note = fields.Text(string="Notes")

    lines = fields.One2many(
        'mobile.order.line',
        'mobile_order_id',
        string="Lignes"
    )

    # ─── Statut ───────────────────────────────────────────────────────────────

    x_tr_order_status = fields.Selection([
        ('PENDING',     'En attente'),
        ('CONFIRMED',   'Confirmée'),
        ('SENT_TO_POS', 'Envoyée au POS'),
        ('REJECTED',    'Rejetée'),
        ('PAID',        'Payée'),
        ('COMPLETED',   'Terminée'),
    ], string="Statut commande mobile",
       default='PENDING',
       required=True,
       index=True,
       tracking=True,
     
       
    )
    x_tr_is_mobile_order = fields.Boolean(string='Commande mobile TR', default=True)

    rejection_reason = fields.Text(string="Motif de rejet")

    # ─── Lien vers la pos.order créée ─────────────────────────────────────────

    pos_order_id = fields.Many2one(
        'pos.order',
        string="Commande POS",
        readonly=True,
        copy=False,
        ondelete='set null'
    )
    pos_order_status = fields.Selection(
        [
            ('PENDING',     'En attente'),
            ('CONFIRMED',   'Confirmée'),
            ('READY',       'Prête'),
            ('SENT_TO_POS', 'Envoyée au POS'),
            ('CANCELLED',   'Annulée'),
            ('PAID',        'Payée'),
            ('COMPLETED',   'Terminée'),
        ],
        string="Statut POS",
        related='pos_order_id.x_tr_order_status',
        store=True,
        readonly=True,
    )

    # ─── Montants calculés ────────────────────────────────────────────────────

    amount_total = fields.Float(
        compute='_compute_amounts',
        store=True,
        string="Total TTC"
    )
    amount_tax = fields.Float(
        compute='_compute_amounts',
        store=True,
        string="Taxes"
    )

    @api.depends('lines.price_subtotal_incl', 'lines.price_subtotal')
    def _compute_amounts(self):
        for order in self:
            order.amount_total = sum(order.lines.mapped('price_subtotal_incl'))
            order.amount_tax = order.amount_total - sum(
                order.lines.mapped('price_subtotal')
            )

    # ─── Create ───────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('mobile.order')
                    or _('Nouveau')
                )
            if not vals.get('x_tr_uuid'):
                vals['x_tr_uuid'] = str(uuid.uuid4())
            if not vals.get('x_tr_qr_token'):
                vals['x_tr_qr_token'] = f"mob-{uuid.uuid4().hex[:12]}"
        return super().create(vals_list)

    # ─── Workflow ─────────────────────────────────────────────────────────────

    def action_validate(self):
        """PENDING → CONFIRMED : validation humaine."""
        for order in self:
            if order.x_tr_order_status != 'PENDING':
                raise ValidationError(
                    _("Seules les commandes PENDING peuvent être validées.")
                )
            order.x_tr_order_status = 'CONFIRMED'
            _logger.info("MobileOrder %s confirmée.", order.name)

    def action_send_to_pos(self):
        """CONFIRMED → SENT_TO_POS : crée la vraie pos.order."""
        for order in self:
            if order.x_tr_order_status != 'CONFIRMED':
                raise ValidationError(
                    _("Seules les commandes CONFIRMÉES peuvent être envoyées au POS.")
                )
            if order.pos_order_id:
                raise ValidationError(
                    _("Cette commande est déjà dans le POS (%s).")
                    % order.pos_order_id.name
                )

            pos_vals = order._prepare_pos_order_valeur()
            pos_order = self.env['pos.order'].create_order_from_api(pos_vals)

            # Reprend l'UUID et QR token de la pré-commande pour cohérence mobile
            pos_order.write({
                'x_tr_uuid':     order.x_tr_uuid,
                'x_tr_qr_token': order.x_tr_qr_token,
            })

            order.write({
                'x_tr_order_status': 'SENT_TO_POS',
                'pos_order_id':      pos_order.id,
            })

            _logger.info(
                "MobileOrder %s → POS %s créée avec succès.",
                order.name, pos_order.name
            )

    def _prepare_pos_order_valeur(self):
        """
        Formate les données au format attendu par create_order_from_api().
        La session est vérifiée ici pour un message d'erreur explicite.
        """
        self.ensure_one()

        session = self.env['pos.session'].search(
            [('state', '=', 'opened')], limit=1
        )
        if not session:
            raise ValidationError(
                _("Aucune session POS ouverte. Veuillez ouvrir une session avant d'envoyer la commande.")
            )

        member = self.x_tr_member_id
        return {
            'memberId':        member.x_tr_uuid if member else '',
            'partnerId':       self.partner_id.id if self.partner_id else False,
            'dateOrder':       self.date_order.strftime('%Y-%m-%d %H:%M:%S') if self.date_order else False,
            'mode':            self.x_tr_order_mode or 'PICKUP',
            'x_tr_is_mobile_order': True,
            'deliveryAddress': self.x_tr_delivery_address or '',
            'internal_note':           self.note or '',
            'items': [{
                'menuItemId': str(line.product_id.id),
                'quantity':   line.qty,
                'unitPrice':  line.price_unit,
            } for line in self.lines],
        }
    def action_reject(self):
        self.ensure_one()
        if self.x_tr_order_status == 'SENT_TO_POS':
            raise ValidationError(
                _("Impossible de rejeter une commande déjà envoyée au POS.")
            )
        return {
            'type':      'ir.actions.act_window',
            'name':      'Rejeter la commande',
            'res_model': 'mobile.order.reject.wizard',
            'view_mode': 'form',
            'target':    'new',
            'context':   {'default_order_id': self.id},
        }
    @api.model
    def create_order_from_api(self, data):
        """
        Crée une pré-commande mobile depuis l'API.
        Point d'entrée unique pour l'app mobile.
        """
        Partner = self.env['res.partner']

        # Résolution du membre
        member = False
        if data.get('memberId'):
            member = Partner.search(
                [('x_tr_uuid', '=', data['memberId'])], limit=1
            )

        # Création de la pré-commande
        order = self.create({
            'partner_id':            member.id if member else False,
            'x_tr_member_id':        member.id if member else False,
            'x_tr_order_mode':       data.get('mode', 'PICKUP'),
            'x_tr_delivery_address': data.get('deliveryAddress', ''),
            'note':                  data.get('notes', ''),
            'x_tr_order_status':     'PENDING',
            'x_tr_is_mobile_order':  True,
        })

        # Création des lignes
        for item in data.get('items', []):
            try:
                product = self.env['product.product'].browse(int(item['menuItemId']))
            except (ValueError, KeyError):
                continue

            if not product.exists():
                _logger.warning("Produit %s introuvable, ignoré.", item.get('menuItemId'))
                continue

            taxes = product.taxes_id.filtered(
                lambda t: t.company_id == self.env.company
            )
            self.env['mobile.order.line'].create({
                'mobile_order_id': order.id,
                'product_id':      product.id,
                'qty':             item.get('quantity', 1),
                'price_unit':      item.get('unitPrice', product.lst_price),
                'tax_ids':         [(6, 0, taxes.ids)],
            })

        _logger.info("MobileOrder %s créée depuis l'API.", order.name)
        return order
    def to_staging_api_dict(self):
        """
        Réponse API pour l'app mobile.
        Format uniforme que la commande soit en staging ou envoyée au POS.
        """
        self.ensure_one()
        result = {
            'id':              self.x_tr_uuid or str(self.id),
            'stagingId':       self.name,
            'status':          self.x_tr_order_status,
            'mode':            self.x_tr_order_mode or 'PICKUP',
            'deliveryAddress': self.x_tr_delivery_address or '',
            'notes':           self.note or '',
            'totalAmount':     self.amount_total,
            'currency':        self.env.company.currency_id.name or 'XOF',
            'qrToken':         self.x_tr_qr_token or '',
            'items': [{
                'id':           str(line.id),
                'menuItemId':   str(line.product_id.id),
                'menuItemName': line.product_id.name or '',
                'quantity':     line.qty,
                'unitPrice':    line.price_unit,
                'amount':       line.price_subtotal_incl,
            } for line in self.lines],
            'member': {
                'id':        self.x_tr_member_id.x_tr_uuid if self.x_tr_member_id else '',
                'firstName': (self.x_tr_member_id.name or '').split(' ')[0] if self.x_tr_member_id else '',
                'lastName':  ' '.join((self.x_tr_member_id.name or '').split(' ')[1:]) if self.x_tr_member_id else '',
                'email':     self.x_tr_member_id.email or '' if self.x_tr_member_id else '',
            } if self.x_tr_member_id else {},
            'createdAt': self.create_date.isoformat() if self.create_date else '',
            'updatedAt': self.write_date.isoformat() if self.write_date else '',
        }

        # Si déjà envoyée au POS, ajoute le statut POS en temps réel
        if self.pos_order_id:
            result['posOrderId'] = self.pos_order_id.x_tr_uuid or str(self.pos_order_id.id)
            result['posStatus']  = self.pos_order_id.x_tr_order_status or ''

        return result


class MobileOrderLine(models.Model):
    _name = "mobile.order.line"
    _description = "Ligne de pré-commande mobile"

    mobile_order_id = fields.Many2one(
        'mobile.order',
        string="Commande Mobile",
        required=True,
        ondelete='cascade',
        index=True
    )
    product_id = fields.Many2one(
        'product.product',
        string="Produit",
        required=True
    )
    qty = fields.Float(string="Quantité", default=1.0)
    price_unit = fields.Float(string="Prix unitaire")
    discount = fields.Float(string="Remise (%)", default=0.0)
    tax_ids = fields.Many2many('account.tax', string="Taxes")

    price_subtotal = fields.Float(
        compute='_compute_price',
        store=True,
        string="Sous-total HT"
    )
    price_subtotal_incl = fields.Float(
        compute='_compute_price',
        store=True,
        string="Sous-total TTC"
    )

    @api.depends('qty', 'price_unit', 'discount', 'tax_ids',
                 'mobile_order_id.x_tr_member_id')
    def _compute_price(self):
        for line in self:
            price = line.price_unit * (1 - line.discount / 100.0)
            taxes = line.tax_ids.compute_all(
                price,
                quantity=line.qty,
                product=line.product_id,
                partner=line.mobile_order_id.x_tr_member_id
            )
            line.price_subtotal = taxes['total_excluded']
            line.price_subtotal_incl = taxes['total_included']

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Pré-remplit prix et taxes depuis le produit sélectionné."""
        if self.product_id:
            self.price_unit = self.product_id.lst_price
            self.tax_ids = self.product_id.taxes_id.filtered(
                lambda t: t.company_id == self.env.company
            )