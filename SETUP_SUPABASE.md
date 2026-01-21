# 🚀 GUIDE COMPLET - CONFIGURATION SUPABASE
## Content Factory - Setup pas à pas

---

## ✅ ÉTAPE 1 : CRÉER COMPTE SUPABASE (5 min)

### 1.1 Inscription
1. **Aller sur** : https://supabase.com
2. **Cliquer** : "Start your project"
3. **S'inscrire avec** :
   - GitHub (recommandé)
   - OU Email + mot de passe
4. **Vérifier email** si inscription par email

### 1.2 Créer un nouveau projet
1. **Cliquer** : "New Project"
2. **Remplir** :
   - **Name** : `content-factory` (ou votre choix)
   - **Database Password** : Générer un mot de passe fort (SAUVEGARDER !)
   - **Region** : Choisir le plus proche de vous (ex: `West EU (Ireland)`)
   - **Pricing Plan** : Sélectionner **"Free"** (500 MB database)
3. **Cliquer** : "Create new project"
4. **Attendre 2-3 minutes** que le projet soit provisionné ☕

---

## ✅ ÉTAPE 2 : RÉCUPÉRER LES CLÉS API (2 min)

### 2.1 Accéder aux paramètres
1. Dans votre projet Supabase
2. **Cliquer** sur l'icône ⚙️ (Settings) en bas à gauche
3. **Cliquer** sur "API" dans le menu

### 2.2 Copier les informations
Vous verrez ces informations :

```
Project URL
https://xxxxxxxxxxx.supabase.co

Project API keys
┌─────────────────────────────────────────┐
│ anon public (client-side)               │
│ eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... │
└─────────────────────────────────────────┘
```

**À COPIER** :
- ✅ **Project URL** → `SUPABASE_URL`
- ✅ **anon public key** → `SUPABASE_KEY`

### 2.3 Créer votre fichier .env
1. **Copier le fichier template** :
   ```powershell
   copy env.example .env
   ```

2. **Ouvrir `.env`** dans Cursor

3. **Remplacer les valeurs** :
   ```env
   SUPABASE_URL=https://xxxxxxxxxxx.supabase.co
   SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...votre-clé-complète
   ```

---

## ✅ ÉTAPE 3 : CRÉER LES TABLES (5 min)

### 3.1 Accéder au SQL Editor
1. Dans votre projet Supabase
2. **Cliquer** sur 🗂️ **"SQL Editor"** dans le menu gauche
3. **Cliquer** sur **"New query"**

### 3.2 Exécuter le script SQL
1. **Ouvrir le fichier** `schema.sql` dans votre projet
2. **Copier TOUT le contenu** (Ctrl+A, Ctrl+C)
3. **Coller** dans le SQL Editor de Supabase
4. **Cliquer** : "Run" (ou F5)
5. **Vérifier** : Message de succès "Success. No rows returned"

### 3.3 Vérifier les tables créées
1. **Cliquer** sur 🗄️ **"Table Editor"** dans le menu gauche
2. **Vous devriez voir 5 tables** :
   - ✅ `raw_articles`
   - ✅ `processed_content`
   - ✅ `scheduled_posts`
   - ✅ `published_posts`
   - ✅ `performance_metrics`

### 3.4 Vérifier les vues (optionnel)
1. Dans le SQL Editor, exécuter :
   ```sql
   SELECT * FROM pipeline_status;
   ```
2. **Résultat attendu** :
   ```
   Articles Pending    | 0
   Content Generated   | 0
   Posts Scheduled     | 0
   Posts Published     | 0
   ```

---

## ✅ ÉTAPE 4 : TESTER LA CONNEXION PYTHON (2 min)

### 4.1 Activer l'environnement virtuel
```powershell
# Si pas encore créé
python -m venv venv

# Activer
.\venv\Scripts\activate

# Installer dépendances
pip install -r requirements.txt
```

### 4.2 Tester la connexion
```powershell
python -c "import config; client = config.get_supabase_client(); print('✅ Connexion Supabase réussie !')"
```

**Résultat attendu** :
```
✅ Connexion Supabase réussie !
```

**Si erreur** :
- ❌ `Missing required env var: SUPABASE_URL` → Vérifier `.env` existe et contient `SUPABASE_URL`
- ❌ `Missing required env var: SUPABASE_KEY` → Vérifier `.env` contient `SUPABASE_KEY`
- ❌ `401 Unauthorized` → Votre clé API est incorrecte, revérifier sur Supabase

---

## ✅ ÉTAPE 5 : CONFIGURER MCP SUPABASE (OPTIONNEL)

