# Full Project Audit

Date: 2026-03-25
Repository: `C:\Users\youcefcheriet\fb\fbautomat`
Branch: `main`
Audit basis: current working tree, not a clean release snapshot

## Executive Summary

Content Factory is a Flask-based SaaS application for Facebook and Instagram page operators. The current codebase has a credible multi-tenant backend foundation:

- Flask application factory with blueprint separation
- Supabase-backed custom auth and tenant data model
- Per-user encrypted AI keys and Facebook page tokens
- Background workers for the main content pipeline and Telegram automation
- Broad test coverage on core backend behavior

The main risk is not backend shape. The main risk is branch state and migration completeness.

This checkout is in the middle of a large UI and cleanup transition. The backend has advanced further than the frontend integration. The most important confirmed problems in the current working tree are:

1. The active UI shell references a missing `static/js/cf.js` asset while the new page templates rely on client-side hydration.
2. Publish safety gates for rate limiting and ban detection are still effectively global, not tenant-scoped.
3. The Fernet key used to protect stored secrets is auto-generated locally but not ignored by Git.
4. Two cleanup tests fail because the current route behavior has drifted from the expected V1 cleanup contract.

If those issues are fixed, the project becomes materially closer to a deployable V1 backend with a coherent tenant model.

## Scope and Method

This audit combined:

- `npx gitnexus analyze`
- manual code reading of entrypoints, routes, engine modules, workers, templates, config, migrations, and tests
- repository shape and worktree inspection
- full backend test run with `py -m pytest -q`

GitNexus output:

- 1,700 nodes
- 4,782 edges
- 135 clusters
- 141 flows

Repo metrics observed during audit:

- 173 tracked/untracked project files in the current tree scan
- 104 Python files
- 15 HTML templates
- 3 currently present JS files in `static/js`
- 2 CSS files
- 24 test files

## Current Repository State

This is not a clean baseline.

- `git status` shows 106 local changes
- `git diff --stat` shows a major migration with 72 files changed
- older `*_v3.html` and `*_v3.js` assets were deleted
- new shell templates and CSS were added as untracked files
- `.fernet_key` is currently untracked in the repo root

Latest commit seen:

- `150b8ea51351e8c991c50bf74cb7650dce32e423`
- `2026-03-22 10:41:33 +0000`
- `Phase 4 (Telegram Bot) - decouple background jobs from bot-token dependency`

Conclusion: any audit of behavior must distinguish between intended architecture and the current migration state of this branch.

## Product Intent

The README describes a SaaS V1 focused on:

- activation-code registration and session login
- Facebook page connection through OAuth
- optional Instagram linkage
- per-user AI provider configuration
- studio generation for `post`, `carousel`, and `story_sequence`
- draft, approval, schedule, publish, and dashboard flows
- Telegram connection and daily summaries

The README also explicitly excludes several legacy or advanced surfaces from V1, including:

- advanced insights
- A/B testing APIs
- unified create-and-publish shortcuts
- randomization tuning
- agent control
- raw log access
- runtime env mutation APIs

That V1 boundary is mostly respected in the current backend.

## Architecture Overview

### Application Layer

Primary web entrypoint:

- `dashboard_app.py`

WSGI compatibility:

- `wsgi.py`

Application factory:

- `app/__init__.py`

Blueprints:

- `app/auth/routes.py`
- `app/dashboard/routes.py`
- `app/api/routes.py`
- `app/pages/routes.py`
- `app/studio/routes.py`
- `app/settings/routes.py`
- `app/onboarding/routes.py`

### Data Layer

Canonical DB adapter:

- `database/database.py`

Modes:

- Supabase for SaaS runtime
- SQLite for limited local compatibility

Important note:

- Auth is Supabase-only.
- SQLite mode is explicitly treated as local/single-user compatibility, not real SaaS mode.

### Worker Layer

Main pipeline worker:

- `tasks/runner.py`

Telegram worker:

- `tasks/telegram_bot.py`

Core pipeline stages:

- scrape: `engine/scraper.py`
- generate: `engine/ai_generator.py`
- schedule: `engine/scheduler.py`
- publish: `engine/publisher.py`
- analytics sync: `engine/analytics_sync.py`

### Runtime Configuration

Global config and presets:

- `config.py`

Per-user runtime profile:

- `engine/user_config.py`

Shared tenant helpers and secret handling:

- `app/utils.py`

## Data Model and Tenancy

Primary tables used by the runtime:

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

Multi-tenant design is based on `user_id` application scoping. The code uses the Supabase service key, so the application layer is the real security boundary. That makes query discipline critical.

Positive observations:

- most route handlers explicitly scope queries with `user_id`
- Facebook page tokens are saved per user in `managed_pages`
- AI keys are saved per user in `user_settings`
- migrations align old schemas toward tenant-aware fields and indexes
- the runner uses per-user distributed locks in `system_status`

Important constraint:

- because service-role access bypasses RLS, any missing `user_id` filter is a real cross-tenant bug, not a theoretical one

## Runtime Flow Map

