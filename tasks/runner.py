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
    Try to acquire a per-user pipeline lock using Supabase `system_status`.

    The lock is a row whose key is ``pipeline_lock:<user_id>`` and whose value
    is a UTC ISO-8601 timestamp.  If a row already exists and was written less
    than PIPELINE_TIMEOUT_SECONDS ago the lock is considered held and we return
    False.  Otherwise we upsert the row with the current timestamp and return True.

    Parameters
    ----------
    user_id : str

    Returns
    -------
    bool
        True if the lock was acquired, False if another worker already holds it.
    """
    try:
        sb = _get_sb()
        key = f"{_LOCK_KEY_PREFIX}{user_id}"
        now = datetime.now(timezone.utc)

        # Check for an existing lock
        existing = (
            sb.table("system_status")
            .select("value, updated_at")
            .eq("key", key)
            .limit(1)
            .execute()
        )
        if existing.data:
            row = existing.data[0]
            try:
                locked_at_str = row.get("updated_at") or row.get("value") or ""
                locked_at = datetime.fromisoformat(locked_at_str.replace("Z", "+00:00"))
                age_seconds = (now - locked_at).total_seconds()
                if age_seconds < PIPELINE_TIMEOUT_SECONDS:
                    logger.debug(
                        "Lock held for user %s (age=%ds)", user_id[:8], int(age_seconds)
                    )
                    return False
            except Exception:
                pass  # Malformed timestamp — treat as expired, overwrite

        # Acquire / refresh the lock
        sb.table("system_status").upsert(
            {"key": key, "value": now.isoformat(), "updated_at": now.isoformat()},
            on_conflict="key",
        ).execute()
        return True

    except Exception as exc:
        logger.warning("Lock acquire failed for user %s: %s", user_id[:8], exc)
        return True  # Fail open — better to run twice than never


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

        # Step 1: Scrape
        try:
            from scraper import run as scrape_run
            saved = scrape_run(user_id=uid)
            result["articles"] = saved or 0
            logger.info("  Scraped %d articles (user=%s)", result["articles"], uid_short)
        except Exception as exc:
            logger.warning("  Scrape failed (user=%s): %s", uid_short, exc)

        # Step 2: Generate AI content
        try:
            from ai_generator import process_pending_articles
            generated = process_pending_articles(
                limit=10,
                batch_size=5,
                user_id=uid,
            )
            result["generated"] = generated or 0
            logger.info("  Generated %d items (user=%s)", result["generated"], uid_short)
        except Exception as exc:
            logger.warning("  AI generation failed (user=%s): %s", uid_short, exc)

        # Step 3: Schedule (honoring user's posting_times + posts_per_day)
        try:
            from scheduler import schedule_posts
            schedule_posts(
                days=1,
                max_per_day=user_config.posts_per_day,
                posting_times_override=user_config.posting_times,
                user_id=uid,
            )
            logger.info("  Scheduling done (user=%s)", uid_short)
        except TypeError:
            # Older scheduler that doesn't accept posting_times_override
            from scheduler import schedule_posts as _sp
            _sp(days=1, max_per_day=user_config.posts_per_day, user_id=uid)
            logger.info("  Scheduling done (legacy, user=%s)", uid_short)
        except Exception as exc:
            logger.warning("  Scheduling failed (user=%s): %s", uid_short, exc)

        # Step 4: Publish due posts
        try:
            from publisher import publish_due_posts
            published = publish_due_posts(limit=5, user_id=uid)
            result["published"] = published or 0
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
        for future in as_completed(futures, timeout=PIPELINE_TIMEOUT_SECONDS + 30):
            uid = futures[future]
            try:
                res = future.result(timeout=PIPELINE_TIMEOUT_SECONDS)
                results.append(res)
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
