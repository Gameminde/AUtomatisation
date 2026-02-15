# 📖 Content Factory - The Deep Dive Documentation (v2.0)

> **Documentation Technique & Opérationnelle Complète**
> Ce document est la "Bible" du projet. Il remplace toute documentation précédente.

---

## 📑 Table des Matières

1.  [Architecture Système](#1-architecture-système)
2.  [Configuration Bible (.env)](#2-configuration-bible-env)
3.  [Référence Base de Données](#3-référence-base-de-données)
4.  [Documentation des Modules (API Internals)](#4-documentation-des-modules-api-internals)
5.  [Flux Opérationnels (Workflows)](#5-flux-opérationnels-workflows)
6.  [Dépannage & FAQ](#6-dépannage--faq)

---

## 1. Architecture Système

Le projet est conçu comme un pipeline linéaire autonome. Il s'exécute séquentiellement pour garantir la qualité de chaque étape avant de passer à la suivante.

### Diagramme de Flux (Détaillé)

```mermaid
graph TD
    subgraph INPUT
    A[Cron Job / CLI] -->|Trigger| B(Main Orchestrator)
    end

    subgraph PHASE 1: ACQUISITION
    B -->|Calls| Scraper[scraper.py]
    Scraper -->|Fetch| RSS[RSS Feeds]
    Scraper -->|Fetch| NewsData[NewsData IO]
    Scraper -->|Fetch| HN[HackerNews]
    Scraper -->|Store| DB[(Database: raw_articles)]
    end

    subgraph PHASE 2: GÉNÉRATION (Unified Worker)
    DB -->|Read Pending| Creator[unified_content_creator.py]
    Creator -->|1. Pick Trending| TrendAlgo{Viral Score}
    Creator -->|2. Generate Text| AI[Gemini / OpenRouter]
    AI -->|JSON| ContentStruct
    Creator -->|3. Get Image| ImgPipe[image_pipeline.py]
    ImgPipe -->|Source| Pexels/Unsplash
    ImgPipe -->|Overlay| Canvas[Pillow Generator]
    ContentStruct -->|Combine| Processor
    Canvas -->|Combine| Processor
    Processor -->|Store| DB2[(Database: processed_content)]
    end

    subgraph PHASE 3: PLANIFICATION & PUBLICATION
    DB2 -->|Read Pool| Sched[scheduler.py]
    Sched -->|Human Logic| Slots[Time Slots Generator]
    Slots -->|Insert| DB3[(Database: scheduled_posts)]
    
    Clock -->|Check Due| Pub[publisher.py]
    DB3 -->|Read Due| Pub
    Pub -->|POST| FB[Facebook Graph API]
    Pub -->|Update Status| DB4[(Database: published_posts)]
    end
```

---

## 2. Configuration Bible (`.env`)

Toutes les variables d'environnement supportées par `config.py`.

| Variable | Requis | Valeur par défaut | Description |
| :--- | :---: | :--- | :--- |
| **DATABASE** |
| `DB_MODE` | Non | `sqlite` | `sqlite` (local) ou `supabase` (cloud). |
| `SUPABASE_URL` | Si cloud | - | URL du projet Supabase. |
| `SUPABASE_KEY` | Si cloud | - | Clé ANON (publique) Supabase. |
| **AI GENERATION** |
| `GEMINI_API_KEY` | **OUI** | - | Clé API Google Gemini (Primaire). |
| `OPENROUTER_API_KEY_1` | Non | - | Clé de secours pour OpenRouter. |
| `OPENROUTER_API_KEY_2` | Non | - | Clé de secours #2. |
| **SOCIAL MEDIA** |
| `FACEBOOK_ACCESS_TOKEN` | **OUI** | - | Token "Page Access Token" (Long-lived). |
| `FACEBOOK_PAGE_ID` | **OUI** | - | ID numérique de la page Facebook. |
| **IMAGES** |
| `PEXELS_API_KEY` | Non | - | Clé Pexels. Si vide, fallback sur Unsplash/LoremPicsum. |
| `PIXABAY_API_KEY` | Non | - | Clé Pixabay (Backup). |
| **SYSTEM** |
| `HTTP_TIMEOUT_SECONDS` | Non | `20` | Timeout pour les requêtes HTTP. |
| `REQUEST_SLEEP_SECONDS` | Non | `2` | Pause entre les requêtes (Rate Limit). |
| `DASHBOARD_API_KEY` | Non | - | Sécurisation de l'API Flask. |

---

## 3. Référence Base de Données

Le système supporte un schéma hybride. Voici la spécification exacte des tables critiques.

### `raw_articles`
Stocke les données brutes scrapées.
- `id` (UUID/TEXT): Clé primaire.
- `url` (TEXT UNIQUE): URL de l'article pour déduplication.
- `title` (TEXT): Titre original.
- `source_name` (TEXT): `techcrunch`, `verge`, etc.
- `status` (TEXT): `pending` (à traiter), `processed` (terminé), `rejected` (ignoré).
- `virality_score` (INT): Score calculé (0-10) basé sur la fraîcheur et la source.

### `processed_content`
Le contenu prêt à l'emploi.
- `post_type` (TEXT): `text` (v2.0) ou `reel` (legacy).
- `generated_text` (TEXT): Le corps du post Facebook.
- `hook` (TEXT): La première ligne ("accroche") du post.
- `hashtags` (JSON/TEXT): Tableau de tags.
- `image_path` (TEXT): Chemin local ou URL de l'image finale générée.
- `arabic_text` (TEXT): Le texte court incrusté sur l'image.

### `scheduled_posts`
La file d'attente de publication.
- `scheduled_time` (TIMESTAMP): Date/Heure exacte de publication (UTC).
- `status` (TEXT): `scheduled`, `published`, `failed`.
- `priority` (INT): 1-10.
- `timezone` (TEXT): Zone cible (ex: `America/New_York` pour calculer les heures de pointe).

---

## 4. Documentation des Modules (API Internals)

### 🧠 `ai_generator.py` (Le Cerveau)
Ce module gère toute la logique de génération de texte.
*   **`generate_batch(articles, client)`**:
    *   Prend une liste d'articles.
    *   Utilise `BATCH_PROMPT_TEMPLATE` pour demander à l'IA de traiter N articles en un seul appel (économie de tokens).
    *   Gère le parsing robuste du JSON de réponse avec `fix_json_string` (répare les erreurs courantes des LLM comme les virgules en trop).
*   **`parse_json_response(text)`**:
    *   Fonction critique qui nettoie la réponse de l'IA (supprime les blocs markdown ` ```json `).
    *   Tente plusieurs stratégies de récupération si le JSON est malformé.

### 🏭 `unified_content_creator.py` (L'Orchestrateur)
Coordonne le pipeline pour un contenu unique.
*   **`create_and_publish(...)`**:
    1.  Trouve un sujet tendance (`find_trending_topic`).
    2.  Vérifie les doublons avec `check_duplicate` (Logique floue de similarité de texte).
    3.  Appelle `generate_complete_content`.
    4.  Lance le pipeline image (`find_matching_image` -> `compose_canvas`).
    5.  Sauvegarde en DB.
    6.  Publie si le flag `publish=True`.

### 🗄️ `database.py` (L'Abstraction)
Ce fichier est une prouesse de compatibilité.
*   **`get_db()`**: Factory qui retourne soit `SQLiteDB` soit `SupabaseWrapper`.
*   **`SQLiteTable`**: Une classe qui implémente *exactement* la même interface que le client Python Supabase (`select`, `eq`, `insert`, `execute`).
    *   *Pourquoi ?* Cela permet de changer de backend DB en changeant une seule ligne dans `.env` sans toucher au reste du code.

### 📆 `scheduler.py` (Le Planificateur)
Logique humaine pour éviter les bans.
*   **`build_slots_for_day`**: Génère des créneaux basés sur `PEAK_HOURS`.
*   **`enforce_min_gap_random`**:
    *   Assure qu'il n'y a pas deux posts trop rapprochés.
    *   Utilise un intervalle aléatoire (ex: entre 2h et 4h) pour simuler un comportement humain naturel et non robotique.

---

## 5. Flux Opérationnels (Workflows)

### Workflow A: Ajout d'une nouvelle source de News
Pour ajouter un nouveau flux RSS :
1.  Ouvrir `scraper.py`.
2.  Localiser la liste `RSS_FEEDS`.
3.  Ajouter l'URL : `RSS_FEEDS.append("https://nouvelle-source.com/rss")`.
4.  Relancer `python main.py scrape`.

### Workflow B: Debugging d'une génération échouée
Si un post ne se génère pas :
1.  Vérifier `logs/pipeline.log`.
2.  Chercher "JSON parse error" ou "API key exhausted".
3.  Si JSON error : Vérifier le prompt dans `ai_generator.py` (peut-être trop complexe).
4.  Si API error : Vérifier le quota Gemini ou ajouter une clé OpenRouter.

### Workflow C: Reset complet de la base de données (Local)
En cas de corruption ou pour repartir à zéro :
1.  Arrêter le script.
2.  Supprimer le fichier `content_factory.db`.
3.  Relancer n'importe quel script (`main.py` ou autre).
4.  `database.py` recréera automatiquement toutes les tables vides au démarrage.

---

## 6. Dépannage & FAQ

**Q: Pourquoi les images sont-elles génériques ?**
R: Si Pexels/Pixabay échouent (ou pas de clé), le système utilise Unsplash (mot-clé) ou LoremPicsum comme fallback ultime. Ajoutez une clé `PEXELS_API_KEY` pour de meilleurs résultats.

**Q: Facebook bloque mes posts (Rate Limit).**
R: Le système a par défaut une pause de 2 secondes (`REQUEST_SLEEP_SECONDS`) et un "jitter" dans le scheduler. Si le blocage persiste, augmentez `REQUEST_SLEEP_SECONDS` à 10 ou 30 dans `.env`.

**Q: Comment voir les posts programmés ?**
R: Lancez le dashboard (`python dashboard_app.py`) et allez sur `localhost:5000`, ou inspectez la table `scheduled_posts` via un outil SQLite.

**Q: Puis-je utiliser MySQL ou PostgreSQL directement ?**
R: Le code est optimisé pour SQLite ou Supabase (Postgres HTTP API). Pour un Postgres local standard, il faudrait adapter `database.py` pour utiliser `psycopg2` ou `sqlalchemy`.

---
*Documentation générée automatiquement par Deep Dive Analyst - Content Factory Team*