### 1. Auth and Session Flow

- User registration and login live in `app/auth/routes.py`
- Auth reads and writes `users` and `activation_codes` directly via Supabase
- Passwords use `bcrypt`
- Flask-Login sessions are used for authenticated web UI access
- `load_user()` in `app/__init__.py` reloads users from Supabase by ID

Assessment:

- Reasonable for a custom-auth Flask SaaS
- Clear separation between auth and local SQLite fallback

### 2. Facebook OAuth Flow

- OAuth route starts in `app/dashboard/routes.py`
- low-level Meta integration lives in `engine/facebook_oauth.py`
- page selection happens in `templates/page_select.html`
- final page token is encrypted and stored through `app.utils.save_fb_page_for_user()`

Assessment:

- The high-level flow is coherent
- Token persistence is tenant-aware
- The branch currently has navigation-state drift around this flow, but the storage logic itself is sound

### 3. Content Generation Flow

- Studio endpoints live in `app/studio/routes.py`
- Provider selection and fallback logic live in `engine/ai_provider.py`
- Prompt building and payload normalization live in `engine/ai_generator.py`
- per-user provider/model/key resolution lives in `engine/user_config.py` and `app/utils.py`

Assessment:

- Good abstraction boundary between route layer and generation layer
- Provider catalog is broader than V1 strictly needs, but manageable
- Normalization logic for structured content formats is one of the stronger parts of the codebase

### 4. Scheduling and Publishing Flow

- scheduling logic is in `engine/scheduler.py`
- publish execution is in `engine/publisher.py`
- publication tracking and duplicate prevention are in `publication_tracker.py`
- content state transitions include draft, scheduled, pending approval, publishing, published, failed, and retry states

Assessment:

- This is the most operationally important subsystem
- CAS-style content status transitions are a positive sign
- the global rate-limit/ban checks are currently the main architecture flaw in this path

### 5. Telegram Integration

- connection records live in `telegram_connections`
- approval and notification logic live in `tasks/telegram_bot.py`
- onboarding and deep-link support are implemented
- daily summaries and token-expiry notifications are present

Assessment:

- The Telegram subsystem is substantial and not just placeholder code
- good separation from the web layer
- worker dependency is explicit in docs and README

## Strengths

### Strong Backend Separation

The codebase is much more modular than a typical early Flask app. Route, engine, worker, config, and database responsibilities are separated clearly enough to reason about.

### Good Tenant-Aware Intent

The current architecture clearly aims for tenant-safe behavior:

- per-user settings
- per-user page credentials
- per-user content and scheduling
- per-user worker locking

That intent appears consistently in most of the code.

### Broad Automated Test Coverage

Observed test result:

- 271 tests collected
- 269 passed
- 2 failed

Coverage appears especially strong around:

- AI provider logic
- scheduler
- scraper
- publisher
- settings and studio routes
- health and security route behavior

That is a strong signal that backend work has been validated incrementally.

### Explicit Operational Documentation

Useful operator-facing docs exist:

- `README.md`
- `docs/operator_runbook.md`
- `RELEASE_CHECKLIST.md`
- `ROLLBACK_PLAN.md`
- `SMOKE_TEST_CHECKLIST.md`

This is above average for a codebase of this size.

### Safer Legacy Surface Handling

Several risky or out-of-scope APIs are explicitly disabled with `410` style responses in V1 rather than silently left half-supported. That is a good product-hardening decision.

## Weaknesses and Risks

### 1. Incomplete Frontend Migration

Severity: High

The active layout loads:

- `static/js/api.js`
- `static/js/cf.js`

But `static/js/cf.js` does not exist in the current working tree.

At the same time, the new templates are mostly shell markup with empty containers such as:

- dashboard slots
- studio library/editor placeholders
- settings provider/profile containers
- channels destination containers

This strongly suggests that the new UI expects a missing client-side controller.

Impact:

- pages can render without their intended behavior
- the app can look structurally complete while being functionally incomplete
- backend tests will not catch this because they do not validate browser behavior

Root cause:

- the branch appears to have deleted older `*_v3.js` assets before the replacement shell JS was added or committed

### 2. Rate Limit and Ban Detection Are Not Tenant-Scoped

Severity: High

`engine/publisher.py` calls:

- `should_pause_automation()`
- `can_post_now()`

without a tenant/page identifier.

But both safety systems query `published_posts` globally and cache a single global instance:

- `engine/rate_limiter.py`
- `engine/ban_detector.py`

Impact:

- one tenant's publication history can affect another tenant's posting eligibility
- a low-engagement tenant can pause others
- a mature page can distort a new page's rate limits
- this is especially dangerous because the rest of the publish path is tenant-aware, creating a false sense of safety

This is the most important backend correctness issue found in the audit.

### 3. Secret-Key Hygiene Gap Around `.fernet_key`

Severity: Medium

`app/utils.py` auto-generates `.fernet_key` when `FERNET_KEY` is not set.

That file protects decryption of:

- per-user AI API keys
- encrypted Facebook page access tokens

