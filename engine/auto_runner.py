"""
auto_runner — Multi-tenant background pipeline runner.

Runs the full content pipeline (scrape → generate → schedule → publish)
for all active users concurrently using a ThreadPoolExecutor.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import config

logger = config.get_logger("auto_runner")

MAX_WORKERS = 10
PIPELINE_TIMEOUT_SECONDS = 300


def _load_active_user_ids() -> List[str]:
    """Return unique user_ids that have at least one active managed_pages row."""
    try:
        from app.utils import _get_supabase_client
        sb = _get_supabase_client()
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


def run_pipeline_for_user(user_config) -> Dict:
    """
    Run the full content pipeline for a single tenant.

    Steps
    -----
    1. Scrape new articles from RSS / NewsData / HN
    2. Generate AI content for pending articles
    3. Schedule content for the next day
    4. Publish any due scheduled posts

    Each step is isolated — failures do not abort subsequent steps.

    Parameters
    ----------
    user_config : UserConfig
        Resolved config for the target user.

    Returns
    -------
    dict
        Summary with counts for articles, generated, published and any error.
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

    logger.info("Pipeline start: user=%s", uid_short)

    # ── Step 1: Scrape ─────────────────────────────────────────────────────
    try:
        from scraper import run as scrape_run
        saved = scrape_run(user_id=uid)
        result["articles"] = saved or 0
        logger.info("  Scraped %d articles (user=%s)", result["articles"], uid_short)
    except Exception as exc:
        logger.warning("  Scrape failed (user=%s): %s", uid_short, exc)

    # ── Step 2: Generate AI content ────────────────────────────────────────
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

    # ── Step 3: Schedule content ───────────────────────────────────────────
    try:
        from scheduler import schedule_posts
        schedule_posts(
            days=1,
            max_per_day=user_config.posts_per_day,
            user_id=uid,
        )
        logger.info("  Scheduling done (user=%s)", uid_short)
    except Exception as exc:
        logger.warning("  Scheduling failed (user=%s): %s", uid_short, exc)

    # ── Step 4: Publish due posts ──────────────────────────────────────────
    try:
        from publisher import publish_due_posts
        published = publish_due_posts(limit=5, user_id=uid)
        result["published"] = published or 0
        logger.info("  Published %d posts (user=%s)", result["published"], uid_short)
    except Exception as exc:
        logger.warning("  Publish failed (user=%s): %s", uid_short, exc)

    logger.info("Pipeline done: user=%s result=%s", uid_short, result)
    return result


def run_all_users(max_workers: int = MAX_WORKERS) -> Dict:
    """
    Load all active tenants and run the pipeline for each concurrently.

    Parameters
    ----------
    max_workers : int
        Maximum parallel threads (capped to the number of active users).

    Returns
    -------
    dict
        Summary with per-user results and aggregate published count.
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

    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        futures = {
            executor.submit(run_pipeline_for_user, UserConfig.from_db(uid)): uid
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
    logger.info("run_all_users done: published_total=%d", summary["published_total"])
    return summary


def run_pipeline(user_id: Optional[str] = None) -> Dict:
    """
    Public entry point — run the pipeline for a single user or all users.

    Parameters
    ----------
    user_id : str | None
        When provided, run only for that user.
        When None, run for all active users.

    Returns
    -------
    dict
        Pipeline result(s).
    """
    if user_id:
        from user_config import UserConfig
        return run_pipeline_for_user(UserConfig.from_db(user_id))
    return run_all_users()
