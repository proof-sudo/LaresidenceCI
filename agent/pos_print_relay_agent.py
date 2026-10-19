#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pos_print_relay_agent.py — Agent de relais d'impression pour La Résidence CI.

Tourne en tâche de fond sur le PC local (même réseau que l'imprimante).
Interroge Odoo.sh en polling (connexion SORTANTE, aucun port forwarding requis),
récupère les jobs d'impression en attente, et les envoie directement à
l'imprimante ePOS en local.

Installation :
    pip install requests
    python pos_print_relay_agent.py

Pour le faire tourner en service Windows au démarrage, voir NSSM
(https://nssm.cc) ou le Planificateur de tâches Windows.
"""

import logging
import time

import requests

# ── Configuration ────────────────────────────────────────────────────────────

ODOO_URL = "https://laresidenceci.odoo.com"   # base URL de l'instance Odoo.sh
RELAY_TOKEN = "REMPLACER_PAR_LE_TOKEN_GENERE"  # doit matcher ir.config_parameter
POLL_INTERVAL_SECONDS = 2
HTTP_TIMEOUT = 5  # secondes, pour joindre Odoo.sh et pour joindre l'imprimante

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("print_relay")


def _rpc(path, params):
    """Appelle un endpoint JSON-RPC 'type=jsonrpc' d'Odoo (payload simplifié)."""
    url = ODOO_URL.rstrip('/') + path
    resp = requests.post(url, json=params, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_pending_jobs():
    return _rpc('/pos_print_relay/pending', {'token': RELAY_TOKEN, 'limit': 10})


def ack_job(job_id, status, error_message='', duration_ms=0):
    return _rpc('/pos_print_relay/ack', {
        'token': RELAY_TOKEN,
        'job_id': job_id,
        'status': status,
        'error_message': error_message,
        'duration_ms': duration_ms,
    })


def send_xml_to_printer(ip, xml_str, timeout=8):
    """Envoie le XML ePOS à l'imprimante en HTTP POST local (même logique
    que le cgi-bin/epos/service.cgi utilisé par Odoo nativement)."""
    url = ip if ip.startswith('http') else 'http://' + ip
    url = url.rstrip('/') + '/cgi-bin/epos/service.cgi'
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'If-Modified-Since': 'Thu, 01 Jan 1970 00:00:00 GMT',
    }
    resp = requests.post(url, data=xml_str.encode('utf-8'), headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def process_job(job):
    t0 = time.time()
    try:
        send_xml_to_printer(job['ip'], job['xml'])
        duration_ms = int((time.time() - t0) * 1000)
        ack_job(job['id'], 'sent', duration_ms=duration_ms)
        log.info("Job %s imprimé (%s) en %d ms", job['id'], job['job_type'], duration_ms)
    except Exception as exc:
        duration_ms = int((time.time() - t0) * 1000)
        ack_job(job['id'], 'error', error_message=str(exc), duration_ms=duration_ms)
        log.error("Job %s en échec (%s): %s", job['id'], job['ip'], exc)


def main_loop():
    log.info("Agent de relais d'impression démarré — cible %s", ODOO_URL)
    while True:
        try:
            result = fetch_pending_jobs()
            if not result.get('success'):
                log.warning("Réponse Odoo invalide: %s", result)
            else:
                for job in result.get('jobs', []):
                    process_job(job)
        except requests.exceptions.RequestException as exc:
            log.warning("Odoo.sh injoignable, nouvelle tentative dans %ss (%s)",
                        POLL_INTERVAL_SECONDS, exc)
        except Exception:
            log.exception("Erreur inattendue dans la boucle principale")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == '__main__':
    main_loop()
