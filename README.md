# Content Factory

Content Factory is a Flask-based SaaS application for Facebook and Instagram page operators. It gives a single user a private editorial workspace to connect a page, configure an AI provider, generate content in Studio, review or schedule drafts, publish supported formats, and monitor account health from a dashboard.

This repository contains the web app, the background automation runner, the Telegram bot worker, the Supabase schema bootstrap, and the supporting engine modules used to scrape, generate, schedule, publish, and track content.

## What the product does

Content Factory is built around one core flow:

1. Register and sign in with an activation-code-gated account.
2. Complete onboarding or configure profile/settings directly.
3. Connect a Facebook page through Meta OAuth.
4. Add an AI provider key in Settings.
5. Open Studio and create a draft from a short creator brief.
6. Run an AI preview to inspect the final publish surface.
7. Save, review, schedule, or publish supported formats.
8. Monitor setup, queue health, approvals, and destination readiness from the dashboard.

## Current shipped scope

The current branch ships these user-facing surfaces:

- Dashboard
- Studio
- Channels
- Settings
- Diagnostics
- Onboarding
- Meta OAuth page selection
- Telegram connection and summary controls

### Content formats

Studio currently supports:

- `post`
- `carousel`
- `story_sequence`
- `reel_script`

V1 publishing behavior is intentionally split:

- Auto-publishable formats:
  - `post`
  - `carousel`
- Draft-only / export-first formats:
  - `story_sequence`
  - `reel_script`

That means story sequences and reel scripts can be created and stored in Studio, but they are not treated as normal auto-publish surfaces in the current V1 workflow.

## What is intentionally not in V1

These surfaces are intentionally disabled, hidden, or out of scope in the shipped SaaS V1:

- Team collaboration and multi-user workspaces
- Billing-provider integrations
- Advanced insights analytics APIs
- Legacy template customization APIs
- A/B testing APIs
- Unified create-and-publish shortcut APIs
- ML virality scoring APIs
- Randomization tuning endpoints
- Agent control endpoints
- Runtime database or `.env` mutation endpoints
- Raw log access endpoints

## Runtime architecture

Content Factory has three main runtime surfaces.

### 1. Web app

- Framework: Flask
- Auth: Flask-Login
- Form CSRF: Flask-WTF protection for form posts
- UI: Jinja templates plus a modular browser runtime under `static/js/cf/`
- Main entrypoints:
  - local/dev: `py dashboard_app.py`
  - WSGI: `gunicorn wsgi:app`

The Flask app factory lives in [`app/__init__.py`](app/__init__.py). It registers the blueprints for:

- `auth`
- `dashboard`
- `api`
- `pages`
- `studio`
- `settings`
- `onboarding`

### 2. Background automation runner

The automation worker lives in [`tasks/runner.py`](tasks/runner.py).

Responsibilities:

- load active tenants from Supabase
- acquire a per-user distributed lock in `system_status`
- run the pipeline per tenant
- schedule periodic runs with APScheduler
- handle immediate post-onboarding runs

Pipeline stages:

- scrape
- generate
- schedule
- publish
- analytics

Run it separately from the web app:

```bash
python -m tasks.runner
```

### 3. Telegram bot worker

The Telegram worker lives in [`tasks/telegram_bot.py`](tasks/telegram_bot.py).

Responsibilities:

- connect users by unique code
- send publish notifications
- support approval/reject flows
- schedule daily summaries
- support pause/resume automation commands
- warn about Facebook token expiry

Run it separately from the web app:

```bash
python -m tasks.telegram_bot
```

## Frontend structure

The authenticated UI uses [`templates/layout.html`](templates/layout.html) as the shell and the modular runtime in [`static/js/cf/`](static/js/cf/).

Key pieces:

- shell and shared runtime:
  - [`static/js/cf.js`](static/js/cf.js)
  - [`static/js/cf/shared.js`](static/js/cf/shared.js)
  - [`static/js/cf/shell.js`](static/js/cf/shell.js)
- page modules:
  - [`static/js/cf/pages/dashboard.js`](static/js/cf/pages/dashboard.js)
  - [`static/js/cf/pages/channels.js`](static/js/cf/pages/channels.js)
  - [`static/js/cf/pages/settings.js`](static/js/cf/pages/settings.js)
  - [`static/js/cf/pages/diagnostics.js`](static/js/cf/pages/diagnostics.js)
- Studio modules:
  - [`static/js/cf/studio/actions.js`](static/js/cf/studio/actions.js)
  - [`static/js/cf/studio/render.js`](static/js/cf/studio/render.js)
  - [`static/js/cf/studio/helpers.js`](static/js/cf/studio/helpers.js)
- global styles:
  - [`static/css/cf.css`](static/css/cf.css)

Internationalization uses one shared source of truth:

- server-side templates use `t(...)`
- browser runtime uses `window.CF_I18N` with `tr(...)` / `tt(...)`
- shared catalog lives in [`app/i18n.py`](app/i18n.py)