But `.gitignore` does not ignore `.fernet_key`, and the current tree already shows it as untracked.

Impact:

- accidental commit would expose the key needed to decrypt stored tenant secrets
- this is a workflow and hygiene risk rather than an immediate remote exploit

### 4. Route Cleanup Drift

Severity: Low

The route layer and tests disagree on expected behavior:

- `/templates` now redirects to `/channels`
- OAuth page selection marks `active_page="channels"`

But the cleanup tests still expect:

- a dedicated templates view with `active_page="templates"`
- the page picker to be under settings context

Impact:

- only 2 tests fail, so this is not a broad regression
- however it shows product/navigation intent is not fully aligned during cleanup

### 5. Session and Proxy Hardening Are Documented More Than Enforced

Severity: Watch item

The docs correctly say the app should run behind HTTPS and same-origin browser traffic. The API guard also blocks cross-origin writes. But the code does not visibly set hardened Flask session defaults such as:

- `SESSION_COOKIE_SECURE`
- `SESSION_COOKIE_SAMESITE`
- `SESSION_COOKIE_HTTPONLY`
- reverse-proxy handling such as `ProxyFix`

Impact:

- deploy safety depends on external infrastructure and environment discipline
- not an immediate code bug, but weaker than ideal for production defaults

This is a deployment-hardening gap, not a confirmed exploit path from the code alone.

## Test and Quality Status

Command run:

```bash
py -m pytest -q
```

Result:

- passed: 269
- failed: 2

Failing tests:

- `tests/test_v1_cleanup.py::test_templates_route_uses_active_template`
- `tests/test_v1_cleanup.py::test_oauth_select_page_uses_active_template`

Interpretation:

- backend logic is in relatively good shape
- route cleanup and UI migration are lagging behind the tested contract
- the test suite is useful and should be kept as part of release gates

## Security Review

### Positive Security Signals

- passwords use `bcrypt`
- tenant secrets are encrypted before storage
- JSON API routes use session auth rather than exposing bearer-token style API auth for the web flow
- mutating API routes reject cross-origin `Origin` and `Referer` mismatches
- risky V1-excluded endpoints are intentionally disabled

### Primary Security Concerns

- tenant isolation depends entirely on application query discipline because service-role Supabase access bypasses RLS
- `.fernet_key` is not ignored by Git
- production cookie and proxy hardening are not obviously enforced in code

## Maintainability Review

### What Helps Maintainability

- route and engine separation
- compatibility shims at repo root reduce breakage while code migrates into `engine/` and `database/`
- explicit runbooks and checklists
- extensive test suite

### What Hurts Maintainability

- branch is mid-migration and currently mixes old and new frontends
- duplicated compatibility layers can hide canonical ownership of modules
- some legacy comments and disabled surfaces indicate ongoing cleanup debt
- frontend behavior is currently harder to reason about than backend behavior because the intended main shell script is missing

## Operational Readiness

Current readiness judgment:

- backend foundation: moderately strong
- tenant model: mostly sound, with one critical safety flaw in publish gating
- docs and migrations: strong enough for controlled rollout
- frontend completeness: not ready in the current branch snapshot
- release confidence for this exact checkout: not ready

Why not ready:

- missing shell JS path
- dirty migration state
- 2 failing tests
- tenant publish gating flaw

## Recommended Remediation Order

### Priority 1

1. Restore or replace `static/js/cf.js` and confirm dashboard, studio, channels, and settings actually work end-to-end in a browser.
2. Make rate limiter and ban detector tenant-aware.
3. Add `.fernet_key` to `.gitignore`.

### Priority 2

4. Decide the canonical navigation contract for `/templates`, `/channels`, and OAuth page selection.
5. Update either code or cleanup tests so the contract is explicit and stable.
6. Add release validation for active frontend asset presence.

### Priority 3

7. Harden production defaults in code or config docs for secure cookies and reverse-proxy awareness.
8. Reduce migration ambiguity by removing dead references once the new shell is fully committed.

## Concrete Next Actions

Recommended immediate engineering tasks:

1. Fix tenant scoping in `engine/rate_limiter.py`, `engine/ban_detector.py`, and caller sites in `engine/publisher.py`.
2. Restore the missing shell/controller JS or rewire templates to existing scripts.
3. Add `.fernet_key` to `.gitignore`.
4. Resolve the two failing tests in `tests/test_v1_cleanup.py`.
5. Run a smoke pass for:
   - login/register
   - settings save/load
   - Facebook OAuth page connect
   - studio generate/save/schedule
   - publish path
   - Telegram link and status

## Final Assessment

This is not a weak project. It is a project with a stronger backend than frontend at the current moment.

The most important takeaway is:

- the core SaaS backend direction is valid
- tenant-aware data modeling is mostly in place
- test coverage is a real asset
- the current branch should be treated as an active migration branch, not as a finished release candidate

Once the missing frontend runtime is restored and the global publish-safety logic is made tenant-aware, the codebase will be in a much better position for a controlled V1 release.
