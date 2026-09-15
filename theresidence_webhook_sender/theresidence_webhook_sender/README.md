# The Residence - Webhook Sender

Module Odoo pour envoyer automatiquement des webhooks vers l'API externe de The Residence.

## 📋 Description

Ce module gère l'envoi de webhooks sortants vers l'API The Residence lorsque des événements se produisent dans Odoo :
- Changements de statut des commandes
- Approbation/rejet/annulation de réservations
- Changements d'état des abonnements
- Mises à jour des informations membres

## 🚀 Installation

### 1. Prérequis

```bash
pip install requests
```

### 2. Installation du module

1. Copier le dossier `theresidence_webhook_sender` dans le répertoire addons d'Odoo
2. Redémarrer Odoo
3. Aller dans Apps > Update Apps List
4. Rechercher "The Residence - Webhook Sender"
5. Cliquer sur "Install"

### 3. Configuration initiale

Après installation, une configuration par défaut est automatiquement créée :
- URL : `https://api.laresidence-abidjan.com`
- API Key : `EDjN4QtXERbgGOjiNil7b40iNTIiwG3q`
- État : Actif

Vous pouvez modifier cette configuration dans **Webhooks The Residence > Configuration**

## 🔌 Intégration avec le module existant

Pour que votre module existant utilise ce nouveau service, vous devez remplacer les appels à `theresidence.webhook` par `theresidence.webhook.service`.

### Exemple de modification

**AVANT (dans votre module existant):**
```python
self.env['theresidence.webhook'].trigger_event(
    'ORDER_STATUS_CHANGED', 'order', order.x_tr_uuid,
    order.to_order_api_dict(), old, 'CONFIRMED'
)
```

**APRÈS:**
```python
self.env['theresidence.webhook.service'].trigger_event(
    'ORDER_STATUS_CHANGED', 'order', order.x_tr_uuid,
    order.to_order_api_dict(), old, 'CONFIRMED'
)
```

### Fichiers à modifier

Dans votre module **theresidence_integration** (ou équivalent) :

1. **`models/sale_order.py`** - Remplacer tous les appels (lignes 143, 156, 168, 179, 191, 246, 258, 269, 280)
2. **`models/pos_order.py`** - Remplacer tous les appels (lignes 89, 100, 111, 122, 133)

### Script de remplacement automatique

```bash
# Dans le dossier de votre module existant
find . -name "*.py" -type f -exec sed -i "s/theresidence\.webhook/theresidence.webhook.service/g" {} \;
```

## 📊 Fonctionnalités

### Configuration
- URL de l'API configurable
- Clé API sécurisée
- Timeout personnalisable
- Nombre de tentatives configurable
- Délais de retry avec backoff exponentiel

### Queue
- Stockage des événements en attente
- Priorités d'envoi
- Vue Kanban pour visualisation
- Actions de retry manuel
- Filtres avancés

### Logs
- Historique complet de toutes les tentatives
- Code HTTP et durée des requêtes
- Messages d'erreur détaillés
- Recherche et filtrage

### Monitoring
- Statistiques en temps réel
- Compteurs (envoyés, en attente, échoués)
- Vue d'ensemble de la santé du système

## 🔄 Mapping des événements

| Événement Odoo | Événement API | Description |
|----------------|---------------|-------------|
| `ORDER_STATUS_CHANGED` → CONFIRMED | `order.confirmed` | Commande confirmée |
| `ORDER_STATUS_CHANGED` → READY | `order.ready` | Commande prête |
| `ORDER_STATUS_CHANGED` → COMPLETED | `order.completed` | Commande terminée |
| `ORDER_CANCELLED` | `order.cancelled` | Commande annulée |
| `RESERVATION_STATUS_CHANGED` → APPROVED | `reservation.approved` | Réservation approuvée |
| `RESERVATION_STATUS_CHANGED` → REJECTED | `reservation.rejected` | Réservation rejetée |
| `RESERVATION_STATUS_CHANGED` → CHECKED_IN | `reservation.checked_in` | Check-in réservation |
| `RESERVATION_CANCELLED` | `reservation.cancelled` | Réservation annulée |
| `SUBSCRIPTION_STATUS_CHANGED` → ACTIVE | `subscription.activated` | Abonnement activé |
| `SUBSCRIPTION_STATUS_CHANGED` → PAUSED | `subscription.paused` | Abonnement en pause |
| `SUBSCRIPTION_STATUS_CHANGED` → ACTIVE (depuis PAUSED) | `subscription.resumed` | Abonnement repris |
| `SUBSCRIPTION_CANCELLED` | `subscription.cancelled` | Abonnement annulé |

