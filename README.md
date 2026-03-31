# Content Factory

Content Factory is a Flask-based SaaS application for Facebook and Instagram page operators. It gives a single user a private editorial workspace to connect a page, configure an AI provider, generate content in Studio, review or schedule drafts, publish supported formats, and monitor account health from a dashboard.

This repository contains the web app, the background automation runner, the Telegram bot worker, the Supabase schema bootstrap, and the supporting engine modules used to scrape, generate, schedule, publish, and track content.

## Who this repository is for

This repo serves three audiences at once:

- operators who need to deploy and run the SaaS safely
- developers who need to understand the web app, workers, and data model
- contributors who need to know which files are canonical and which ones are compatibility shims

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

### Surface overview

- Dashboard
  - setup progress
  - pending approvals
  - queue and publish health
  - destination readiness
- Studio
  - creator brief for generation and iteration inputs
  - single preview rail
  - live draft editing
  - template builder for reusable visual defaults
  - save / review / schedule / publish actions
- Channels
  - connected page list
  - active destination management
  - Facebook and Instagram connection state
  - Telegram connection and summary controls
- Settings
  - locale and profile preferences
  - AI provider settings
  - RSS/source configuration
  - presets and approval mode
- Diagnostics
  - health view for account, pipeline, cooldown, tokens, and recent failures
- Onboarding
  - initial profile setup
  - AI key test/store flow
  - preset seeding
  - post-onboarding immediate pipeline request

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

### Studio interaction contract

The current Studio implementation is intentionally split into three non-overlapping responsibilities:

- `Creator Brief`
  - prompt-only inputs for generation and iteration
  - format, route, tone, topic, angle, audience, proof, CTA, and iteration note
  - does not act as a second content editor
- `Live Editor`
  - the only editable source of final draft content
  - hook, body, caption, CTA, hashtags, image path, carousel slides, story frames, and reel points
  - the preview reads from the current draft state instead of synthesizing copy from the brief
- `Template Builder`
  - reusable design defaults only
  - brand markers, social strip, brand badge, framing, crop, scale, density, and media positioning
  - no duplicate template title/subtitle content layer

This separation is enforced in the React Studio route and in the Studio API so that generation, editing, and reusable design no longer compete as parallel sources of truth.

### Studio design intent

Studio should be treated as a dense desktop SaaS workspace, not as a marketing landing page.

The intended open-state composition is:

- compact top row with:
  - `Studio canvas` title block on the left
  - `Preview surface` controls in the center
  - `Library`, `New Draft`, and status pills on the right
- working row directly beneath it with:
  - `Creator Brief` on the left
  - sticky phone preview rail in the center
  - `Live Editor` on the right
- secondary row beneath the fold with:
  - `Template Builder` on the left
  - `Action Rail` on the right

The core UX priorities for the Studio page are:

- zero dead vertical space above the main working row
- full phone visible on first load on a normal laptop viewport
- one clear source of truth for content, one for design, one for generation
- consistent card rhythm, spacing, and visual hierarchy
- the phone preview feels central and stable during scroll

### Studio visual language

The Studio visual language is intentionally:

- warm beige canvas
- white operational cards
- deep black top bar and primary CTA accents
- large editorial display type for major headings
- compact utility typography for labels, pills, and field metadata

This is meant to feel like a premium creator dashboard with a slightly editorial or neo-brutalist edge, while still behaving like a professional operations tool.

In practical terms:

- the canvas should read as background, never as a broken white slab
- cards should read as cards, with one border/shadow/radius system
- the preview rail should feel like one unit, not scattered parts
- the user should always know which panel owns which decision

### Studio layout architecture

The current React Studio layout should be understood in four layers:

1. Page shell
   - handled by the authenticated React shell and top navigation
   - provides the fixed app chrome and route context
2. Studio dashboard grid
   - owned by `StudioPage.tsx` and `cf_react_studio.css`
   - defines the top row, left column, center rail, and right column
3. Preview rail
   - owned by `StudioPage.tsx` and `cf_react_preview.css`
   - defines the preview top controls, warnings, phone frame, and inner screen
4. Social/template rendering
   - handled inside the preview body and template canvas
   - turns the current draft content plus template design defaults into the final visual mockup

