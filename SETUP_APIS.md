# 🔑 GUIDE - CONFIGURATION DES APIs
## Gemini API + NewsData.io + Facebook

---

## ✅ STATUT ACTUEL

- [x] ✅ **Supabase** : Configuré et fonctionnel
- [x] ✅ **Python Dependencies** : Installées
- [x] ✅ **Tables Database** : 5 tables créées
- [x] ✅ **Scraper** : 32 articles collectés (RSS feeds)
- [ ] ⏳ **Gemini API** : À configurer (PRIORITAIRE)
- [ ] ⏳ **NewsData.io** : À configurer (optionnel)
- [ ] ⏳ **Facebook** : À configurer (pour publication)

---

## 🔥 ÉTAPE 1 : GEMINI API (5 minutes) - GRATUIT

### Pourquoi c'est important ?
Gemini génère le contenu viral à partir des articles collectés. **Sans cette clé, vous ne pouvez pas générer de posts.**

### Comment obtenir la clé ?

1. **Aller sur** : https://ai.google.dev/

2. **Cliquer** : "Get API Key in Google AI Studio"

3. **Se connecter** avec votre compte Google

4. **Cliquer** : "Get API Key" (bouton bleu)

5. **Créer une clé** :
   - Si premier projet : "Create API key in new project"
   - Sinon : Sélectionner projet existant

6. **Copier la clé** (format : `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`)

### Ajouter dans .env

Ouvrir le fichier `.env` et ajouter :

```env
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### Limites gratuites
- ✅ **60 requêtes par minute**
- ✅ **1500 requêtes par jour**
- ✅ Largement suffisant pour démarrer !

### Tester l'API

```powershell
python -c "import config; print('Gemini API Key:', 'OK' if config.GEMINI_API_KEY else 'MANQUANTE')"
```

---

## 🟡 ÉTAPE 2 : NEWSDATA.IO (3 minutes) - OPTIONNEL

### Pourquoi c'est optionnel ?
Votre scraper fonctionne déjà avec RSS feeds gratuits (TechCrunch, The Verge, etc.). NewsData.io ajoute **87K+ sources supplémentaires** si vous voulez plus de contenu.

### Comment obtenir la clé ?

1. **Aller sur** : https://newsdata.io

2. **Cliquer** : "Get API Key Free"

3. **S'inscrire** :
   - Email
   - Mot de passe
   - Confirmer email

4. **Dashboard** : Copier votre API Key

### Ajouter dans .env

```env
NEWSDATA_API_KEY=pub_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### Limites gratuites
- ✅ **200 requêtes par jour**
- ✅ Filtres par catégorie, pays, langue
- ✅ Sources premium incluses

### Note
Si vous ne configurez pas NewsData.io, le scraper continuera de fonctionner avec les RSS feeds (comme actuellement).

---

## 📱 ÉTAPE 3 : FACEBOOK DEVELOPER (15 minutes)

### Pourquoi c'est important ?
Pour publier automatiquement sur votre page Facebook.

### Prérequis
- ✅ Avoir une **Page Facebook** (pas profil personnel)
- ✅ Être admin de cette page

### Comment configurer ?

#### A. Créer une Application Facebook

1. **Aller sur** : https://developers.facebook.com

2. **Cliquer** : "My Apps" → "Create App"

3. **Sélectionner** : "Business" → Next

4. **Remplir** :
   - **Display Name** : `Content Factory`
   - **App Contact Email** : Votre email
   - **Business Account** : (optionnel)

5. **Créer l'app**

#### B. Ajouter les produits

1. Dans votre app, **ajouter** :
   - **Facebook Login** (Add Product)
   - **Pages API** (Add Product)

