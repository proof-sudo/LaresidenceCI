# -*- coding: utf-8 -*-
"""Un passage d'étape, enregistré comme un fait daté.

Le modèle natif ne garde que l'étape courante et la date du dernier
changement. Pour savoir combien de temps un plat est resté en cuisson, il
faut une ligne par passage, fermée au moment où le plat en sort.
"""

from odoo import api, fields, models


class PrepPassage(models.Model):
    _name = 'laresidence.prep.passage'
    _description = "Passage d'un plat par une étape de préparation"
    _order = 'date_debut desc, id desc'
    _rec_name = 'product_id'

    prep_state_id = fields.Many2one(
        'pos.prep.state', string="Suivi de préparation",
        required=True, ondelete='cascade', index=True)
    prep_line_id = fields.Many2one(
        'pos.prep.line', string="Ligne de préparation",
        related='prep_state_id.prep_line_id', store=True, index=True)
    prep_order_id = fields.Many2one(
        'pos.prep.order', string="Commande de préparation",
        related='prep_line_id.prep_order_id', store=True, index=True)
    pos_order_id = fields.Many2one(
        'pos.order', string="Commande en caisse",
        related='prep_order_id.pos_order_id', store=True, index=True)
    product_id = fields.Many2one(
        'product.product', string="Plat",
        related='prep_line_id.product_id', store=True, index=True)
    quantite = fields.Float(
        string="Quantité", related='prep_line_id.quantity', store=True)
    table_id = fields.Many2one(
        'restaurant.table', string="Table",
        related='pos_order_id.table_id', store=True, index=True,
        help="Plus parlant que le numéro de commande, qui reste « / » tant "
             "que la commande n'est pas encaissée.")

    stage_id = fields.Many2one(
        'pos.prep.stage', string="Étape", required=True, index=True)
    display_id = fields.Many2one(
        'pos.prep.display', string="Poste",
        related='stage_id.prep_display_id', store=True, index=True)

    date_debut = fields.Datetime(string="Entrée dans l'étape", required=True, index=True)
    date_fin = fields.Datetime(string="Sortie de l'étape", index=True)
    en_cours = fields.Boolean(
        string="En cours", compute='_compute_en_cours', store=True, index=True)

    duree = fields.Float(
        string="Durée (min)", compute='_compute_duree', store=True,
        help="Durée du passage, une fois l'étape quittée. Vaut zéro tant que "
             "le plat est encore dans l'étape.")
    duree_courante = fields.Float(
        string="Durée écoulée (min)", compute='_compute_duree_courante',
        help="Durée réelle, y compris pour une étape encore en cours.")

    seuil = fields.Integer(
        string="Seuil d'alerte (min)", related='stage_id.alert_timer', store=True)
    depassement = fields.Boolean(
        string="Hors délai", compute='_compute_depassement', store=True, index=True)
    alerte = fields.Boolean(
        string="En alerte", compute='_compute_duree_courante',
        help="Étape encore en cours qui a déjà dépassé son seuil. Non "
             "stocké : un champ stocké ne se recalcule pas avec le temps "
             "qui passe, et resterait à faux pendant que le plat attend.")

    user_id = fields.Many2one(
        'res.users', string="Enregistré par", index=True,
        default=lambda self: self.env.user)
    employee_id = fields.Many2one(
        'hr.employee', string="Serveur", index=True,
        help="Caissier connecté en caisse au moment de la validation. "
             "L'utilisateur Odoo est le même pour toute la salle : c'est "
             "l'employé qui dit qui a réellement servi.")
    force = fields.Boolean(
        string="Validé sans passage au passe", index=True,
        help="Le plat a été déclaré servi alors que la cuisine ne l'avait pas "
             "marqué prêt. La mesure de temps est donc approximative.")

    # ------------------------------------------------------------------
    @api.depends('date_fin')
    def _compute_en_cours(self):
        for passage in self:
            passage.en_cours = not passage.date_fin

    @api.depends('date_debut', 'date_fin')
    def _compute_duree(self):
        for passage in self:
            if passage.date_debut and passage.date_fin:
                delta = passage.date_fin - passage.date_debut
                passage.duree = delta.total_seconds() / 60.0
            else:
                passage.duree = 0.0

    @api.depends('date_debut', 'date_fin', 'seuil')
    def _compute_duree_courante(self):
        maintenant = fields.Datetime.now()
        for passage in self:
            if not passage.date_debut:
                passage.duree_courante = 0.0
                passage.alerte = False
                continue
            fin = passage.date_fin or maintenant
            passage.duree_courante = (fin - passage.date_debut).total_seconds() / 60.0
            passage.alerte = bool(
                not passage.date_fin and passage.seuil
                and passage.duree_courante > passage.seuil)

    @api.depends('duree', 'seuil', 'en_cours')
    def _compute_depassement(self):
        for passage in self:
            # Une étape encore en cours n'est pas déclarée hors délai : le
            # champ est stocké, il ne se recalcule pas avec le temps qui passe.
            # Le dépassement en direct se lit sur l'écran de préparation.
            passage.depassement = bool(
                passage.seuil and not passage.en_cours and passage.duree > passage.seuil)
