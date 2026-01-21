"""Publish scheduled posts to Facebook."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Dict, Optional

import requests

import config

logger = config.get_logger("publisher")


GRAPH_API_VERSION = "v19.0"


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{path.lstrip('/')}"


def publish_text_post(message: str) -> str:
    access_token = config.require_env("FACEBOOK_ACCESS_TOKEN")
    page_id = config.require_env("FACEBOOK_PAGE_ID")
    url = _graph_url(f"{page_id}/feed")
    payload = {"message": message, "access_token": access_token}
    try:
        resp = requests.post(url, data=payload, timeout=config.HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Facebook post failed: {exc}") from exc
    data = resp.json()
    post_id = data.get("id")
    if not post_id:
        raise RuntimeError("Facebook response missing post id")
    return post_id


def publish_reel(video_url: str, description: str) -> str:
    access_token = config.require_env("FACEBOOK_ACCESS_TOKEN")
    page_id = config.require_env("FACEBOOK_PAGE_ID")
    url = _graph_url(f"{page_id}/videos")
    payload = {
        "file_url": video_url,
        "description": description,
        "access_token": access_token,
    }
    try:
        resp = requests.post(url, data=payload, timeout=config.HTTP_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Facebook reel upload failed: {exc}") from exc
    data = resp.json()
    post_id = data.get("id")
    if not post_id:
        raise RuntimeError("Facebook response missing video id")
    return post_id


def fetch_due_posts(limit: int = 5):
    client = config.get_supabase_client()
    now = datetime.utcnow().replace(tzinfo=None).isoformat()
    response = (
        client.table("scheduled_posts")
        .select("id,content_id,scheduled_time,status")
        .lte("scheduled_time", now)
        .eq("status", "scheduled")
        .order("scheduled_time")
        .limit(limit)
        .execute()
    )
    return response.data or []


def fetch_content(content_id: str) -> Optional[Dict]:
    client = config.get_supabase_client()
    response = (
        client.table("processed_content")
        .select("id,post_type,generated_text,script_for_reel,hook,call_to_action")
        .eq("id", content_id)
        .single()
        .execute()
    )
    return response.data


def mark_published(content_id: str, post_id: str) -> None:
    client = config.get_supabase_client()
    client.table("published_posts").insert(
        {
            "content_id": content_id,
            "facebook_post_id": post_id,
        }
    ).execute()


def update_schedule_status(schedule_id: str, status: str) -> None:
    client = config.get_supabase_client()
    client.table("scheduled_posts").update({"status": status}).eq("id", schedule_id).execute()


def publish_due_posts(limit: int = 5) -> int:
    due_posts = fetch_due_posts(limit=limit)
    published = 0
    for item in due_posts:
        schedule_id = item["id"]
        content = fetch_content(item["content_id"])
        if not content:
            update_schedule_status(schedule_id, "failed")
            continue
        try:
            if content["post_type"] == "text":
                message = f"{content.get('hook', '')}\n\n{content.get('generated_text', '')}\n\n{content.get('call_to_action', '')}"
                post_id = publish_text_post(message)
            else:
                raise RuntimeError("Reel publishing requires a video URL")
            mark_published(content["id"], post_id)
            update_schedule_status(schedule_id, "published")
            published += 1
            time.sleep(config.REQUEST_SLEEP_SECONDS)
        except Exception as exc:
            logger.error("Publish failed for %s: %s", schedule_id, exc)
            update_schedule_status(schedule_id, "failed")
    logger.info("Published %s posts", published)
    return published


if __name__ == "__main__":
    publish_due_posts()