2. **Settings → Basic** :
   - Remplir "Privacy Policy URL" (utiliser : https://www.privacypolicygenerator.info/)
   - Remplir "Terms of Service URL" (optionnel)

#### C. Générer un Access Token

1. **Aller sur** : https://developers.facebook.com/tools/explorer/

2. **Sélectionner** :
   - Votre app dans le dropdown
   - User Token → Get Token

3. **Permissions nécessaires** :
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `pages_manage_engagement`
   - `publish_video` (pour Reels)

4. **Cliquer** : "Generate Access Token"

5. **Copier le token** (commence par `EAAA...`)

#### D. Étendre le token à 60 jours

1. **Aller sur** : https://developers.facebook.com/tools/debug/accesstoken/

2. **Coller** votre token

3. **Cliquer** : "Extend Access Token"

4. **Copier** le nouveau token (60 jours)

#### E. Obtenir votre Page ID

1. **Aller sur votre Page Facebook**

2. **Settings** → **About**

3. **Copier** le Page ID (nombre comme `123456789012345`)

OU via Graph API Explorer :
```
GET /me/accounts
```

### Ajouter dans .env

```env
FACEBOOK_ACCESS_TOKEN=EAAXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
FACEBOOK_PAGE_ID=123456789012345
```

### Tester la configuration

```powershell
python -c "
import config
import requests
url = f'https://graph.facebook.com/v19.0/{config.FACEBOOK_PAGE_ID}?access_token={config.FACEBOOK_ACCESS_TOKEN}&fields=name'
resp = requests.get(url)
print('Facebook Page:', resp.json().get('name', 'ERREUR'))
"
```

---

## ⚡ VALIDATION COMPLÈTE

Une fois les 3 APIs configurées, tester :

### Test 1 : Variables d'environnement

```powershell
python -c "
import config
print('=== CONFIGURATION APIS ===')
print('Supabase:', 'OK' if config.SUPABASE_URL else 'MANQUANTE')
print('Gemini:', 'OK' if config.GEMINI_API_KEY else 'MANQUANTE')
print('NewsData:', 'OK' if config.NEWSDATA_API_KEY else 'OPTIONNEL')
print('Facebook Token:', 'OK' if config.FACEBOOK_ACCESS_TOKEN else 'MANQUANTE')
print('Facebook Page:', 'OK' if config.FACEBOOK_PAGE_ID else 'MANQUANTE')
"
```

### Test 2 : Pipeline complet

```powershell
# Collecter articles (vous avez déjà 32 articles)
python main.py scrape

# Générer contenu avec Gemini (NÉCESSITE GEMINI_API_KEY)
python main.py generate --limit 2

# Planifier publications
python main.py schedule

# Publier 1 post TEST (NÉCESSITE FACEBOOK)
python main.py publish --limit 1
```

---

## 🎯 RÉCAPITULATIF - CE QU'IL RESTE À FAIRE

| Tâche | Priorité | Temps | Statut |
|-------|----------|-------|--------|
| **Obtenir Gemini API Key** | 🔴 CRITIQUE | 5 min | ⏳ |
| **Configurer .env avec Gemini** | 🔴 CRITIQUE | 1 min | ⏳ |
| **Tester génération contenu** | 🔴 CRITIQUE | 2 min | ⏳ |
| Obtenir NewsData.io Key | 🟡 Optionnel | 3 min | ⏳ |
| Configurer Facebook App | 🟡 Important | 15 min | ⏳ |
| Tester publication Facebook | 🟡 Important | 2 min | ⏳ |

---

## 🚀 PROCHAINES ÉTAPES

### MAINTENANT (10 minutes)

1. ✅ **Obtenir Gemini API Key** → Suivre ÉTAPE 1
2. ✅ **Ajouter dans .env**
3. ✅ **Tester génération** :
   ```powershell
   python main.py generate --limit 2
   ```

### AUJOURD'HUI (30 minutes)

1. ✅ **Obtenir NewsData.io Key** (optionnel)
2. ✅ **Configurer Facebook Developer**
3. ✅ **Première publication test**

### CETTE SEMAINE

1. ✅ **Automatiser** avec cron/scheduler
2. ✅ **Déployer** sur Railway (hébergement gratuit)
3. ✅ **Monitorer** performances

---

## 🆘 PROBLÈMES FRÉQUENTS

### Gemini API : "API key not valid"
**Solution** : 
- Vérifier que la clé commence par `AIzaSy`
- Activer "Generative Language API" dans Google Cloud Console
- Attendre 5 minutes après création

### Facebook : "Invalid OAuth access token"
**Solution** :
- Générer un nouveau token avec Graph API Explorer
- Étendre à 60 jours avec Access Token Debugger
- Vérifier les permissions (pages_manage_posts)

### NewsData.io : "Rate limit exceeded"
**Solution** :
- Limite = 200 req/jour en gratuit
- Attendre 24h ou upgrader
- Le scraper fonctionne sans (RSS feeds)

---

## 📚 LIENS UTILES

- **Gemini API** : https://ai.google.dev/
- **NewsData.io** : https://newsdata.io
- **Facebook Developers** : https://developers.facebook.com
- **Graph API Explorer** : https://developers.facebook.com/tools/explorer/
- **Access Token Debugger** : https://developers.facebook.com/tools/debug/accesstoken/

---

*Last updated: 2026-01-19*