## ⚙️ Configuration avancée

### Modifier les délais de retry

Par défaut : `1,2,4,8,16` (secondes)

Cela signifie :
- 1ère tentative échouée → retry après 1 seconde
- 2ème tentative échouée → retry après 2 secondes
- 3ème tentative échouée → retry après 4 secondes
- etc.

Vous pouvez personnaliser dans **Configuration > retry_delays**

### Activer les logs de débogage

Dans **Configuration**, cochez **Logs de débogage** pour voir les détails de chaque requête dans les logs Odoo.

### Nettoyer automatiquement les anciens enregistrements

Trois cron jobs sont configurés :
1. **Traiter la queue** : toutes les 5 minutes
2. **Nettoyer les webhooks envoyés** : après 30 jours (quotidien)
3. **Nettoyer les logs** : après 90 jours (hebdomadaire)

## 🧪 Tests

### Tester la connexion

1. Aller dans **Webhooks The Residence > Configuration**
2. Ouvrir la configuration
3. Cliquer sur **Tester la connexion**

Un webhook de test sera envoyé :
```json
{
  "event_type": "test.connection",
  "event_id": "test_1706432400",
  "timestamp": "2026-01-28T10:00:00Z",
  "entity_type": "test",
  "entity_id": "test-123",
  "data": {
    "message": "Test de connexion depuis Odoo",
    "odoo_version": "19.0"
  }
}
```

### Traiter la queue manuellement

Si des webhooks sont bloqués, vous pouvez forcer le traitement :
1. Aller dans **Configuration**
2. Cliquer sur **Traiter la queue maintenant**

### Réessayer un webhook échoué

1. Aller dans **Queue**
2. Ouvrir un webhook échoué
3. Cliquer sur **Réessayer maintenant**

## 🐛 Dépannage

### Les webhooks ne sont pas envoyés

1. Vérifier que la configuration est **Active**
2. Vérifier que le cron job **"Traiter la queue des webhooks sortants"** est actif
3. Regarder les logs Odoo pour les erreurs

### Webhooks échoués définitivement

1. Aller dans **Queue**
2. Filtrer par **Échoués**
3. Vérifier le message d'erreur dans **Dernière erreur**
4. Corriger le problème (API key, URL, etc.)
5. Cliquer sur **Réessayer maintenant**

### API Key invalide

Erreur : `HTTP 401: Unauthorized`

Solution : Vérifier la clé API dans **Configuration > API Key**

### Timeout

Erreur : `Timeout après X secondes`

Solution : Augmenter le timeout dans **Configuration > Timeout**

## 📚 Structure du module

```
theresidence_webhook_sender/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── webhook_config.py       # Configuration
│   ├── webhook_queue.py        # Queue des webhooks
│   ├── webhook_log.py          # Logs
│   └── webhook_service.py      # Service d'envoi
├── views/
│   ├── webhook_config_views.xml
│   ├── webhook_queue_views.xml
│   ├── webhook_log_views.xml
│   └── menu_views.xml
├── data/
│   ├── webhook_config_data.xml # Configuration par défaut
│   └── cron.xml                # Cron jobs
├── security/
│   └── ir.model.access.csv
└── README.md
```

## 🔒 Sécurité

- La clé API est stockée avec le type `password` (masquée dans l'interface)
- Seuls les administrateurs système peuvent modifier la configuration
- Les utilisateurs normaux ont accès en lecture seule

## 📈 Performance

- Traitement par lots (50 webhooks max par cycle)
- Commit après chaque envoi réussi
- Rollback en cas d'erreur pour éviter les blocages
- Délais exponentiels pour éviter de surcharger l'API

## 🔗 Liens utiles

- API The Residence : https://api.laresidence-abidjan.com
- Documentation webhook : Voir ODOO_WEBHOOK_SPECIFICATION.md

## 📝 Changelog

### Version 1.0.0 (2026-01-28)
- Première version
- Support des événements commandes, réservations, abonnements
- Queue avec retry automatique
- Logs détaillés
- Interface de monitoring

## 👥 Support

Pour toute question ou problème, contacter l'équipe développement The Residence.

## 📄 Licence

LGPL-3
