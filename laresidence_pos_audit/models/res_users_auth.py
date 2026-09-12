# -*- coding: utf-8 -*-
"""Traçage des connexions, réussies comme échouées.

Une série de tentatives infructueuses sur un compte, la nuit, depuis une
adresse inconnue, est le premier signe d'une intrusion. Odoo n'en garde rien
d'exploitable en base : ces événements ne vivent que dans le journal du
serveur, qui tourne et disparaît.

Précautions prises, parce qu'une erreur ici empêcherait tout le monde de se
connecter :

- la signature d'origine est transmise telle quelle (``*args``/``**kwargs``),
  une évolution d'Odoo ne peut donc pas casser l'appel ;
- le comportement d'origine est exécuté en premier, et son résultat comme son
  exception sont rendus intacts ;
- toute la journalisation est enfermée dans un ``try`` qui avale tout ;
- un interrupteur d'arrêt permet de la désactiver sans redéployer, via le
  paramètre système ``laresidence_pos_audit.trace_auth`` mis à ``0``.
"""

import logging

from odoo import SUPERUSER_ID, api, models

_logger = logging.getLogger(__name__)

PARAM_TRACE_AUTH = 'laresidence_pos_audit.trace_auth'


def _journaliser_hors_transaction(base, valeurs):
    """Écrit dans une transaction séparée.

    Indispensable : lors d'un échec de connexion, la transaction d'origine est
    annulée. Une trace écrite dedans disparaîtrait avec elle — précisément le
    cas qu'il faut conserver.
    """
    try:
        import odoo
        try:
            from odoo.modules.registry import Registry
            registre = Registry(base)
        except Exception:
            registre = odoo.registry(base)
        with registre.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            if env['ir.config_parameter'].get_param(PARAM_TRACE_AUTH, '1') in ('0', 'false', 'False'):
                return
            valeurs.update(env['laresidence.pos.audit']._contexte_requete())
            env['laresidence.pos.audit'].create([valeurs])
            cr.commit()
    except Exception:
        _logger.debug("laresidence_pos_audit : trace d'authentification impossible", exc_info=True)


class ResUsersAuth(models.Model):
    _inherit = 'res.users'

    def _login(self, *args, **kwargs):
        """Observe l'authentification sans jamais s'interposer.

        Signature relevée sur l'instance et non supposée : en Odoo 19, _login
        est une méthode d'instance appelée ``self._login(credential,
        user_agent_env=...)``. La déclarer méthode de classe décalait tous les
        arguments d'un cran et rendait toute connexion impossible — le défaut a
        été trouvé en tentant réellement de se connecter.

        Les arguments sont transmis tels quels : une évolution de signature ne
        peut plus rien casser ici.
        """
        base = self.env.cr.dbname
        identifiant = None
        try:
            credential = args[0] if args else kwargs.get('credential')
            if isinstance(credential, dict):
                identifiant = credential.get('login')
            elif isinstance(credential, str):
                identifiant = credential
        except Exception:
            identifiant = None

        try:
            resultat = super()._login(*args, **kwargs)
        except Exception as echec:
            _journaliser_hors_transaction(base, {
                'event_type': 'auth_failure',
                'new_value': (identifiant or '')[:256] or False,
                'note': "Tentative de connexion refusée : %s" % type(echec).__name__,
            })
            raise

        _journaliser_hors_transaction(base, {
            'event_type': 'auth_success',
            'new_value': (identifiant or '')[:256] or False,
            'note': "Connexion acceptée.",
        })
        return resultat
