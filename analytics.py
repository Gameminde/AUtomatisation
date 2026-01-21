"""Sync basic analytics for published posts."""

from __future__ import annotations

from typing import Dict, Optional

import requests

import config

logger = config.get_logger("analytics")


GRAPH_API_VERSION = "v19.0"


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{path.lstrip('/')}"


def fetch_post_metrics(post_id: str) -> Optional[Dict]:
    access_token = config.require_env("FACEBOOK_ACCESS_TOKEN")
    fields = "shares,comments.summary(true),likes.summary(true)"
    url = _graph_url(post_id)
    params = {"access_token": access_token, "fields": fields}
    try:
        resp = requests.get(url, params=params, timeout=config.HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Metrics request failed for %s: %s", post_id, exc)
        return None

    data = resp.json()
    likes = data.get("likes", {}).get("summary", {}).get("total_count", 0)
    comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
    shares = data.get("shares", {}).get("count", 0)
    return {"likes": likes, "comments": comments, "shares": shares}


def update_published_post(post_id: str, metrics: Dict) -> None:
    client = config.get_supabase_client()
    client.table("published_posts").update(metrics).eq("facebook_post_id", post_id).execute()


def sync_metrics(limit: int = 25) -> int:
    client = config.get_supabase_client()
    response = (
        client.table("published_posts")
        .select("facebook_post_id")
        .order("published_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = response.data or []
    updated = 0
    for row in rows:
        post_id = row.get("facebook_post_id")
        if not post_id:
            continue
        metrics = fetch_post_metrics(post_id)
        if not metrics:
            continue
        update_published_post(post_id, metrics)
        updated += 1
    logger.info("Updated metrics for %s posts", updated)
    return updated


if __name__ == "__main__":
    sync_metrics()
