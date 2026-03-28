# Operator Runbook

## 1. Required environment

Set these before starting production:

- `DB_MODE=supabase`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `APP_BASE_URL`
- `FERNET_KEY` preferred in production
- `SESSION_SECURE_COOKIES=1`
- `FB_APP_ID`
- `FB_APP_SECRET`
- `FB_REDIRECT_URI`

Optional:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BOT_USERNAME`
- `TRUST_PROXY_HEADERS=1` when running behind a reverse proxy that forwards the original host and scheme
- `ALLOW_ENV_AI_FALLBACK=1` plus the provider keys you want as server-side fallback
- `PEXELS_API_KEY`
- `PIXABAY_API_KEY`
- `NEWSDATA_API_KEY`

## 2. Database bootstrap and migration

Run these in Supabase SQL Editor, in order:

1. [`supabase_schema.sql`](C:/Users/youcefcheriet/fb/fbautomat/supabase_schema.sql)
2. [`migrations/001_saas_alignment.sql`](C:/Users/youcefcheriet/fb/fbautomat/migrations/001_saas_alignment.sql)

Verify `user_settings` includes:

- `ui_language`
- `ai_provider`
- `ai_model`
- `ai_api_key`
- `daily_summary_time`

## 3. Meta OAuth

Configure the Meta app with:

- App type that supports Facebook Login
- Redirect URI matching `FB_REDIRECT_URI`
- Permissions needed for page access and publishing

Then verify the full flow:

1. Login to Content Factory
2. Open `/oauth/facebook`
3. Complete Meta login
4. Choose the page in the page picker
5. Confirm the page appears in Channels and the dashboard destination cards

## 4. Web process

Local:

```bash
py dashboard_app.py
```

WSGI:

```bash
gunicorn --bind=0.0.0.0:5000 --reuse-port dashboard_app:app
```

Session/auth assumptions:

- The app uses Flask session cookies, not bearer tokens, for the authenticated web UI.
- Authenticated `POST` endpoints assume same-origin browser use behind HTTPS.
- The shipped web client sends `X-Requested-With: XMLHttpRequest` and `credentials: same-origin`; keep that behavior intact if you replace the frontend transport helper.
- Authenticated mutating API routes reject cross-origin `Origin` or `Referer` mismatches. If you place the app behind a proxy, preserve the original host/scheme headers.
- In production, terminate TLS before the app or at the proxy and keep `SESSION_SECURE_COOKIES=1`.
- Enable `TRUST_PROXY_HEADERS=1` only when the upstream proxy correctly forwards `X-Forwarded-Proto` and `X-Forwarded-Host`; otherwise leave it disabled.
- Do not expose the web app over plain HTTP on the public internet.

## 5. Background workers

Start these as separate long-running processes:

```bash
python -m tasks.runner
python -m tasks.telegram_bot
```

- `tasks.runner` handles scrape -> generate -> schedule -> publish -> analytics
- `tasks.telegram_bot` handles Telegram connection, summaries, and notifications

## 6. Post-deploy checks

Run these manually after deployment:

1. Register or log in with a real account
2. Save an AI provider key in Settings
3. Change navigation language and confirm the shell updates in place without a full reload
4. Connect a Facebook page through OAuth
5. Generate a Studio draft
6. Save and approve content
7. Verify Dashboard pending approvals and page status
8. Toggle Telegram daily summaries on and off

Recommended restart order after deploy:

1. Web app
2. `tasks.runner`
3. `tasks.telegram_bot`

## 7. Known V1 exclusions

These surfaces are intentionally disabled or hidden in the shipped SaaS V1:

- Advanced `/api/insights`
- Legacy template customization and template-library APIs
- A/B testing APIs
- Unified create-and-publish shortcut APIs
- ML virality scoring APIs
- Randomization tuning and legacy module-status APIs
- Agent control endpoints
- Runtime database/env mutation endpoints
- Global prompt mutation endpoints
- Raw log access endpoints

## 8. Rollback basics

If a deploy fails:

1. Revert the app release to the previous build
2. Keep the database if the migration only added nullable/defaulted columns
3. Re-run smoke tests for login, Settings, OAuth, and Studio

## 9. Security notes

- Production mode is Supabase-backed and tenant scoping depends on `user_id` on application queries.
- Prefer `FERNET_KEY` from the environment in production so encrypted tenant secrets do not depend on a repo-local key file.
- Disabled V1 routes should stay disabled; do not re-enable legacy runtime config, agent control, or raw log endpoints in production.
- If you run behind a reverse proxy, preserve the original scheme/host so Meta OAuth callbacks and session cookies stay correct.
