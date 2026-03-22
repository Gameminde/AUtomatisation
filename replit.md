# Content Factory SaaS — Arabic Social Media Automation

## Overview
A multi-tenant SaaS web application for Arabic-speaking content creators. Automates Facebook (and Instagram) content creation and publishing. Sold via Gumroad with activation codes. Features AI-powered content generation, news scraping, image handling, and scheduling.

## Architecture
- **Framework:** Flask (Python 3.10) with `create_app()` factory pattern
- **Auth:** Flask-Login + bcrypt; custom `users` table in Supabase (not GoTrue)
- **Database:** SQLite (default, local) or Supabase (cloud, set `DB_MODE=supabase`)
- **Frontend:** Vanilla JS + custom CSS (RTL-ready, theme_v3)
- **AI:** Google Gemini (primary) or OpenRouter/Claude (fallback)
- **Entry Points:** `python dashboard_app.py` (dev) or `gunicorn wsgi:app` (prod)

## Application Structure (Phase 1)

```
dashboard_app.py          Thin entry point: load_dotenv + create_app() + app.run()
wsgi.py                   Gunicorn entry point
app/
  __init__.py             create_app() factory — registers all 6 blueprints
  utils.py                api_login_required decorator, env file helpers
  auth/routes.py          auth_bp: /auth/login, /auth/register, /auth/logout
                          (always uses Supabase directly — never SQLite)
  dashboard/routes.py     web_bp: 6 HTML pages + media serving + Facebook OAuth
  api/routes.py           api_bp: analytics, insights, status, health, agent,
                          facebook, instagram, AI, license, logs
  pages/routes.py         pages_bp: /api/pages/* CRUD (user_id scoped)
  studio/routes.py        studio_bp: /api/content/*, /api/actions/*,
                          /api/brand/*, /api/ab-tests/*, /api/virality/*
  settings/routes.py      settings_bp: /api/config/*, /api/settings/*,
                          /api/setup/*, /api/version, /api/providers
engine/__init__.py        engine package — lazy imports for pipeline modules
database/__init__.py      database package — re-exports from database.py via importlib
database.py               Database abstraction layer (SQLite/Supabase)
models.py                 User(UserMixin) for Flask-Login
config.py                 Centralized env var handling
supabase_schema.sql       Full schema: users, activation_codes, tenant tables,
                          RLS policies (USING/WITH CHECK auth.uid())
```

## Key Security Properties
- All web routes: `@login_required` (302 redirect on unauthenticated)
- All API routes: `@api_login_required` (401 JSON on unauthenticated)
- Public exceptions: `/media/public/<filename>`, `/api/license/activate`,
  `/auth/login`, `/auth/register`, `/auth/logout`
- All Supabase queries on tenant tables scoped to `current_user.id`

## Auth Flow
1. Unauthenticated users hitting any web route → redirect to `/auth/login`
2. Unauthenticated API calls → 401 JSON response
3. Registration requires a valid activation code (pre-seeded in Supabase `activation_codes`)
4. Passwords hashed with bcrypt, stored in `users` table
5. Flask-Login session manages login state

## Running the App
```
python dashboard_app.py   # dev (port 5000)
gunicorn wsgi:app         # production
```

## Environment Variables
- `GEMINI_API_KEY` — Google Gemini API key (recommended, free)
- `FACEBOOK_ACCESS_TOKEN` — Facebook Graph API token
- `FACEBOOK_PAGE_ID` — Facebook page to publish to
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` — if using Supabase (DB_MODE=supabase)
- `SECRET_KEY` — Flask session secret (set in production)
- `DB_MODE` — `sqlite` (default) or `supabase`

## Phase 3 — Engine Multi-tenancy (DONE)

Key additions:
- `engine/user_config.py`: `UserConfig` dataclass loaded from Supabase per tenant
  (gemini_api_key, fb_access_token, fb_page_id, instagram_account_id,
   newsdata_api_key, pexels_api_key, posts_per_day, posting_times,
   language_ratio, telegram_chat_id, niche_keywords)
- `engine/analytics_sync.py`: Syncs Facebook engagement metrics to published_posts
- `engine/scheduler.py`: `schedule_posts()` now accepts `posting_times_override`
  (honors per-user posting schedule from UserConfig)
- `engine/publisher.py`: `publish_text_post()` / `publish_photo_post()` accept
  optional `access_token` + `page_id` params for per-user credentials;
  `publish_due_posts()` loads per-user tokens via `load_tokens_for_user()`
- `tasks/runner.py` (NEW): APScheduler-based orchestrator — loads active tenants,
  acquires per-user distributed locks via `system_status`, runs 5-step pipeline
  (scrape → generate → schedule → publish → analytics sync) in ThreadPoolExecutor
- `dashboard_app.py` + `wsgi.py`: Call `tasks.runner.start_scheduler()` at boot
- `supabase_schema.sql`: Migrations for `last_error`, `retry_count`,
  `posts_per_day`, `posting_times`, `newsdata_api_key`, `language_ratio`

## SaaS Phases Roadmap
- **Phase 1 (DONE):** Foundation — user system, auth, activation codes, route protection
- **Phase 2 (DONE):** Onboarding wizard + per-user Gemini key + managed FB pages
- **Phase 3 (DONE):** Engine multi-tenancy (UserConfig, APScheduler runner, analytics sync)
- **Phase 4 (DONE):** Landing page — Three.js hero, Arabic RTL, FAQ, pricing
- **Phase 5 (PENDING):** Design, mobile & RTL polish