Le serveur MCP Supabase est déjà installé globalement (✅ fait automatiquement).

### 5.1 Obtenir un Personal Access Token (PAT)
1. **Aller sur** : https://supabase.com/dashboard/account/tokens
2. **Cliquer** : "Generate new token"
3. **Name** : `content-factory-mcp`
4. **Scopes** : Sélectionner `all` ou `read`/`write` selon besoin
5. **Copier le token** (vous ne le reverrez plus !)

### 5.2 Configurer MCP dans Cursor
1. **Ouvrir** : Settings (Ctrl+,)
2. **Chercher** : "MCP"
3. **Ajouter une configuration** :

```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": [
        "-y",
        "@supabase/mcp-server-supabase@latest",
        "--project-ref=VOTRE_PROJECT_REF"
      ],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "VOTRE_PAT_TOKEN"
      }
    }
  }
}
```

**Remplacer** :
- `VOTRE_PROJECT_REF` : C'est la partie avant `.supabase.co` dans votre URL
  - Exemple : Si URL = `https://abc123xyz.supabase.co`, alors `project-ref` = `abc123xyz`
- `VOTRE_PAT_TOKEN` : Le Personal Access Token généré à l'étape 5.1

### 5.3 Redémarrer Cursor
- Fermer et rouvrir Cursor
- Le serveur MCP Supabase sera disponible

---

## ✅ ÉTAPE 6 : INSÉRER DES DONNÉES DE TEST (2 min)

### 6.1 Via SQL Editor
1. Dans Supabase SQL Editor
2. Exécuter :

```sql
-- Insérer un article de test
INSERT INTO raw_articles (source_name, title, url, content, virality_score, status)
VALUES (
  'techcrunch',
  'Test Article: AI Revolutionizes Tech Industry',
  'https://example.com/test-article-' || gen_random_uuid(),
  'This is a test article about artificial intelligence and its impact on the tech industry. The latest breakthroughs in machine learning are transforming how we work and live.',
  8,
  'pending'
);

-- Vérifier insertion
SELECT id, title, status FROM raw_articles ORDER BY scraped_at DESC LIMIT 1;
```

### 6.2 Via Python (recommandé)
```powershell
python -c "
import config
client = config.get_supabase_client()
result = client.table('raw_articles').insert({
    'source_name': 'test',
    'title': 'Test Article from Python',
    'url': 'https://example.com/test-python',
    'content': 'This is a test article inserted via Python',
    'virality_score': 7,
    'status': 'pending'
}).execute()
print('✅ Article de test inséré:', result.data)
"
```

---

## ✅ ÉTAPE 7 : TESTER LE PIPELINE COMPLET (5 min)

### 7.1 Test Scraper (collecte news)
```powershell
python main.py scrape
```

**Résultat attendu** :
```
2026-01-19 15:30:45 INFO scraper: Scraper saved 15 new articles
```

**Vérifier dans Supabase** :
- Table Editor → `raw_articles`
- Vous devriez voir des articles avec `status = 'pending'`

### 7.2 Test AI Generator (génération contenu)
```powershell
python main.py generate --limit 2
```

**Résultat attendu** :
```
2026-01-19 15:32:10 INFO ai_generator: Processed 2 articles
```

**Vérifier dans Supabase** :
- Table `processed_content` → 4 nouvelles lignes (2 text + 2 reel)
- Table `raw_articles` → articles passés à `status = 'processed'`

### 7.3 Test Scheduler (planification)
```powershell
python main.py schedule
```

**Résultat attendu** :
```
2026-01-19 15:33:20 INFO scheduler: Scheduled 56 posts
```

**Vérifier dans Supabase** :
- Table `scheduled_posts` → Posts planifiés avec dates futures
- Regarder la colonne `scheduled_time` (en UTC)

### 7.4 Test Publisher (ATTENTION : publie vraiment !)
⚠️ **Ne faire QUE si Facebook est configuré** (voir ÉTAPE 8)

```powershell
# Publier 1 seul post pour tester
python main.py publish --limit 1
```

---

## ✅ ÉTAPE 8 : DASHBOARD SUPABASE (5 min)

### 8.1 Créer un tableau de bord SQL
1. SQL Editor → New query
2. Coller :