The grid is intentionally responsive in three modes:

- `1366px+`
  - unified 3-column desktop dashboard
  - centered preview rail
- `1280px–1365px`
  - preview-right desktop fallback
- `<1280px`
  - stacked/mobile-friendly composition

### Studio CSS ownership rules

When a designer or engineer changes the Studio page, file ownership matters.

- [`web/src/routes/StudioPage.tsx`](web/src/routes/StudioPage.tsx)
  - panel ordering
  - DOM structure
  - logical boundaries between brief, editor, template, preview, and action rail
- [`static/css/cf_react_studio.css`](static/css/cf_react_studio.css)
  - page-level layout
  - card spacing
  - desktop/mobile grid
  - stage/canvas/card surface hierarchy
- [`static/css/cf_react_preview.css`](static/css/cf_react_preview.css)
  - phone dimensions
  - preview chrome
  - template canvas internals
  - sticky preview behavior
- [`static/css/cf_react.css`](static/css/cf_react.css)
  - shared React primitives and shell utilities only
  - should not be used as the primary place for split-Studio layout work

Rule of thumb:

- if the change is about meaning, panel ownership, or content flow, start in `StudioPage.tsx`
- if the change is about spacing, grid, or cards, start in `cf_react_studio.css`
- if the change is about the phone, preview rail, or template media framing, start in `cf_react_preview.css`

### Design system constraints for Studio

Studio should stay within a small controlled measurement system:

- spacing ladder:
  - `8 / 12 / 16 / 24 / 32`
- radii:
  - major panels around `24px`
  - inset cards around `16px`
  - field and button controls around `14px–16px`
- minimum readable utility text:
  - labels, kickers, and pills should generally stay at or above `0.72rem`
- the phone preview should be constrained by viewport height first, not by arbitrary fixed width alone

Avoid reintroducing:

- duplicate title or subtitle systems inside the template
- duplicated device sizing math in multiple CSS files
- separate “almost white” surface bands that make the stage look broken
- new `display: contents` layout hacks to force desktop alignment

### How designers and engineers should collaborate on Studio

The fastest safe workflow is:

1. agree on which layer is being changed
   - content logic
   - page layout
   - preview/device rendering
2. define the acceptance state in screenshots
   - initial open state
   - above-the-fold desktop state
   - one scrolled state
   - RTL state if alignment is affected
3. make the DOM and CSS changes in the owning files only
4. validate at minimum on:
   - `1366x768`
   - `1440x900`
   - `1920x1080`
5. check that brief, editor, and template still obey their contract

Designers should think in terms of:

- what decision the user is making in each card
- whether that decision is generation, editing, or reusable design
- whether the preview is visually downstream of those decisions

Engineers should think in terms of:

- single source of truth
- layout ownership by file
- no duplicated CSS responsibility
- no hidden data sync between brief and final draft

### Studio regression checklist

Any Studio visual or logic refactor should be checked against these questions:

- Does the page open with the phone fully visible on a normal desktop viewport?
- Is there any empty top band above the working row?
- Does `Creator Brief` only shape generation and iteration, not final content editing?
- Does `Live Editor` fully own final visible copy?
- Does `Template Builder` only control reusable design defaults?
- Is the preview rail still visually central and sticky?
- Are left, center, and right columns aligned on the same top baseline?
- Are there any duplicate content layers inside the template canvas?
- Does the page still behave correctly in EN and AR/RTL?

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

- Backend framework: Flask
- Auth: Flask-Login
- Form CSRF: Flask-WTF protection for form posts
- Frontend: React + Vite + TypeScript served same-origin by Flask
- Legacy compatibility layer: Jinja templates plus the older modular browser runtime under `static/js/cf/`
- Main entrypoints:
  - local web server: `py dashboard_app.py`
  - React frontend dev server: `npm run dev`
  - production/static frontend build: `npm run build`
  - WSGI: `gunicorn wsgi:app`

The Flask app factory lives in [`app/__init__.py`](app/__init__.py). It registers the blueprints for:

- `auth`
- `dashboard`
- `api`
- `pages`
- `studio`
- `settings`
- `onboarding`

