# Rollback Plan

This rollback plan assumes the current V1 deployment model:
- Flask web app
- Supabase database
- separate `tasks.runner`
- separate `tasks.telegram_bot`

## 1. Rollback Triggers

Rollback immediately if any of these happen after deploy:
- login or session flow is broken
- Settings save is broken
- Facebook OAuth callback or page picker is broken
- Studio generate/save/approve is broken
- worker startup fails
- authenticated POST requests are blocked unexpectedly in the deployed environment

## 2. Immediate Actions

1. Stop new deploy propagation.
2. Revert the app release to the last known good build.
3. Restart services in this order:
   1. web
   2. `tasks.runner`
   3. `tasks.telegram_bot`
4. Re-run the core smoke path:
   - login
   - settings save
   - OAuth connect
   - studio generate/save

## 3. Database Guidance

- The current migration path is additive and mostly uses nullable/defaulted columns.
- Do not rush to roll back the database if the failure is app-code only.
- Prefer:
  - revert app release first
  - keep DB at the newer schema if the previous app version tolerates it
- Use a database restore only if the failure is clearly caused by schema/data migration and the app rollback is insufficient.

## 4. If Same-Origin Guard Causes Production Breakage

Symptoms:
- authenticated POST/PUT actions fail with `403`
- error code `csrf_origin_mismatch`

Check first:
- proxy preserves original host and scheme
- app is served over HTTPS
- frontend requests are same-origin
- `X-Requested-With` header is not stripped

If this cannot be fixed immediately:
1. roll back the app release
2. restore the previous web build
3. restart web + workers
4. verify POST flows again

## 5. Post-Rollback Verification

- [ ] login works
- [ ] settings save works
- [ ] Facebook OAuth works
- [ ] Studio generate/save works
- [ ] Dashboard loads
- [ ] workers are running

## 6. Aftercare

- capture the failing request/route
- save logs from web and workers
- record whether the issue was:
  - code regression
  - proxy / HTTPS misconfiguration
  - env var issue
  - OAuth configuration issue
  - worker/process issue
