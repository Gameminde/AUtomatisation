# 🚀 DEPLOYMENT CHECKLIST - Content Factory

## ✅ Pré-requis

### 1. Variables d'environnement (.env)
```bash
# Vérifier que ces variables sont configurées:
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGci...
OPENROUTER_API_KEY_1=sk-or-v1-xxxxx
OPENROUTER_API_KEY_2=sk-or-v1-xxxxx  # (backup)
OPENROUTER_API_KEY_3=sk-or-v1-xxxxx  # (backup)
FACEBOOK_ACCESS_TOKEN=EAAW...  # ⚠️ Expire après 60 jours!
FACEBOOK_PAGE_ID=1024612280726703
PEXELS_API_KEY=xxxxx
```

### 2. Dépendances Python
```bash
pip install -r requirements.txt
```

### 3. Base de données Supabase
Les tables suivantes doivent exister:
- ✅ `raw_articles` - Articles scrapés
- ✅ `processed_content` - Contenu généré (avec `image_path`, `arabic_text`)
- ✅ `scheduled_posts` - Posts programmés
- ✅ `published_posts` - Posts publiés
- ✅ `performance_metrics` - Métriques (optionnel)

---

## 🔄 Flux du Pipeline

```
[Scraper] → [AI Generator] → [Scheduler] → [Publisher] → [Analytics]
   ↓              ↓              ↓             ↓            ↓
 Articles    Contenu AR      Programme      Facebook    Métriques
             + Images        horaires       Publie      Sync
```

---

## 📅 Automatisation

### Option 1: Windows Task Scheduler
```batch
# Exécuter en admin:
deploy\setup_windows_task.bat
```

### Option 2: Cron (Linux)
```bash
# Toutes les 4 heures:
0 */4 * * * cd /path/to/project && python auto_runner.py >> logs/cron.log 2>&1
```

### Option 3: GitHub Actions (Cloud)
```yaml
# .github/workflows/content_factory.yml
name: Content Factory
on:
  schedule:
    - cron: '0 */4 * * *'  # Toutes les 4 heures
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python auto_runner.py
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          # ... autres secrets
```

---

## ⚠️ Points d'attention

### 1. Token Facebook (CRITIQUE)
- **Durée**: 60 jours max
- **Renouvellement**: 
  1. Aller sur https://developers.facebook.com/tools/explorer/
  2. Sélectionner votre app
  3. Permissions: `pages_manage_posts`, `pages_read_engagement`
  4. Générer un User Token
  5. Appeler `GET /me/accounts` pour obtenir le Page Token
  6. Mettre à jour `.env`

### 2. Limites API
- **OpenRouter**: ~100 requêtes/minute (avec rotation des clés)
- **Facebook**: ~200 posts/jour
- **Pexels**: 200 requêtes/heure

### 3. Contenu Arabe
- Le système génère maintenant du contenu **arabe** avec images
- Vérifier que les images s'affichent correctement

---

## 🧪 Tests avant déploiement

```bash
# 1. Vérifier les tests
pytest tests/ -v

# 2. Vérifier la qualité du code
flake8 . --max-line-length=120
black --check .

# 3. Test du pipeline complet
python auto_runner.py --limit 2 --publish-limit 1

# 4. Vérifier l'audit de la base
python db_audit.py
```

---

## 📊 Monitoring

### Dashboard
```bash
streamlit run dashboard.py
```

### Logs
- Les logs sont dans le dossier `logs/`
- Ou dans la sortie console

### Alertes
- Configurer `SMTP_*` dans `.env` pour les alertes email
- Les erreurs critiques déclenchent des alertes automatiques

---

## 🔧 Dépannage

| Problème | Solution |
|----------|----------|
| Token Facebook expiré | Renouveler sur Graph API Explorer |
| Posts non publiés | Vérifier `scheduled_posts` avec `status='scheduled'` |
| Images manquantes | Vérifier clé Pexels API |
| Contenu en anglais | Vérifier que `arabic_text` est généré |
| Rate limit OpenRouter | Ajouter plus de clés API |

---

## ✅ Checklist finale

- [ ] `.env` configuré avec toutes les clés
- [ ] Token Facebook valide et non expiré
- [ ] Tests passent (`pytest`)
- [ ] Pipeline test réussi (`auto_runner.py`)
- [ ] Task Scheduler / Cron configuré
- [ ] Monitoring en place (dashboard ou logs)
- [ ] Backup des clés API
