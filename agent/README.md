# Agent de relais d'impression — pos_print_relay_agent.py

Contourne la restriction iOS "Local Network Access" (Safari/iPad ne peut pas
contacter une IP locale depuis une page web) en inversant le sens de la
communication : le PC va chercher les jobs sur Odoo.sh au lieu qu'Odoo.sh
(ou le navigateur) essaie de joindre l'imprimante directement.

## Prérequis
- Python 3.8+
- `pip install requests`
- Le module `pos_epos_direct` v19.0.2+ installé sur l'instance Odoo

## Configuration

1. Sur Odoo : Réglages > Technique > Paramètres système > Nouveau
   - Clé : `pos_epos_direct.relay_token`
   - Valeur : une chaîne aléatoire longue, générée par exemple avec :
     `python3 -c "import secrets; print(secrets.token_hex(32))"`

2. Dans `pos_print_relay_agent.py`, renseigner :
   - `ODOO_URL` : l'URL de l'instance (ex: `https://laresidenceci.odoo.com`)
   - `RELAY_TOKEN` : la même valeur que le paramètre système ci-dessus

## Lancement

```bash
pip install requests
python pos_print_relay_agent.py
```

## Faire tourner en service Windows (démarrage automatique)

Utiliser [NSSM](https://nssm.cc/) :

```bash
nssm install PosPrintRelay "C:\Python3\python.exe" "C:\chemin\vers\pos_print_relay_agent.py"
nssm start PosPrintRelay
```

Ou via le Planificateur de tâches Windows : déclencheur "Au démarrage de
l'ordinateur", action = lancer le script, case "Exécuter que l'utilisateur
soit connecté ou non" cochée.
