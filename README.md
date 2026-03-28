# Content Factory

Content Factory is a Flask-based SaaS app for Facebook and Instagram page operators. Users activate an account, connect a Facebook page through OAuth, add their own AI provider key, generate content in Studio, approve or schedule drafts, publish supported formats, and monitor health from a dashboard.

## Shipped V1 scope

- Activation-code registration and session login
- Supabase-backed multi-tenant data model
- Facebook OAuth page connection
- Optional Instagram linkage through the connected Facebook page
- AI provider configuration for Gemini, Claude, OpenAI, and OpenRouter
- Studio generation for `post`, `carousel`, and `story_sequence`
- Draft save, regenerate, approve, reject, schedule, and publish flows
- Telegram connection plus daily summary toggle
- Dashboard and health views for setup, pending approvals, page status, and pipeline status

## Not part of V1

- Team or workspace collaboration
- Billing-provider integrations such as Gumroad, LemonSqueezy, or Paddle
- Reel Script creation in the active Studio flow
- Legacy template customization and template-library APIs
- Advanced `/api/insights` analytics
- A/B test APIs and unified create-and-publish shortcuts
- ML virality scoring and randomization tuning endpoints
- Legacy module-status, agent-control, and raw-log APIs
- Runtime config endpoints that mutate global `.env` or shared local files

## Architecture

- Web app: Flask + Jinja + `static/js/cf.js`
- Auth/session: Flask-Login with Supabase-backed `users`
- Database: Supabase / Postgres in production
- Workers:
  - `python -m tasks.runner`
  - `python -m tasks.telegram_bot`
- Core data tables:
  - `users`
  - `activation_codes`
  - `managed_pages`
  - `user_settings`
  - `raw_articles`
  - `processed_content`
  - `scheduled_posts`
  - `published_posts`
  - `telegram_connections`
  - `system_status`

## Developer utility

- `main.py` is retained as a manual local CLI for one-off pipeline runs.
- It is not used by the Flask web app, `python -m tasks.runner`, or `python -m tasks.telegram_bot`.
- Treat it as a developer convenience entrypoint, not part of the supported SaaS runtime surface.

## Local setup

1. Create a virtual environment and install dependencies.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Copy one of the example env files.

```bash
copy .env.example .env
```

3. Set `DB_MODE=supabase` and configure Supabase, Meta OAuth, and any optional workers/services you need.

4. In Supabase SQL Editor, run:
   - [`supabase_schema.sql`](C:/Users/youcefcheriet/fb/fbautomat/supabase_schema.sql)
   - [`migrations/001_saas_alignment.sql`](C:/Users/youcefcheriet/fb/fbautomat/migrations/001_saas_alignment.sql)

5. Start the web app.

```bash
py dashboard_app.py
```

6. Start the background workers in separate processes if you want automation and Telegram.

```bash
python -m tasks.runner
python -m tasks.telegram_bot
```

## Testing

```bash
py -m pytest -q
```

## Production notes

- Production mode expects Supabase. SQLite is only for limited local compatibility and is not the supported SaaS runtime.
- Prefer setting `FERNET_KEY` in production so encrypted per-user secrets do not depend on a local `.fernet_key` file. The file-based key remains a local-dev fallback only.
- The main AI path is bring-your-own-key per user. Environment AI keys are optional fallbacks only when explicitly enabled.
- Meta OAuth must be configured before Facebook connection can work.
- Telegram summaries require the Telegram worker process to be running.
- The authenticated web UI uses Flask session cookies. Deploy it behind HTTPS, keep authenticated POST/JSON traffic same-origin, and preserve the `X-Requested-With` header sent by `static/js/api.js`.
- Set `SESSION_SECURE_COOKIES=1` in production so Flask emits secure session and remember cookies and prefers `https` URL generation.
- Set `TRUST_PROXY_HEADERS=1` only when the app is behind a reverse proxy that correctly forwards `X-Forwarded-Proto` and `X-Forwarded-Host`.
- Authenticated mutating API routes reject cross-origin `Origin` or `Referer` mismatches for the shipped web flow.

See the operator runbook in [docs/operator_runbook.md](C:/Users/youcefcheriet/fb/fbautomat/docs/operator_runbook.md).
