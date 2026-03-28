"""
analytics_sync — Sync post engagement metrics from Facebook Graph API.

Fetches likes, comments, shares, reach, and impressions for recently
published posts and writes them back to the ``published_posts`` table in
Supabase, scoped per-tenant via user_id.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import config

logger = config.get_logger("analytics_sync")

GRAPH_API_VERSION = "v19.0"
LOOKBACK_DAYS = 7


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{path.lstrip('/')}"


def _fetch_post_insights(
    fb_post_id: str, page_token: str
) -> Dict:
    """
    Fetch engagement metrics for a single Facebook post.

    Returns a dict with keys: likes, comments, shares, reach.
    Returns empty dict on failure (non-blocking).
    """
    import requests

    try:
        url = _graph_url(fb_post_id)
        resp = requests.get(
            url,
            params={
                "fields": "likes.summary(true),comments.summary(true),shares,insights.metric(post_impressions_unique)",
                "access_token": page_token,
            },
            timeout=config.HTTP_TIMEOUT_SECONDS,
        )
        if not resp.ok:
            logger.debug("Graph API error for post %s: %s", fb_post_id, resp.status_code)
            return {}

        data = resp.json()
        metrics: Dict = {
            "likes": data.get("likes", {}).get("summary", {}).get("total_count", 0),
            "comments": data.get("comments", {}).get("summary", {}).get("total_count", 0),
            "shares": (data.get("shares") or {}).get("count", 0),
        }

        # reach from insights
        insights = data.get("insights", {}).get("data", [])
        for item in insights:
            if item.get("name") == "post_impressions_unique":
                vals = item.get("values", [])
                if vals:
                    metrics["reach"] = vals[-1].get("value", 0)

        return metrics

    except Exception as exc:
        logger.debug("_fetch_post_insights failed for %s: %s", fb_post_id, exc)
        return {}


def sync_metrics(user_config) -> int:
    """
    Sync engagement metrics for all recently published posts belonging to
    *user_config.user_id* that have a Facebook post ID.

    Parameters
    ----------
    user_config : UserConfig
        Must have facebook_access_token set for API calls to succeed.

    Returns
    -------
    int
        Number of posts whose metrics were successfully updated.
    """
    uid = user_config.user_id
    uid_short = uid[:8]
    page_token = user_config.facebook_access_token

    if not page_token:
        logger.debug("No page token for user %s — skipping analytics sync", uid_short)
        return 0

    try:
        client = config.get_database_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()

        result = (
            client.table("published_posts")
            .select("id, facebook_post_id, published_at")
            .eq("user_id", uid)
            .gte("published_at", cutoff)
            .not_.is_("facebook_post_id", "null")
            .order("published_at", desc=True)
            .limit(20)
            .execute()
        )
        rows: List[Dict] = result.data or []

    except Exception as exc:
        logger.warning("Analytics sync DB fetch failed (user=%s): %s", uid_short, exc)
        return 0

    updated = 0
    for row in rows:
        fb_post_id = row.get("facebook_post_id")
        if not fb_post_id:
            continue

        metrics = _fetch_post_insights(fb_post_id, page_token)
        if not metrics:
            continue

        try:
            client.table("published_posts").update(metrics).eq("id", row["id"]).execute()
            updated += 1
        except Exception as exc:
            logger.debug("Metrics write failed for post %s: %s", fb_post_id, exc)

    logger.info(
        "Analytics sync complete: %d/%d posts updated (user=%s)",
        updated, len(rows), uid_short
    )
    return updated