```sql
-- Dashboard Content Factory
SELECT 
  '📰 Articles Pending' AS metric,
  COUNT(*)::TEXT AS value
FROM raw_articles WHERE status = 'pending'

UNION ALL

SELECT 
  '🤖 Contenu Généré' AS metric,
  COUNT(*)::TEXT AS value
FROM processed_content

UNION ALL

SELECT 
  '📅 Posts Planifiés' AS metric,
  COUNT(*)::TEXT AS value
FROM scheduled_posts WHERE status = 'scheduled'

UNION ALL

SELECT 
  '✅ Posts Publiés' AS metric,
  COUNT(*)::TEXT AS value
FROM published_posts

UNION ALL

SELECT 
  '👍 Total Likes' AS metric,
  SUM(likes)::TEXT AS value
FROM published_posts

UNION ALL

SELECT 
  '💬 Total Comments' AS metric,
  SUM(comments)::TEXT AS value
FROM published_posts

UNION ALL

SELECT 
  '🔄 Total Shares' AS metric,
  SUM(shares)::TEXT AS value
FROM published_posts

UNION ALL

SELECT 
  '📊 Reach Total' AS metric,
  TO_CHAR(SUM(reach), '999,999,999') AS value
FROM published_posts;
```

3. **Sauvegarder** : "Save as" → `Dashboard Content Factory`
4. Vous pouvez exécuter cette requête n'importe quand pour voir vos stats !

### 8.2 Top Performing Posts
```sql
SELECT 
  published_at::DATE AS date,
  facebook_post_id,
  likes + shares + comments AS engagement,
  reach,
  ROUND((likes + shares + comments)::NUMERIC / NULLIF(reach, 0) * 100, 2) AS engagement_rate
FROM published_posts
ORDER BY engagement DESC
LIMIT 10;
```

---

## ✅ PROCHAINES ÉTAPES

### 🔥 CRITIQUE (À faire maintenant)
- [ ] ✅ Supabase configuré et testé
- [ ] Obtenir **Gemini API Key** (gratuit) → https://ai.google.dev
- [ ] Obtenir **NewsData API Key** (gratuit) → https://newsdata.io
- [ ] Configurer **Facebook Developer App** (voir guide séparé)

### 🟡 IMPORTANT (Cette semaine)
- [ ] Tester pipeline complet end-to-end
- [ ] Configurer cron job pour automation
- [ ] Déployer sur Railway (hébergement gratuit)

### 🟢 NICE TO HAVE (Plus tard)
- [ ] Dashboard HTML custom
- [ ] Intégration Pexels pour vidéos
- [ ] Tests unitaires
- [ ] Monitoring avancé

---

## 🆘 DÉPANNAGE

### Erreur: "Missing required env var: SUPABASE_URL"
**Solution** :
1. Vérifier que `.env` existe dans le dossier racine
2. Vérifier que `.env` contient `SUPABASE_URL=...`
3. Redémarrer le terminal (Ctrl+D puis rouvrir)
4. Re-activer venv : `.\venv\Scripts\activate`

### Erreur: "401 Invalid API key"
**Solution** :
1. Aller sur Supabase → Settings → API
2. Copier à nouveau la clé `anon public`
3. Remplacer dans `.env`
4. ⚠️ Ne PAS copier la clé `service_role` (risque sécurité)

### Tables pas créées
**Solution** :
1. Aller dans SQL Editor
2. Vérifier qu'il n'y a pas d'erreur SQL
3. Exécuter ligne par ligne si besoin
4. Vérifier que vous êtes sur le bon projet

### MCP Supabase ne fonctionne pas
**Solution** :
1. Vérifier que Node.js est installé : `node --version`
2. Réinstaller : `npm install -g @supabase/mcp-server-supabase`
3. Vérifier project-ref (sans https:// ni .supabase.co)
4. Redémarrer Cursor complètement

---

## 📚 RESSOURCES

- **Documentation Supabase** : https://supabase.com/docs
- **SQL Reference** : https://supabase.com/docs/guides/database
- **API Client Python** : https://supabase.com/docs/reference/python
- **Dashboard** : https://supabase.com/dashboard

---

## ✅ CHECKLIST FINALE

Avant de passer aux autres APIs :

- [ ] ✅ Compte Supabase créé
- [ ] ✅ Projet créé et provisionné
- [ ] ✅ Clés API copiées dans `.env`
- [ ] ✅ 5 tables créées (vérifier dans Table Editor)
- [ ] ✅ Vues et fonctions créées
- [ ] ✅ Connexion Python testée (pas d'erreur)
- [ ] ✅ Article de test inséré
- [ ] ✅ Scraper testé (articles collectés)
- [ ] ✅ Dashboard SQL créé et sauvegardé

**🎉 BRAVO ! Supabase est 100% configuré et opérationnel !**

---

## 🚀 PROCHAINE ÉTAPE

👉 **Configurer Gemini API** pour la génération de contenu IA  
👉 **Guide** : `SETUP_GEMINI.md` (à créer)

---

*Last updated: 2026-01-19*