## Data model

Production mode is Supabase-backed and tenant isolation depends on `user_id` scoping across application queries.

Important tables:

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

The main bootstrap SQL lives in:

- [`supabase_schema.sql`](supabase_schema.sql)
- [`migrations/001_saas_alignment.sql`](migrations/001_saas_alignment.sql)

## Main user-facing routes

HTML routes:

- `/` - landing page
- `/app/dashboard` - dashboard
- `/studio` - Studio
- `/channels` - destination management
- `/templates` - legacy redirect to `/channels`
- `/settings` - profile, AI, feeds, presets
- `/diagnostics` - diagnostics surface
- `/health` - legacy redirect to `/diagnostics`
- `/onboarding` - onboarding entrypoint
- `/oauth/facebook` - start Meta OAuth
- `/oauth/facebook/select-page` - page picker after OAuth

API surfaces are split by concern:

- [`app/api/routes.py`](app/api/routes.py) - bootstrap, health, dashboard data, Telegram status, AI/provider utilities
- [`app/pages/routes.py`](app/pages/routes.py) - managed pages CRUD
- [`app/settings/routes.py`](app/settings/routes.py) - profile, AI, feeds, presets, setup status
- [`app/studio/routes.py`](app/studio/routes.py) - Studio endpoints, now delegated into focused modules under `app/studio/`

## Repository layout

```text
fbautomat/
|- app/                     Flask app package and blueprints
|  |- api/
|  |- auth/
|  |- dashboard/
|  |- onboarding/
|  |- pages/
|  |- settings/
|  |- studio/
|  |- csrf.py
|  |- i18n.py
|  |- utils.py
|  `- __init__.py
|- data/                    Static preset data and runtime JSON resources
|- database/                Database adapters and helpers
|- docs/                    Audit and operator runbook
|- engine/                  Publish, rate limiting, ban detection, config, etc.
|- migrations/              SQL migrations
|- static/                  CSS and JS assets
|- tasks/                   Background workers
|- templates/               Jinja templates
|- tests/                   Test suite
|- dashboard_app.py         Local web entrypoint
|- wsgi.py                  WSGI entrypoint
|- main.py                  Developer CLI utility only
|- requirements.txt
|- .env.example
`- supabase_schema.sql
```

## Local development setup

### Prerequisites

- Python 3.11+ recommended
- A Supabase project
- A Meta app with Facebook Login configured
- Optional: Telegram bot credentials
- Optional: AI provider fallback keys for server-side fallback

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Create your local environment file

```powershell
Copy-Item .env.example .env
```

### 3. Fill in the required environment variables

Required for normal SaaS operation:

| Variable | Required | Purpose |
| --- | --- | --- |
| `DB_MODE` | Yes | Use `supabase` for the supported SaaS runtime |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase service-role key used by the backend |
| `APP_BASE_URL` | Yes | Public base URL used by the app and callbacks |
| `FB_APP_ID` | Yes | Meta app ID |
| `FB_APP_SECRET` | Yes | Meta app secret |
| `FB_REDIRECT_URI` | Yes | OAuth callback URI, must match Meta config |

Recommended in production:

| Variable | Recommended | Purpose |
| --- | --- | --- |
| `FERNET_KEY` | Yes | Preferred encryption key source for tenant secrets |
| `SESSION_SECURE_COOKIES=1` | Yes | Marks session cookies as secure |
| `TRUST_PROXY_HEADERS=1` | Only behind a correct proxy | Trust `X-Forwarded-Proto` and `X-Forwarded-Host` |

Optional runtime features:

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Enables Telegram bot polling, summaries, and notifications |
| `TELEGRAM_BOT_USERNAME` | Telegram bot username used for connection flow |
| `ALLOW_ENV_AI_FALLBACK=1` | Allow server-side AI fallback when a user has not stored their own AI key |
| `GEMINI_API_KEY` | Optional fallback AI key |
| `ANTHROPIC_API_KEY` | Optional fallback AI key |
| `OPENAI_API_KEY` | Optional fallback AI key |
| `OPENROUTER_API_KEY` | Optional fallback AI key |
| `PEXELS_API_KEY` | Optional image source |
| `PIXABAY_API_KEY` | Optional image source |
| `NEWSDATA_API_KEY` | Optional news source |

### 4. Bootstrap the database

Run these SQL files in Supabase SQL Editor, in order:

1. [`supabase_schema.sql`](supabase_schema.sql)
2. [`migrations/001_saas_alignment.sql`](migrations/001_saas_alignment.sql)

Important:

- the web app expects the Supabase schema to exist before first sign-in
- auth and activation-code registration are Supabase-backed
- SQLite is only a local compatibility mode and is not the supported SaaS production runtime

### 5. Start the web app

```powershell
py dashboard_app.py
```

The local server runs on `http://localhost:5000` unless you override the port.

