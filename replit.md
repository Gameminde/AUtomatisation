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

## Key Files
- `dashboard_app.py` — Main Flask app with `create_app()` factory; all routes protected
- `wsgi.py` — Gunicorn entry point
- `models.py` — `User(UserMixin)` class for Flask-Login
- `app/auth/routes.py` — Auth blueprint: `/auth/login`, `/auth/register`, `/auth/logout`
- `config.py` — Centralized configuration and environment variable handling
- `database.py` — Database abstraction layer (SQLite/Supabase)
- `supabase_schema.sql` — Full schema including `users`, `activation_codes`, `user_id` FKs
- `templates/auth/` — Login and register pages
- `templates/layout_v3.html` — Sidebar layout with user email + sign out button
- `ai_generator.py` — AI content generation
- `scraper.py` — News/RSS scraping
- `publisher.py` — Facebook/Instagram Graph API publishing
- `scheduler.py` — Post scheduling

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

## SaaS Phases Roadmap
- **Phase 1 (DONE):** Foundation — user system, auth, activation codes, route protection
- **Phase 2 (DONE):** Instagram publishing support
- **Phase 3:** Per-user Facebook OAuth + Gemini key storage + onboarding wizard
- **Phase 4:** Engine multi-tenancy (UserConfig dataclass, per-user scheduling)
- **Phase 5:** Telegram Bot notifications
- **Phase 6:** RTL/Arabic design polish, Three.js landing
