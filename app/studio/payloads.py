"""Studio payload builders used by routes and bootstrap."""

from __future__ import annotations

import json
from typing import Any, Dict

from . import helpers as studio_helpers

_client = studio_helpers._client
_build_content_preview = studio_helpers._build_content_preview
_extract_language_from_content = studio_helpers._extract_language_from_content
_load_active_page_context = studio_helpers._load_active_page_context
_normalize_draft_row = studio_helpers._normalize_draft_row


def _load_pending_content_payload(user_id: str, limit: int = 20) -> Dict[str, Any]:
    result = (
        _client()
        .table("processed_content")
        .select(
            "id, post_type, generated_text, hook, hashtags, image_path, "
            "generated_at, status, article_id, target_audience"
        )
        .eq("status", "waiting_approval")
        .eq("user_id", user_id)
        .order("generated_at", desc=True)
        .limit(limit)
        .execute()
    )
    page_context = _load_active_page_context(user_id)
    rows = result.data or []
    article_ids = [
        str(row.get("article_id") or "").strip()
        for row in rows
        if str(row.get("article_id") or "").strip()
    ]
    article_lookup: Dict[str, Dict[str, Any]] = {}
    if article_ids:
        article_rows = (
            _client()
            .table("raw_articles")
            .select("id, title, source_name, url")
            .eq("user_id", user_id)
            .in_("id", article_ids)
            .execute()
        ).data or []
        article_lookup = {str(row.get("id")): row for row in article_rows}

    pending = []
    for row in rows:
        article = article_lookup.get(str(row.get("article_id") or ""))
        pending.append(
            {
                **row,
                "language": _extract_language_from_content(row),
                "page_id": page_context.get("page_id", ""),
                "page_name": page_context.get("page_name", "Connected page"),
                "platforms": page_context.get("platforms", "facebook"),
                "platform_label": page_context.get("platform_label", "Facebook"),
                "page_language": page_context.get("language", ""),
                "preview_text": _build_content_preview(row),
                "context": {
                    "article_title": (article or {}).get("title") or "",
                    "source_name": (article or {}).get("source_name") or "",
                    "url": (article or {}).get("url") or "",
                },
            }
        )
    return {"pending": pending}


def _load_draft_content_payload(user_id: str, limit: int = 50) -> Dict[str, Any]:
    result = (
        _client()
        .table("processed_content")
        .select("id, post_type, generated_text, hook, hashtags, image_path, status, generated_at, article_id")
        .eq("user_id", user_id)
        .in_("status", ["draft_only", "draft_ready", "drafted", "pending"])
        .order("generated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"drafts": [_normalize_draft_row(row) for row in (result.data or [])]}


def _load_scheduled_content_payload(user_id: str, limit: int = 20) -> Dict[str, Any]:
    result = (
        _client()
        .table("scheduled_posts")
        .select("id, content_id, scheduled_time, timezone, status, platforms")
        .eq("status", "scheduled")
        .eq("user_id", user_id)
        .order("scheduled_time")
        .limit(limit)
        .execute()
    )
    return {"scheduled": result.data or []}


def _load_published_content_payload(user_id: str, limit: int = 20) -> Dict[str, Any]:
    result = (
        _client()
        .table("published_posts")
        .select(
            "id, content_id, facebook_post_id, facebook_status, instagram_post_id, "
            "instagram_status, platforms, published_at, likes, shares, comments, reach"
        )
        .eq("user_id", user_id)
        .order("published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"published": result.data or []}


def _load_dashboard_summary_payload(user_id: str) -> Dict[str, Any]:
    client = _client()
    pending = (
        client.table("processed_content")
        .select("id, generated_text, generated_at")
        .eq("status", "waiting_approval")
        .eq("user_id", user_id)
        .order("generated_at", desc=True)
        .limit(5)
        .execute()
    ).data or []
    scheduled = (
        client.table("scheduled_posts")
        .select("id, scheduled_time, status")
        .eq("status", "scheduled")
        .eq("user_id", user_id)
        .order("scheduled_time")
        .limit(5)
        .execute()
    ).data or []
    published = (
        client.table("published_posts")
        .select("id, published_at")
        .eq("user_id", user_id)
        .order("published_at", desc=True)
        .limit(5)
        .execute()
    ).data or []
    return {
        "pending": [
            {
                "id": row["id"],
                "text": row.get("generated_text", "No text"),
                "time": str(row.get("generated_at") or "").split("T")[0],
                "image": f"/api/content/{row['id']}/image",
            }
            for row in pending
        ],
        "scheduled": [
            {
                "id": row["id"],
                "text": "Scheduled Post",
                "time": str(row.get("scheduled_time") or "").replace("T", " ")[:16],
                "image": None,
            }
            for row in scheduled
        ],
        "published": [
            {
                "id": row["id"],
                "text": "Published Post",
                "time": str(row.get("published_at") or "").replace("T", " ")[:16],
                "image": None,
            }
            for row in published
        ],
        "ready_count": len(scheduled),
    }


def _load_studio_bootstrap_payload(user_id: str) -> Dict[str, Any]:
    from app.utils import get_available_presets
    from app.utils import get_user_settings
    from user_config import get_user_config
    from . import routes as studio_routes

    profile = get_user_config(user_id)
    settings = get_user_settings(user_id) or {}
    template_defaults_raw = str(settings.get("studio_template_defaults") or "").strip()
    try:
        template_defaults = json.loads(template_defaults_raw) if template_defaults_raw else {}
    except Exception:
        template_defaults = {}
    normalized_template_defaults = studio_routes._normalize_template_defaults(template_defaults if isinstance(template_defaults, dict) else {})
    return {
        "profile": {
            "timezone": profile.timezone,
            "content_language": profile.content_language,
            "content_tone": profile.content_tone,
            "niche_preset": profile.niche_preset,
            "template_defaults": normalized_template_defaults,
        },
        "page_context": _load_active_page_context(user_id),
        **_load_draft_content_payload(user_id),
        **_load_pending_content_payload(user_id),
        **_load_scheduled_content_payload(user_id),
        **_load_published_content_payload(user_id),
        "presets": {"niches": get_available_presets()["niches"]},
    }