### 6. Start background workers

Open separate terminals for:

```powershell
python -m tasks.runner
python -m tasks.telegram_bot
```

You can run the web app without the workers, but:

- scheduled automation will not run without `tasks.runner`
- Telegram connection, approvals, summaries, and notifications will not run without `tasks.telegram_bot`

## Production deployment notes

### Supported runtime model

Production deployment assumes:

- `DB_MODE=supabase`
- Flask session-cookie auth
- same-origin authenticated web traffic
- HTTPS in front of the app
- separate long-running worker processes

### Web process

Example WSGI startup:

```bash
gunicorn --bind=0.0.0.0:5000 wsgi:app
```

### Restart order

Recommended restart order after deploy:

1. web app
2. `tasks.runner`
3. `tasks.telegram_bot`

### Cookie and proxy notes

- Keep `SESSION_SECURE_COOKIES=1` in production.
- Enable `TRUST_PROXY_HEADERS=1` only if your proxy correctly forwards original host and scheme.
- Do not expose the authenticated web app over public plain HTTP.
- Keep authenticated browser requests same-origin.

## Meta OAuth setup

To connect Facebook pages successfully:

1. create a Meta app that supports Facebook Login
2. configure the redirect URI to exactly match `FB_REDIRECT_URI`
3. grant the page access/publishing permissions needed by your workflow
4. log into Content Factory
5. open `/oauth/facebook`
6. complete Meta login
7. choose the page in the page picker
8. confirm the page appears in Channels

Channels is the canonical destination-management screen. The legacy `/templates` route redirects there.

## Settings and AI model behavior

Each user can store their own AI provider settings in Settings.

Supported providers in the current branch:

- Gemini
- Claude / Anthropic
- OpenAI
- OpenRouter

Important behavior:

- the main app model is bring-your-own-key per user
- optional environment fallback is only used when explicitly enabled
- per-user secrets are encrypted before being stored

## Security notes

- Production mode is multi-tenant and tenant isolation depends on `user_id`-scoped queries.
- Managed page tokens and user AI keys are stored encrypted at rest.
- Prefer `FERNET_KEY` from the environment in production.
- The repo-local `.fernet_key` is a local development fallback only.
- Disabled V1 routes should remain disabled.
- JSON/API surfaces assume same-origin authenticated browser traffic.
- Logout uses a POST-backed flow in the shipped UI.

## Testing

Run the full Python suite:

```bash
py -m pytest -q
```

For frontend module sanity checks during refactors:

```bash
node --check static/js/cf.js
node --check static/js/cf/studio/actions.js
node --check static/js/cf/studio/render.js
```

For release validation, also run the manual smoke checklist in [`SMOKE_TEST_CHECKLIST.md`](SMOKE_TEST_CHECKLIST.md).

## Troubleshooting

### Dashboard bootstrap fails on missing Supabase columns

If you see errors such as missing columns in `managed_pages` or related tables:

- verify you ran both SQL files
- verify the deployed Supabase schema matches the current branch
- rerun the SaaS alignment migration if the environment was created from an older schema

### Login or registration fails in local mode

If `DB_MODE=sqlite`, auth will not behave like the supported SaaS runtime. Use:

```env
DB_MODE=supabase
SUPABASE_URL=...
SUPABASE_KEY=...
```

### Facebook page connect succeeds but Studio cannot publish

Check these in order:

1. the page is visible in Channels
2. one destination is active
3. the user has a stored AI key or allowed env fallback
4. the selected format is publishable in V1
5. for Instagram previews, required media is present

### Telegram controls do nothing

Make sure:

- `TELEGRAM_BOT_TOKEN` is configured
- `tasks.telegram_bot` is running
- the user completed the Telegram connection flow

## Developer utility

[`main.py`](main.py) is retained as a manual local CLI for one-off developer runs.

It is not part of the supported web runtime and it is not the worker entrypoint used by production.

Example:

```bash
python main.py run-all --limit 10
```

## Additional project docs

- Operator runbook: [`docs/operator_runbook.md`](docs/operator_runbook.md)
- Smoke checklist: [`SMOKE_TEST_CHECKLIST.md`](SMOKE_TEST_CHECKLIST.md)
- Release checklist: [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)
- Rollback plan: [`ROLLBACK_PLAN.md`](ROLLBACK_PLAN.md)
- Full project audit: [`docs/full_project_audit_2026-03-25.md`](docs/full_project_audit_2026-03-25.md)

## Recommended first-run validation

After local setup or deployment, validate this exact flow:

1. register or log in
2. save an AI provider key in Settings
3. change UI language and confirm the shell updates correctly
4. connect a Facebook page through OAuth
5. verify the page appears in Channels
6. generate a Studio draft
7. save or review the draft
8. confirm Dashboard and Diagnostics reflect the new state
9. connect Telegram and toggle daily summaries if that feature is enabled

If that flow works, the core SaaS surface is operating as intended.
