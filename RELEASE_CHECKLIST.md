# Release Checklist

Status target: `Ready with cautions`

This checklist is for the current shipped V1 scope only:
- Supabase-backed SaaS runtime
- Facebook/Instagram page workflow
- AI provider BYO-key setup
- Studio draft/generate/approve/schedule/publish flow
- Telegram connection and daily summary toggle

## 1. Code And Test Baseline

- [ ] Working tree reviewed and release branch/tag chosen
- [ ] Non-V1 surfaces remain disabled:
  - `/api/insights`
  - A/B testing APIs
  - virality scoring APIs
  - randomization tuning APIs
  - legacy module-status, agent-control, raw-log APIs
  - legacy template customization/template-library APIs
- [ ] Full automated suite passes locally:
  - `py -m pytest -q`
- [ ] Frontend syntax checks pass:
  - `node --check static/js/api.js`
  - `node --check static/js/cf.js`

## 2. Database Readiness

- [ ] Production Supabase project is selected correctly
- [ ] [`supabase_schema.sql`](C:/Users/youcefcheriet/fb/fbautomat/supabase_schema.sql) has been applied on new environments
- [ ] [`migrations/001_saas_alignment.sql`](C:/Users/youcefcheriet/fb/fbautomat/migrations/001_saas_alignment.sql) has been applied on the target environment
- [ ] `public.user_settings` contains at least:
  - `ui_language`
  - `ai_provider`
  - `ai_model`
  - `ai_api_key`
  - `daily_summary_time`
- [ ] `managed_pages.user_id` exists
- [ ] `processed_content.user_id` exists
- [ ] `scheduled_posts.user_id` exists
- [ ] `published_posts.user_id` exists
- [ ] A current database backup or snapshot exists before go-live

## 3. Environment Variables

Required:
- [ ] `DB_MODE=supabase`
- [ ] `SUPABASE_URL`
- [ ] `SUPABASE_KEY`
- [ ] `APP_BASE_URL`
- [ ] `FLASK_SECRET_KEY`
- [ ] `FERNET_KEY`
- [ ] `FB_APP_ID`
- [ ] `FB_APP_SECRET`
- [ ] `FB_REDIRECT_URI`

Optional but commonly needed:
- [ ] `TELEGRAM_BOT_TOKEN`
- [ ] `TELEGRAM_BOT_USERNAME`
- [ ] `ALLOW_ENV_AI_FALLBACK` only if intentionally using server-side fallback keys
- [ ] provider fallback keys only if intentionally enabled
- [ ] `PEXELS_API_KEY`
- [ ] `PIXABAY_API_KEY`
- [ ] `NEWSDATA_API_KEY`

## 4. Auth, HTTPS, And Proxy Expectations

- [ ] Production is behind HTTPS
- [ ] Session cookies are working end-to-end
- [ ] Reverse proxy preserves original host/scheme
- [ ] Same-origin authenticated browser flow is preserved
- [ ] Authenticated mutating API routes are not being called cross-origin
- [ ] The shipped frontend still sends:
  - `credentials: same-origin`
  - `X-Requested-With: XMLHttpRequest`

## 5. Meta OAuth Readiness

- [ ] Meta app supports Facebook Login
- [ ] Redirect URL matches `FB_REDIRECT_URI`
- [ ] App mode / tester permissions are correct for the release environment
- [ ] Facebook page connect flow works
- [ ] Page picker works
- [ ] Connected page appears in Dashboard and Settings
- [ ] Instagram linkage is verified if required

## 6. Runtime Processes

- [ ] Web process command is chosen and tested
  - `py dashboard_app.py` or
  - `gunicorn --bind=0.0.0.0:5000 --reuse-port dashboard_app:app`
- [ ] Background runner is running:
  - `python -m tasks.runner`
- [ ] Telegram worker is running if Telegram is part of launch:
  - `python -m tasks.telegram_bot`
- [ ] Restart order for deploy is confirmed:
  1. web
  2. runner
  3. telegram worker

## 7. Manual QA Gate

- [ ] Run every item in [SMOKE_TEST_CHECKLIST.md](C:/Users/youcefcheriet/fb/fbautomat/SMOKE_TEST_CHECKLIST.md)
- [ ] Any failed smoke test is resolved or explicitly waived
- [ ] Final go/no-go owner signs off

## 8. Go / No-Go

Go only if all of the following are true:
- [ ] No unresolved code-level release blocker remains
- [ ] Database migration state is confirmed on target
- [ ] Required env vars are present on target
- [ ] Meta OAuth works on target
- [ ] Web + worker processes are running
- [ ] Smoke test passes on target

