"""
tasks/runner.py — APScheduler-based multi-tenant pipeline runner.

Responsibilities
----------------
- Load all active tenants from Supabase `managed_pages`
- Acquire a per-user distributed lock via `system_status` before running each
  user's pipeline, preventing duplicate runs across Gunicorn workers
- Run the 5-step pipeline (scrape → generate → schedule → publish → analytics)
  for each tenant concurrently in a ThreadPoolExecutor
- APScheduler fires `run_all_users` every PIPELINE_INTERVAL_SECONDS (default 30 min)

Usage (called from dashboard_app.py / wsgi.py at startup)
----------------------------------------------------------
    from tasks.runner import start_scheduler
    start_scheduler()
"""

from __future__ import annotations

import logging
import os
import sys

# Ensure the project root and engine/ are on sys.path so bare module imports
# (scraper, publisher, scheduler, etc.) resolve correctly regardless of how
# this module is first loaded (by dashboard_app, wsgi, or a test runner).
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_ENGINE = os.path.join(_ROOT, "engine")
for _p in (_ROOT, _ENGINE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional

import config

logger = config.get_logger("runner")

MAX_WORKERS: int = int(os.getenv("PIPELINE_MAX_WORKERS", "10"))
PIPELINE_INTERVAL_SECONDS: int = int(os.getenv("PIPELINE_INTERVAL_SECONDS", "1800"))
PIPELINE_STARTUP_DELAY_SECONDS: int = int(os.getenv("PIPELINE_STARTUP_DELAY", "90"))
PIPELINE_TIMEOUT_SECONDS: int = int(os.getenv("PIPELINE_TIMEOUT", "300"))

# Key prefix used in system_status for per-user pipeline locks
_LOCK_KEY_PREFIX = "pipeline_lock:"


# ── Distributed lock helpers (system_status table) ──────────────────────────

def _acquire_user_lock(user_id: str) -> bool:
    """
    Try to acquire a per-user pipeline lock using Supabase ``system_status``.

    Strategy (minimises race window):
    1. Read the existing row.
    2a. If no row → try INSERT; if INSERT succeeds we hold the lock.
        If INSERT fails (unique conflict from another worker) → lock held, return False.
    2b. If row exists and lock is fresh → return False immediately.
    2c. If row exists but lock is expired → do a conditional UPDATE filtered by
        the old ``updated_at`` timestamp. If 0 rows updated, another worker won
        the race → return False.

    On any DB error the lock is NOT granted (fail-closed) to prevent two workers
    from running the same user concurrently.

    Parameters
    ----------
    user_id : str

    Returns
    -------
    bool
        True if the lock was acquired by this worker, False otherwise.
    """
    try:
        sb = _get_sb()
        key = f"{_LOCK_KEY_PREFIX}{user_id}"
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Step 1: Read existing lock row
        existing = (
            sb.table("system_status")
            .select("value, updated_at")
            .eq("key", key)
            .limit(1)
            .execute()
        )

        if not existing.data:
            # Step 2a: No lock — try to INSERT (atomic; fails on conflict)
            try:
                sb.table("system_status").insert(
                    {"key": key, "value": now_iso, "updated_at": now_iso}
                ).execute()
                return True
            except Exception:
                # Another worker inserted between our read and insert
                return False

        # Step 2b/2c: Lock row exists — check freshness
        row = existing.data[0]
        old_ts = row.get("updated_at") or row.get("value") or ""
        try:
            locked_at = datetime.fromisoformat(old_ts.replace("Z", "+00:00"))
            age_seconds = (now - locked_at).total_seconds()
        except Exception:
            # Malformed timestamp — treat as fully expired
            age_seconds = PIPELINE_TIMEOUT_SECONDS + 1

        if age_seconds < PIPELINE_TIMEOUT_SECONDS:
            # Lock is fresh — another worker holds it
            logger.debug(
                "Lock held for user %s (age=%ds)", user_id[:8], int(age_seconds)
            )
            return False

        # Step 2c: Lock is expired — conditional UPDATE (only if updated_at unchanged)
        result = (
            sb.table("system_status")
            .update({"value": now_iso, "updated_at": now_iso})
            .eq("key", key)
            .eq("updated_at", old_ts)
            .execute()
        )
        if result.data:
            return True  # We won the conditional update race

        # Another worker updated the row between our read and write
        return False

    except Exception as exc:
        logger.warning(
            "Lock acquire failed (fail-closed) for user %s: %s", user_id[:8], exc
        )
        return False  # Fail closed — skip this user rather than risk double-run


def _release_user_lock(user_id: str) -> None:
    """Delete the per-user pipeline lock from system_status."""
    try:
        sb = _get_sb()
        sb.table("system_status").delete().eq(
            "key", f"{_LOCK_KEY_PREFIX}{user_id}"
        ).execute()
    except Exception as exc:
        logger.warning("Lock release failed for user %s: %s", user_id[:8], exc)


def _get_sb():
    from app.utils import _get_supabase_client
    return _get_supabase_client()


# ── Active user discovery ────────────────────────────────────────────────────

def _load_active_user_ids() -> List[str]:
    """Return distinct user_ids that have at least one active managed_pages row."""
    try:
        sb = _get_sb()
        result = (
            sb.table("managed_pages")
            .select("user_id")
            .eq("status", "active")
            .execute()
        )
        seen: set = set()
        ids: List[str] = []
        for row in result.data or []:
            uid = row.get("user_id")
            if uid and uid not in seen:
                seen.add(uid)
                ids.append(uid)
        return ids
    except Exception as exc:
        logger.error("_load_active_user_ids failed: %s", exc)
        return []


# ── Per-user pipeline ────────────────────────────────────────────────────────

def _run_pipeline_for_user(user_config) -> Dict:
    """
    Execute the full 5-step pipeline for a single tenant, guarded by a
    distributed lock so concurrent workers don't double-process the same user.

    Steps
    -----
    1. Scrape new articles
    2. Generate AI content for pending articles
    3. Schedule content for the next day (respecting user's posting_times)
    4. Publish due scheduled posts using per-user Facebook credentials
    5. Sync engagement analytics from Facebook Graph API

    Parameters
    ----------
    user_config : UserConfig

    Returns
    -------
    dict
        Summary: user_id, articles, generated, published, error
    """
    uid = user_config.user_id
    uid_short = uid[:8]
    result: Dict = {
        "user_id": uid,
        "articles": 0,
        "generated": 0,
        "published": 0,
        "error": None,
    }

    if not user_config.is_configured():
        logger.info("Skipping user %s — not fully configured", uid_short)
        result["error"] = "not_configured"
        return result

    if not _acquire_user_lock(uid):
        logger.info("Skipping user %s — lock held by another worker", uid_short)
        result["error"] = "lock_held"
        return result

    try:
        logger.info("Pipeline start: user=%s", uid_short)

        # Step 1: Scrape — UserConfig is the first-class entry point
        try:
            from scraper import run_for_user as scrape_for_user
            result["articles"] = scrape_for_user(user_config) or 0
            logger.info("  Scraped %d articles (user=%s)", result["articles"], uid_short)
        except Exception as exc:
            logger.warning("  Scrape failed (user=%s): %s", uid_short, exc)

        # Step 2: Generate AI content — UserConfig is the first-class entry point
        try:
            from ai_generator import generate_for_user
            result["generated"] = generate_for_user(user_config) or 0
            logger.info("  Generated %d items (user=%s)", result["generated"], uid_short)
        except Exception as exc:
            logger.warning("  AI generation failed (user=%s): %s", uid_short, exc)

        # Step 3: Schedule (honoring user's posting_times + posts_per_day from managed_pages)
        try:
            from scheduler import schedule_for_user
            schedule_for_user(user_config)
            logger.info("  Scheduling done (user=%s)", uid_short)
        except Exception as exc:
            logger.warning("  Scheduling failed (user=%s): %s", uid_short, exc)

        # Step 4: Publish due posts (fail-closed — skips if no tenant creds)
        try:
            from publisher import publish_for_user
            result["published"] = publish_for_user(user_config) or 0
            logger.info("  Published %d posts (user=%s)", result["published"], uid_short)
        except Exception as exc:
            logger.warning("  Publish failed (user=%s): %s", uid_short, exc)

        # Step 5: Analytics sync
        try:
            from analytics_sync import sync_metrics
            sync_metrics(user_config)
            logger.info("  Analytics synced (user=%s)", uid_short)
        except Exception as exc:
            logger.warning("  Analytics sync failed (user=%s): %s", uid_short, exc)

        logger.info("Pipeline done: user=%s result=%s", uid_short, result)

    finally:
        _release_user_lock(uid)

    return result


# ── All-user orchestration ───────────────────────────────────────────────────

def run_all_users(max_workers: int = MAX_WORKERS) -> Dict:
    """
    Load all active tenants and run the pipeline for each concurrently.

    Parameters
    ----------
    max_workers : int
        Maximum parallel threads (capped to number of active users).

    Returns
    -------
    dict
        users, results list, published_total.
    """
    logger.info("run_all_users starting")
    user_ids = _load_active_user_ids()

    if not user_ids:
        logger.info("No active users — skipping run")
        return {"users": 0, "results": [], "published_total": 0}

    logger.info("Found %d active user(s)", len(user_ids))

    from user_config import UserConfig

    results: List[Dict] = []
    effective_workers = min(max_workers, len(user_ids))

    with ThreadPoolExecutor(max_workers=effective_workers, thread_name_prefix="pipeline") as executor:
        futures = {
            executor.submit(_run_pipeline_for_user, UserConfig.from_db(uid)): uid
            for uid in user_ids
        }
        # Iterate without a global batch timeout so queued users are always
        # processed as workers free up (TimeoutError would silently drop them).
        for future in as_completed(futures):
            uid = futures[future]
            try:
                # Per-future timeout ensures one slow user cannot block others
                res = future.result(timeout=PIPELINE_TIMEOUT_SECONDS)
                results.append(res)
            except TimeoutError:
                logger.error(
                    "Pipeline timed out for user=%s after %ds",
                    uid[:8], PIPELINE_TIMEOUT_SECONDS,
                )
                results.append({"user_id": uid, "error": "timeout"})
            except Exception as exc:
                logger.error("Pipeline future failed (user=%s): %s", uid[:8], exc)
                results.append({"user_id": uid, "error": str(exc)})

    summary: Dict = {
        "users": len(user_ids),
        "results": results,
        "published_total": sum(r.get("published", 0) for r in results),
    }
    logger.info(
        "run_all_users done: users=%d published_total=%d",
        summary["users"],
        summary["published_total"],
    )
    return summary


# ── APScheduler entry point ──────────────────────────────────────────────────

_scheduler_started: bool = False


def start_scheduler() -> None:
    """
    Start the APScheduler background scheduler if it hasn't been started yet.

    The scheduler fires ``run_all_users`` every PIPELINE_INTERVAL_SECONDS
    seconds.  An initial delay of PIPELINE_STARTUP_DELAY_SECONDS prevents the
    pipeline from hitting the DB before the Flask app is fully initialised.

    Safe to call multiple times — only one scheduler instance is created.
    """
    global _scheduler_started
    if _scheduler_started:
        logger.debug("Scheduler already started — skipping duplicate start")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler(daemon=True, timezone="UTC")
        scheduler.add_job(
            func=run_all_users,
            trigger=IntervalTrigger(seconds=PIPELINE_INTERVAL_SECONDS),
            id="pipeline_all_users",
            name="Pipeline — all users",
            replace_existing=True,
            next_run_time=None,  # Will be set after startup delay below
        )
        scheduler.start()
        _scheduler_started = True

        # Reschedule first run after startup delay
        import threading
        import time

        def _delayed_first_run() -> None:
            time.sleep(PIPELINE_STARTUP_DELAY_SECONDS)
            logger.info("Triggering first pipeline run after startup delay")
            try:
                scheduler.modify_job(
                    "pipeline_all_users",
                    next_run_time=datetime.now(timezone.utc),
                )
            except Exception:
                pass

        t = threading.Thread(target=_delayed_first_run, daemon=True, name="pipeline-delay")
        t.start()

        logger.info(
            "APScheduler started: first run in %ds, then every %ds",
            PIPELINE_STARTUP_DELAY_SECONDS,
            PIPELINE_INTERVAL_SECONDS,
        )

    except Exception as exc:
        logger.error("Failed to start APScheduler: %s", exc, exc_info=True)
