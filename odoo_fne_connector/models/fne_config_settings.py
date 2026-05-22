# -*- coding: utf-8 -*-
import requests
from odoo import models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """Configuration FNE intégrée dans les paramètres généraux d'Odoo."""
    _inherit = 'res.config.settings'

    fne_api_key = fields.Char(
        string="API Key FNE",
        config_parameter='fne.api_key',
        help="Clé API fournie par la DGI pour l'accès au service FNE",
    )
    fne_mode = fields.Selection(
        [('test', 'Test'), ('prod', 'Production')],
        string="Mode",
        default='test',
        config_parameter='fne.mode',
        help="Environnement d'exécution (Test ou Production)",
    )
    fne_auto_send = fields.Boolean(
        string="Envoi automatique après validation",
        config_parameter='fne.auto_send',
        help="Si coché, les factures de vente sont automatiquement envoyées à la DGI après validation",
    )
    fne_test_url = fields.Char(
        string="URL Test",
        default="http://54.247.95.108/ws",
        config_parameter='fne.test_url',
    )
    fne_prod_url = fields.Char(
        string="URL Production",
        default="https://www.services.fne.dgi.gouv.ci/ws",
        config_parameter='fne.prod_url',
    )
    fne_point_de_vente = fields.Char(
        string="Point de Vente",
        config_parameter='fne.point_de_vente',
        help="Identifiant du point de vente (ex: SIEGE, AGENCE PLATEAU…)",
    )
    fne_establishment = fields.Char(
        string="Établissement",
        config_parameter='fne.establishment',
        help="Raison sociale telle qu'elle apparaîtra sur la facture certifiée",
    )
    fne_footer = fields.Char(
        string="Pied de page FNE",
        default="Merci pour votre confiance",
        config_parameter='fne.footer',
        help="Message affiché en pied de page sur les factures certifiées",
    )

    def action_test_fne_connection(self):
        """Teste la connexion vers l'API FNE et affiche le résultat."""
        api_key = (self.fne_api_key or '').strip()
        mode = (self.fne_mode or 'test').lower()
        base_url = (self.fne_prod_url if mode == 'prod' else self.fne_test_url or '').strip()

        if not api_key:
            raise UserError(_("Veuillez d'abord renseigner une clé API FNE."))
        if not base_url:
            raise UserError(_("Veuillez d'abord renseigner l'URL de l'API FNE."))

        endpoint = base_url.rstrip('/') + "/external/invoices/sign"
        headers = {
            'Authorization': f"Bearer {api_key}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        try:
            # Envoi d'un payload vide volontairement pour tester l'authentification :
            # - 400 Bad Request  → URL joignable et clé valide (payload rejeté, c'est normal)
            # - 401 Unauthorized → clé API invalide
            # - Erreur réseau    → URL non joignable
            resp = requests.post(endpoint, headers=headers, json={}, timeout=10)

            if resp.status_code == 401:
                raise UserError(_(
                    "Connexion échouée : clé API refusée (401 Unauthorized).\n"
                    "Vérifiez la clé API dans votre espace FNE."
                ))

            _logger.info("[FNE] Test connexion %s → HTTP %s", endpoint, resp.status_code)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Connexion FNE OK"),
                    'message': _(
                        "L'API FNE est joignable en mode %s (HTTP %s)."
                    ) % (mode.upper(), resp.status_code),
                    'type': 'success',
                    'sticky': False,
                },
            }

        except requests.ConnectionError:
            raise UserError(_(
                "Impossible de joindre l'URL :\n%s\n\n"
                "Vérifiez l'URL et la connexion réseau."
            ) % endpoint)
        except requests.Timeout:
            raise UserError(_("Délai dépassé en tentant de joindre :\n%s") % endpoint)