The authenticated shell is now served by Flask through [`templates/react_shell.html`](templates/react_shell.html) for migrated app routes. Flask injects session-backed boot metadata into the page:

- `csrf_token`
- `window.CF_I18N`
- current locale and direction
- current user email
- `window.__CF_WEB_BOOT__` with route and URL metadata

React then hydrates the app on the same origin and loads page startup data through `/api/bootstrap`.

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

The repository now contains two frontend layers.

### Primary frontend: React + Vite

The main authenticated app routes are now owned by the React app in [`web/`](web/).

Current React-driven routes:

- `/app/dashboard`
- `/studio`
- `/channels`
- `/settings`
- `/diagnostics`

Routes still intentionally server-rendered with Jinja:

- auth (`/auth/*`)
- onboarding (`/onboarding`)
- Meta OAuth start/callback/page selection

Key pieces:

- app shell and routing:
  - [`web/src/App.tsx`](web/src/App.tsx)
  - [`web/src/ui/AppShell.tsx`](web/src/ui/AppShell.tsx)
- route surfaces:
  - [`web/src/routes/DashboardPage.tsx`](web/src/routes/DashboardPage.tsx)
  - [`web/src/routes/StudioPage.tsx`](web/src/routes/StudioPage.tsx)
  - [`web/src/routes/ChannelsPage.tsx`](web/src/routes/ChannelsPage.tsx)
  - [`web/src/routes/SettingsPage.tsx`](web/src/routes/SettingsPage.tsx)
  - [`web/src/routes/DiagnosticsPage.tsx`](web/src/routes/DiagnosticsPage.tsx)
- frontend boot/auth/i18n/api helpers:
  - [`web/src/lib/boot.ts`](web/src/lib/boot.ts)
  - [`web/src/lib/api.ts`](web/src/lib/api.ts)
  - [`web/src/lib/auth.ts`](web/src/lib/auth.ts)
  - [`web/src/lib/i18n.ts`](web/src/lib/i18n.ts)
- React-specific style layer:
  - [`static/css/cf_react.css`](static/css/cf_react.css)
  - [`static/css/cf_react_studio.css`](static/css/cf_react_studio.css)
  - [`static/css/cf_react_preview.css`](static/css/cf_react_preview.css)

The root monorepo wrapper [`package.json`](package.json) exposes convenience scripts and delegates to [`web/package.json`](web/package.json).

### Studio design ownership

The Studio page now has explicit frontend ownership boundaries:

- [`web/src/routes/StudioPage.tsx`](web/src/routes/StudioPage.tsx)
  - Studio DOM structure, panel contracts, and page-level orchestration
- [`static/css/cf_react_studio.css`](static/css/cf_react_studio.css)
  - Studio grid, spacing, surfaces, panel layout, and desktop/mobile geometry
- [`static/css/cf_react_preview.css`](static/css/cf_react_preview.css)
  - phone frame, preview rail internals, and template-canvas rendering rules
- [`static/css/cf_react.css`](static/css/cf_react.css)
  - shared React primitives only; it should not be treated as the primary owner of split-Studio layout

If a Studio visual change is needed, start in `StudioPage.tsx`, `cf_react_studio.css`, or `cf_react_preview.css` before touching the broader shared stylesheet.

### Legacy compatibility frontend

The older Jinja + browser-runtime layer remains in the repo as a compatibility and fallback layer:

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

These files are still useful for fallback rendering and migration safety, but the main authenticated experience should now be considered React-owned.

### Internationalization

Internationalization still uses one shared source of truth:

- server-side templates use `t(...)`
- React and browser runtime use the server-injected `window.CF_I18N`
- the shared catalog lives in [`app/i18n.py`](app/i18n.py)

## Backend module layout

The backend is split into:

- `app/` for Flask routes, auth, CSRF, i18n, and web-facing helpers
- `engine/` for the canonical business/runtime modules
- `tasks/` for long-running worker processes
- `database/` for database adapters and helpers

