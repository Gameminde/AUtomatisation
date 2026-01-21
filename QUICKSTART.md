# ⚡ QUICKSTART - CONTENT FACTORY
## Démarrage Express (15 minutes)

---

## 🎯 OBJECTIF

Avoir un système fonctionnel qui collecte des news tech et génère du contenu viral en **moins de 15 minutes**.

---

## 📋 CHECKLIST PRÉ-REQUIS

Avant de commencer, vérifiez que vous avez :

- [x] ✅ **Python 3.11+** installé
  ```powershell
  python --version
  ```

- [x] ✅ **Node.js** installé (pour MCP Supabase)
  ```powershell
  node --version
  ```

- [x] ✅ **Cursor** ou **VSCode** ouvert dans le dossier projet

---

## 🚀 INSTALLATION EXPRESS

### 1️⃣ ENVIRONNEMENT PYTHON (2 min)

```powershell
# Créer environnement virtuel
python -m venv venv

# Activer
.\venv\Scripts\activate

# Installer dépendances
pip install -r requirements.txt
```

**✅ Résultat attendu** : `Successfully installed supabase-1.0.0 requests-2.31.0 ...`

---

### 2️⃣ CONFIGURATION SUPABASE (5 min)

#### A. Créer compte + projet
1. **Aller sur** : https://supabase.com
2. **S'inscrire** (GitHub recommandé)
3. **Créer projet** : `content-factory`
4. **Attendre 2-3 minutes** ☕

#### B. Copier les clés
1. **Settings** ⚙️ → **API**
2. **Copier** :
   - `Project URL`
   - `anon public` key

#### C. Créer `.env`
```powershell
copy env.example .env
notepad .env
```

**Remplacer** :
```env
SUPABASE_URL=https://votre-project-id.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### D. Créer les tables
1. **SQL Editor** 🗂️ dans Supabase
2. **Copier-coller** tout le contenu de `schema.sql`
3. **Run** (F5)

**✅ Vérifier** : Table Editor → 5 tables créées

---

### 3️⃣ CONFIGURATION GEMINI API (3 min)

1. **Aller sur** : https://ai.google.dev
2. **Cliquer** : "Get API Key"
3. **Créer projet** si nécessaire
4. **Copier la clé** API

**Ajouter dans `.env`** :
```env
GEMINI_API_KEY=votre-cle-gemini-ici
```

---

### 4️⃣ CONFIGURATION NEWSDATA.IO (2 min)

1. **Aller sur** : https://newsdata.io
2. **Sign up** (gratuit)
3. **Dashboard** → Copier API Key

**Ajouter dans `.env`** :
```env
NEWSDATA_API_KEY=votre-cle-newsdata-ici
```

---

### 5️⃣ TEST RAPIDE (3 min)

#### Test 1 : Connexion Supabase
```powershell
python -c "import config; config.get_supabase_client(); print('✅ OK')"
```

#### Test 2 : Scraper (collecter news)
```powershell
python main.py scrape
```

**✅ Résultat** : `Scraper saved 15 new articles`

#### Test 3 : Génération IA
```powershell
python main.py generate --limit 2
```

**✅ Résultat** : `Processed 2 articles`

#### Test 4 : Planning
```powershell
python main.py schedule
```

**✅ Résultat** : `Scheduled 56 posts`

---

## 🎉 FÉLICITATIONS !

Vous avez maintenant un système qui :

- ✅ Collecte automatiquement des actualités tech
- ✅ Génère du contenu viral avec IA
- ✅ Planifie des publications optimisées

---

## 🚀 PROCHAINES ÉTAPES

### 🔥 MAINTENANT (10 min)

**Configurer Facebook** pour publier :

1. **Aller sur** : https://developers.facebook.com
2. **Créer une app**
3. **Ajouter** : Facebook Login + Pages
4. **Graph API Explorer** → Générer token
5. **Ajouter dans `.env`** :
   ```env
   FACEBOOK_ACCESS_TOKEN=votre-token
   FACEBOOK_PAGE_ID=votre-page-id
   ```

6. **Tester publication** :
   ```powershell
   python main.py publish --limit 1
   ```

### 🟡 AUJOURD'HUI (30 min)

1. **Automatiser avec cron** :
   ```powershell
   python main.py run-all
   ```
   (Exécuter toutes les 3 heures)

2. **Vérifier analytics** :
   ```powershell
   python main.py analytics
   ```

### 🟢 CETTE SEMAINE

1. **Déployer sur Railway** (hébergement gratuit)
2. **Monitoring** : Dashboard Supabase
3. **Scale** : Augmenter fréquence posts

---

## 🆘 PROBLÈMES FRÉQUENTS

### ❌ "Missing required env var"
**Solution** : Vérifier que `.env` existe et contient toutes les clés

### ❌ "401 Unauthorized" (Supabase)
**Solution** : Revérifier la clé `anon public` dans Supabase Settings → API

### ❌ "Gemini request failed"
**Solution** : 
1. Vérifier quota gratuit (60 req/min)
2. Attendre 1 minute et réessayer

### ❌ "NewsData.io request failed"
**Solution** : Quota gratuit = 200 req/jour. Réessayer demain ou utiliser uniquement RSS.

---

## 📚 GUIDES DÉTAILLÉS

Pour plus d'informations :

- **Setup Supabase complet** : `SETUP_SUPABASE.md`
- **Configuration Facebook** : `SETUP_FACEBOOK.md` (à créer)
- **Déploiement Railway** : `DEPLOY_RAILWAY.md` (à créer)
- **README général** : `README.md`

---

## 💡 COMMANDES UTILES

```powershell
# Pipeline complet
python main.py run-all

# Scraper seulement
python main.py scrape

# Générer contenu (5 articles)
python main.py generate --limit 5

# Planifier posts
python main.py schedule

# Publier (3 posts)
python main.py publish --limit 3

# Sync analytics (10 posts récents)
python main.py analytics --limit 10
```

---

## 🎯 MÉTRIQUES DE SUCCÈS

Après 1 semaine d'utilisation :

- 📰 **100+ articles** collectés
- 🤖 **200+ posts** générés (text + reels)
- 📅 **50+ posts** planifiés
- ✅ **10+ posts** publiés sur Facebook
- 👍 **Premiers likes** et engagement

---

## 🚀 SUPPORT

- **GitHub Issues** : [Votre repo]
- **Documentation** : Voir dossier `/docs`
- **Supabase Docs** : https://supabase.com/docs

---

**🎊 Bon lancement !**

*Last updated: 2026-01-19*
