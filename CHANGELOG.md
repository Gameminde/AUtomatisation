# Changelog

## [v2.1.1] - 2026-01-27 (Thread Safety & Anti-Double Publish)

### 🐛 Correctifs Critiques (Blackbox)
*   **Anti-Double Publish** : Vérification `fb_post_id` avant appel API + `content_hash` unique.
*   **Thread Safety** : Module `process_lock.py` (File lock + DB flag `running`) empêche le lancement multiple.
*   **CAS Transitions** : Mise à jour atomique des statuts (`status='scheduled' -> 'publishing'`) pour éviter les race conditions.

### 🛡️ Robustesse
*   **Retry Clarity** : Ajout du champ `next_retry_at` pour un scheduling précis des retries.
*   **Rejected Status** : Nouveau statut `rejected` séparé de `failed` (exclu du calcul error_rate).
*   **Windows Compatibility** : Fallback automatique sur DB-lock si `fcntl` absent.

## [v2.1.0] - 2026-01-27 (Robustness Update)

### ✨ Nouveautés Majeures
*   **Approval Workflow** : Nouveau mode `APPROVAL_MODE=on` pour valider manuellement le contenu avant publication. Les posts passent par `waiting_approval` pour review.
*   **Smart Retry System** : Nouveau module `error_handler.py` avec classification automatique des erreurs :
    *   Rate Limit (#32, 429) → Cooldown 24h automatique
    *   Erreurs serveur (5xx) → Retry exponentiel (3 tentatives)
    *   Erreurs auth (401/403) → Alerte NEEDS_ACTION (pas de retry)
*   **Adaptive Scheduler** : Le scheduler ajuste automatiquement les intervalles si le taux d'erreur augmente (2-4h → 4-6h → 6-8h).
*   **Status Snapshot Dashboard** : Nouveau panel `/api/system/snapshot` pour diagnostiquer le système en 30 secondes.

### 🛡️ Robustesse
*   **Idempotence** : Hash unique du contenu (`content_hash`) empêche les doublons même après crash/restart.
*   **Cooldown Automatique** : Si Facebook rate-limit (#32), le système se met en pause 24h automatiquement.
*   **State Machine** : Statuts granulaires (`drafted`, `media_ready`, `waiting_approval`, `scheduled`, `publishing`, `published`, `failed`, `retry_scheduled`).

### 🔧 Améliorations Techniques
*   Nouveau endpoint `GET /api/content/pending` pour voir le contenu en attente d'approbation.
*   Nouveaux endpoints `POST /api/content/<id>/approve` et `/reject` pour workflow d'approbation.
*   Table `system_status` pour stocker l'état du système (cooldown, dernière erreur, etc.).

---

## [v2.0.0] - 2026-01-27 (Gumroad Launch Edition)

### ✨ Nouveautés Majeures
*   **Hybrid Database Core** : Introduction de `database.py` supportant à la fois SQLite (par défaut pour installation facile) et Supabase (pour le cloud).
*   **Human-Like Scheduler** : Algorithme de publication réécrit pour inclure du "jitter" (variation aléatoire) et des intervalles dynamiques afin d'éviter les bannissements Facebook.
*   **Dashboard Refresh** : Interface nettoyée pour la vente, affichant les statuts système en temps réel.
*   **Documentation Complète** : Ajout du "Guide Anti-Ban", du "Quickstart" et de la "Deep Wiki".

### 🔧 Améliorations Techniques
*   **Batch Processing** : Le module IA traite désormais les articles par lots de 5 pour économiser les appels API et accélérer la génération.
*   **Robust JSON Parsing** : Nouvelle fonction `parse_json_response` avec auto-réparation pour gérer les erreurs de syntaxe des LLM.
*   **Unified Logging** : Système de logs rotatifs centralisé dans `/logs/pipeline.log`.

### 🐛 Correctifs
*   Correction d'un bug où le token Facebook expirait silencieusement (ajout de logs d'erreur explicites).
*   Correction des imports circulaires dans `db_handler.py` (remplacé par `database.py`).

---

## [v1.0.0] - Alpha Privée
*   Version initiale utilisée en interne.
*   Support basique du scraping et posting.
*   Pas de dashboard, pas de sécurité anti-ban.