There are also legacy root-level compatibility modules such as [`ai_generator.py`](ai_generator.py), [`publisher.py`](publisher.py), and [`scheduler.py`](scheduler.py). These exist as import shims pointing to the canonical `engine.*` modules. New code should prefer the `engine/` modules directly.

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
|- downloaded_images/       Runtime-downloaded media cache
|- engine/                  Publish, rate limiting, ban detection, config, etc.
|- generated_images/        Runtime-generated media cache
|- migrations/              SQL migrations
|- static/                  CSS and JS assets
|- tasks/                   Background workers
|- templates/               Jinja templates
|- tests/                   Test suite
|- web/                     React + Vite + TypeScript frontend
|- dashboard_app.py         Local web entrypoint
|- wsgi.py                  WSGI entrypoint
|- main.py                  Developer CLI utility only
|- package.json             Monorepo frontend helper scripts
|- requirements.txt
|- .env.example
`- supabase_schema.sql
```

Repo hygiene notes:

- `.env.example` is the canonical environment template
- `env.example` is not part of the supported layout
- `downloaded_images/` and `generated_images/` are runtime directories and should not contain committed sample files
- `attached_assets/`, local screenshots, and scratch reference documents are not part of the shipped product

## Local development setup

### Prerequisites

- Python 3.11+ recommended
- Node.js 20+ recommended
- npm
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
npm install
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

There are two supported local modes.

#### Mode A: simple local run using the built frontend

Use this when you want to run or smoke-test the app without React hot reload.

```powershell
npm run build
py dashboard_app.py
```

Open:

```text
http://127.0.0.1:5000/app/dashboard
```

In this mode, Flask serves the built frontend bundle from `static/web/`.

#### Mode B: frontend development with Vite hot reload

Use this when you are actively editing files under `web/src/`.

Terminal 1:

```powershell
$env:CF_WEB_DEV_SERVER="http://127.0.0.1:5173"
py dashboard_app.py
```

Terminal 2:

```powershell
npm run dev
```

Then open:

```text
http://127.0.0.1:5000/app/dashboard
```

Important:

- do not open `http://127.0.0.1:5173/static/web/`
- do not open `http://127.0.0.1:5000/static/web/`
- the correct app entry remains the Flask URL on port `5000`

The local server runs on `http://localhost:5000` unless you override the port.

Useful local helper routes:

- `/design-system` - local visual reference page
- `/media/public/<filename>` - public serving for generated/downloaded publish images

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
- a built frontend bundle already present under `static/web/`

Build the frontend before starting the production web process:

```bash
npm run build
```

### Web process

Example WSGI startup:

```bash
gunicorn --bind=0.0.0.0:5000 wsgi:app
```

Windows helper:

- [`deploy/setup_windows_task.bat`](deploy/setup_windows_task.bat) can be used as a starting point for scheduled-task style deployment on Windows hosts.

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

Frontend validation:

```bash
npm run typecheck
npm run test:web
npm run build
```

Legacy frontend module sanity checks during refactors:

```bash
node --check static/js/cf.js
node --check static/js/cf/studio/actions.js
node --check static/js/cf/studio/render.js
```

For release validation, also run the manual smoke checklist in [`SMOKE_TEST_CHECKLIST.md`](SMOKE_TEST_CHECKLIST.md).

## Troubleshooting

### React app loads blank in development

Check these in order:

1. Flask is running on `127.0.0.1:5000`
2. Vite is running on `127.0.0.1:5173`
3. Flask was started with:

```powershell
$env:CF_WEB_DEV_SERVER="http://127.0.0.1:5173"
```

4. You opened:

```text
http://127.0.0.1:5000/app/dashboard
```

and not a `/static/web/` URL directly.

If DevTools Network does not show `@vite/client` and `/src/main.tsx` with `200` responses, the React dev shell is not wired correctly.

### React app works in build mode but not in Vite dev mode

That usually means one of these:

- `CF_WEB_DEV_SERVER` was not set before starting Flask
- Flask was not restarted after setting `CF_WEB_DEV_SERVER`
- Vite is not running
- you opened the Vite/static asset URL instead of the Flask app URL

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

## What should stay out of GitHub

These should stay local and should not be committed back into the repo:

- `.env`, `.flask_secret`, `.fernet_key`
- downloaded/generated media outputs
- ad hoc screenshots, local design dumps, and pasted prompts
- private local tool folders such as `.claude/` or `.local/`

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
