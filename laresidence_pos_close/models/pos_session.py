# -*- coding: utf-8 -*-
"""Fermeture automatique d'une session de caisse.

Le module ne ferme jamais « dans le doute » : il énumère d'abord tout ce qui
est encore en cours, et ne fait quelque chose que si la liste est vide. Quand
elle ne l'est pas, il nomme précisément les éléments bloquants dans l'alerte,
pour que le responsable sache quoi vérifier plutôt que d'aller chercher.
"""

import logging
from datetime import timedelta

import pytz

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# Au-delà de cette durée après l'heure cible, on cesse de tenter : sans cette
# fenêtre, une heure de fermeture fixée à 03h00 serait considérée comme
# « dépassée » dès 23h00 le soir même.
AUTO_CLOSE_WINDOW_HOURS = 4


class PosSession(models.Model):
    _inherit = 'pos.session'

    # ------------------------------------------------------------------
    # Diagnostic
    # ------------------------------------------------------------------
    def _laresidence_auto_close_blockers(self):
        """Retourne la liste, en clair, de ce qui empêche la fermeture."""
        self.ensure_one()
        config = self.config_id
        blocages = []

        brouillons = self.order_ids.filtered(lambda o: o.state == 'draft')
        if brouillons:
            # restaurant.table n'a pas de champ « name » en Odoo 19 :
            # table_number, et display_name en repli.
            tables = [o.table_id.table_number or o.table_id.display_name
                      for o in brouillons if o.table_id]
            detail = (" (tables %s)" % ", ".join(str(t) for t in tables if t)) if tables else ""
            blocages.append("%s commande(s) encore ouverte(s)%s" % (len(brouillons), detail))

        if config.auto_close_block_on_prep:
            en_prep = self.env['pos.prep.state'].search([
                ('todo', '=', True),
                ('prep_line_id.prep_order_id.pos_order_id.session_id', '=', self.id),
            ])
            if en_prep:
                etapes = sorted({s.stage_id.display_name for s in en_prep if s.stage_id})
                detail = (" à l'étape %s" % ", ".join(etapes)) if etapes else ""
                blocages.append("%s préparation(s) en attente%s" % (len(en_prep), detail))

        delai = max(config.auto_close_idle_minutes or 0, 0)
        if delai:
            limite = fields.Datetime.now() - timedelta(minutes=delai)
            recentes = self.env['pos.order'].search_count([
                ('session_id', '=', self.id),
                ('create_date', '>', limite),
            ])
            if recentes:
                blocages.append("%s commande(s) créée(s) dans les %s dernières minutes"
                                % (recentes, delai))

        return blocages

    # ------------------------------------------------------------------
    # Exécution
    # ------------------------------------------------------------------
    def _laresidence_try_auto_close(self):
        self.ensure_one()
        config = self.config_id
        blocages = self._laresidence_auto_close_blockers()

        if blocages:
            resultat = "Fermeture reportée — " + " ; ".join(blocages)
            self._laresidence_notify(resultat, bloquant=True)
        else:
            resultat = self._laresidence_do_close()

        config.sudo().write({
            'auto_close_last_attempt': fields.Datetime.now(),
            'auto_close_last_result': resultat[:255],
        })
        self._laresidence_trace(resultat)
        _logger.info("laresidence_pos_close : %s — %s", self.name, resultat)
        return resultat

    def _laresidence_do_close(self):
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self.action_pos_session_closing_control()
        except Exception as exc:
            resultat = "Verrouillage impossible (%s)" % exc
            self._laresidence_notify(resultat, bloquant=True)
            return resultat

        resultat = "Session verrouillée automatiquement — comptage à faire au matin."

        if self.config_id.auto_close_full:
            fermeture = getattr(self, 'action_pos_session_close', None)
            if not fermeture:
                return resultat + " Clôture comptable indisponible sur cette version."
            try:
                with self.env.cr.savepoint():
                    fermeture()
                resultat = "Session clôturée et comptabilisée automatiquement."
            except Exception as exc:
                resultat = ("Session verrouillée ; clôture comptable non aboutie (%s). "
                            "À terminer manuellement." % exc)
                self._laresidence_notify(resultat, bloquant=True)

        return resultat

    # ------------------------------------------------------------------
    # Traces et alertes
    # ------------------------------------------------------------------
    def _laresidence_trace(self, message):
        if hasattr(self, 'message_post'):
            try:
                self.message_post(body=message)
            except Exception:
                _logger.debug("laresidence_pos_close : trace impossible sur %s", self.name)

    def _laresidence_notify(self, message, bloquant=False):
        groupe = self.env.ref('laresidence_pos_close.group_pos_close_notified',
                              raise_if_not_found=False)
        if not groupe:
            return False
        emails = [u.email for u in groupe.user_ids if u.email]
        if not emails:
            return False

        titre = ("Caisse non fermée — %s" if bloquant else "Caisse fermée — %s") % self.config_id.name
        corps = (
            "<div style=\"font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#1a1c20\">"
            "<p><b>%s</b></p>"
            "<p>Session <b>%s</b>, ouverte depuis le %s.</p>"
            "<p>%s</p>"
            "%s"
            "</div>" % (
                titre,
                self.name,
                self.start_at or '',
                message,
                "<p style='color:#8a5a00'>La caisse est restée ouverte. "
                "Merci de vérifier ce qui est encore en cours, puis de la fermer.</p>"
                if bloquant else "",
            )
        )
        self.env['mail.mail'].sudo().create({
            'subject': titre,
            'body_html': corps,
            'email_to': ','.join(emails),
            'auto_delete': False,
        })
        return True

    # ------------------------------------------------------------------
    # Tâche planifiée
    # ------------------------------------------------------------------
    @api.model
    def _cron_auto_close(self):
        configs = self.env['pos.config'].search([('auto_close_enabled', '=', True)])
        traitees = 0

        for config in configs:
            fuseau = pytz.timezone(config.company_id.partner_id.tz or 'UTC')
            maintenant = pytz.utc.localize(fields.Datetime.now()).astimezone(fuseau)
            heure = config.auto_close_time or 0.0
            cible = maintenant.replace(hour=int(heure) % 24,
                                       minute=int(round((heure % 1) * 60)) % 60,
                                       second=0, microsecond=0)
            if not (cible <= maintenant < cible + timedelta(hours=AUTO_CLOSE_WINDOW_HOURS)):
                continue

            sessions = self.search([
                ('config_id', '=', config.id),
                ('state', 'in', ('opening_control', 'opened')),
            ])
            for session in sessions:
                # Une session ouverte après l'heure cible appartient au service suivant.
                if session.start_at and pytz.utc.localize(session.start_at).astimezone(fuseau) >= cible:
                    continue
                session._laresidence_try_auto_close()
                traitees += 1

        return traitees
