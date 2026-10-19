# 🚀 Guide d'installation rapide - The Residence Webhook Sender

## Étape 1: Installation du module

### 1.1 Prérequis
```bash
pip install requests
```

### 1.2 Copier le module
```bash
# Copier le dossier dans le répertoire addons d'Odoo
cp -r theresidence_webhook_sender /chemin/vers/odoo/addons/
```

### 1.3 Redémarrer Odoo
```bash
sudo systemctl restart odoo
# OU
sudo service odoo restart
```

### 1.4 Installer depuis l'interface
1. Aller dans **Apps**
2. Cliquer sur **Update Apps List**
3. Rechercher "The Residence - Webhook Sender"
4. Cliquer sur **Install**

✅ **Le module est maintenant installé !**

---

## Étape 2: Modifier votre module existant

### 2.1 Identifier les fichiers à modifier

Dans votre module **theresidence_integration** (ou nom équivalent) :
- `models/sale_order.py` - 9 modifications
- `models/pos_order.py` - 5 modifications

### 2.2 Remplacement automatique (RECOMMANDÉ)

```bash
cd /chemin/vers/odoo/addons/votre_module_theresidence/

# Remplacer automatiquement dans tous les fichiers .py
find . -name "*.py" -type f -exec sed -i "s/self\.env\['theresidence\.webhook'\]/self.env['theresidence.webhook.service']/g" {} \;

# Vérifier les modifications
grep -r "theresidence.webhook.service" .
```

### 2.3 Remplacement manuel (si préféré)

**Rechercher:**
```python
self.env['theresidence.webhook'].trigger_event(
```

**Remplacer par:**
```python
self.env['theresidence.webhook.service'].trigger_event(
```

### 2.4 Ajouter la dépendance

Dans le `__manifest__.py` de votre module existant :

```python
{
    'name': 'The Residence Integration',
    ...
    'depends': [
        'base',
        'sale',
        'point_of_sale',
        'theresidence_webhook_sender',  # <-- AJOUTER CETTE LIGNE
    ],
    ...
}
```

---

## Étape 3: Redémarrer et mettre à jour

### 3.1 Redémarrer Odoo
```bash
sudo systemctl restart odoo
```

### 3.2 Mettre à jour le module
1. Aller dans **Apps**
2. Rechercher votre module existant
3. Cliquer sur les trois points
4. Cliquer sur **Upgrade**

---

## Étape 4: Vérification

### 4.1 Vérifier la configuration
1. Aller dans le menu **Webhooks The Residence > Configuration**
2. Vérifier que la configuration existe avec :
   - URL: `https://api.laresidence-abidjan.com`
   - API Key: `EDjN4QtXERbgGOjiNil7b40iNTIiwG3q`
   - État: **Actif** (toggle vert)

### 4.2 Tester la connexion
1. Dans la configuration, cliquer sur **Tester la connexion**
2. Vous devriez voir : ✅ **"Connexion réussie"**

### 4.3 Test complet

**Option A: Créer une commande de test**
1. Créer une commande POS
2. La confirmer
3. Aller dans **Webhooks The Residence > Queue**
4. Vérifier qu'un webhook apparaît avec le statut **Envoyé**

**Option B: Créer une réservation de test**
1. Créer une réservation
2. L'approuver
3. Vérifier dans la **Queue** qu'un webhook a été envoyé

### 4.4 Vérifier les logs
1. Aller dans **Webhooks The Residence > Logs**
2. Vous devriez voir les tentatives d'envoi avec le statut **Succès**

---

## Étape 5: Configuration avancée (optionnel)

### 5.1 Modifier les paramètres
Dans **Configuration**, vous pouvez ajuster :
- **Timeout** : Temps d'attente max (défaut: 10s)
- **Tentatives maximum** : Nombre de retry (défaut: 5)
- **Délais entre tentatives** : Backoff exponentiel (défaut: 1,2,4,8,16)

### 5.2 Activer les logs de débogage
Cochez **Logs de débogage** pour voir les détails dans les logs Odoo.

### 5.3 Configurer les cron jobs
1. Aller dans **Paramètres > Technique > Automation > Actions planifiées**
2. Rechercher "webhook"
3. Vérifier que les crons sont actifs :
   - **Traiter la queue** : toutes les 5 minutes
   - **Nettoyer les webhooks** : quotidien
   - **Nettoyer les logs** : hebdomadaire

---

## ✅ Checklist finale

- [ ] Module installé
- [ ] Fichiers modifiés (theresidence.webhook → theresidence.webhook.service)
- [ ] Dépendance ajoutée dans __manifest__.py
- [ ] Odoo redémarré
- [ ] Module existant mis à jour
- [ ] Configuration vérifiée
- [ ] Test de connexion réussi
- [ ] Webhook de test envoyé avec succès
- [ ] Logs consultés

---

## 🐛 Problèmes courants

### Problème: "Module not found"
**Solution:** Vérifier que le module est bien dans le dossier addons et qu'Odoo a redémarré.

### Problème: "requests module not found"
**Solution:** 
```bash
pip install requests
# OU pour Odoo installé via système
sudo apt install python3-requests
```

### Problème: Les webhooks ne s'envoient pas
**Solution:**
1. Vérifier que la configuration est **Active**
2. Vérifier que le cron est actif
3. Cliquer sur **Traiter la queue maintenant**

### Problème: "API key invalid"
**Solution:** Vérifier la clé API dans la configuration.

---

## 📞 Support

Si vous rencontrez des problèmes :
1. Consulter le `README.md` complet
2. Vérifier les logs Odoo : `/var/log/odoo/odoo-server.log`
3. Contacter l'équipe développement

---

## 🎉 C'est terminé !

Votre système de webhooks est maintenant opérationnel. Les événements seront automatiquement envoyés vers l'API The Residence.

Pour monitorer l'activité, rendez-vous dans **Webhooks The Residence**.
