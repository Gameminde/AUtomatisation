"""
Core API routes - system status, shipped analytics, health diagnostics,
Facebook/Instagram status, AI, license, and Telegram.

Content CRUD -> app/studio/routes.py  (studio_bp)
Pages CRUD   -> app/pages/routes.py   (pages_bp)
Settings     -> app/settings/routes.py (settings_bp)
"""

import os
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict

import requests
from flask import Blueprint, g, jsonify, request
from flask_login import current_user

import config
import app.utils as app_utils
from app.utils import api_login_required, disabled_in_v1

logger = config.get_logger("api")

api_bp = Blueprint("api", __name__)
_BOOTSTRAP_CACHE_TTL_SECONDS = float(os.getenv("BOOTSTRAP_CACHE_TTL_SECONDS", "30"))
_bootstrap_cache: dict[tuple[str, str], tuple[float, Dict[str, Any]]] = {}


def _is_truthy(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _safe_count(result) -> int:
    count = getattr(result, "count", None)
    if count is not None:
        return int(count or 0)
    return len(getattr(result, "data", []) or [])


def _format_platforms(platforms: str) -> str:
    names = [token.strip().capitalize() for token in str(platforms or "facebook").split(",") if token.strip()]
    return ", ".join(names) if names else "Facebook"


def _validate_license_request(data: dict):
    from license_validator import validate_license

    key = (data.get("license_key") or "").strip()
    platform = (data.get("platform") or "").strip() or None
    if not key:
        return {"valid": False, "reason": "No key provided"}, 400
    return validate_license(key, platform=platform), 200


def _api_success(**payload):
    data = {"success": True}
    data.update(payload)
    return jsonify(data)


def _api_error(message: str, status: int = 400, **payload):
    data = {"success": False, "error": message}
    data.update(payload)
    return jsonify(data), status


def _request_cache_value(key: str, builder: Callable[[], Any]):
    try:
        cached = getattr(g, key, None)
        if cached is not None:
            return cached
    except RuntimeError:
        return builder()
    value = builder()
    setattr(g, key, value)
    return value


def _bootstrap_cache_get(cache_key: tuple[str, str], *, allow_stale: bool = False):
    if _BOOTSTRAP_CACHE_TTL_SECONDS <= 0:
        return None
    cached = _bootstrap_cache.get(cache_key)
    if not cached:
        return None
    cached_at, payload = cached
    age = time.monotonic() - cached_at
    if age > _BOOTSTRAP_CACHE_TTL_SECONDS and not allow_stale:
        return None
    return deepcopy(payload)


def _bootstrap_cache_set(cache_key: tuple[str, str], payload: Dict[str, Any]) -> None:
    if _BOOTSTRAP_CACHE_TTL_SECONDS <= 0:
        return
    _bootstrap_cache[cache_key] = (time.monotonic(), deepcopy(payload))


def _safe_bootstrap_value(
    label: str,
    builder: Callable[[], Any],
    default: Any,
    errors: list[Dict[str, str]],
):
    try:
        return builder()
    except Exception as exc:
        logger.warning("Bootstrap section %s failed: %s", label, exc)
        errors.append({"section": label, "error": str(exc)})
        return deepcopy(default)


def _default_health_payload() -> Dict[str, Any]:
    return {
        "ai_source": "not_configured",
        "page": {"connected": False, "page_id": "", "page_name": "", "status": "missing"},
        "tokens": {
            "facebook": False,
            "facebook_status": "missing",
            "facebook_expires_at": None,
            "facebook_page_name": "",
            "instagram_connected": False,
            "ai": False,
            "ai_source": "not_configured",
            "pexels": False,
        },
        "cooldown": {"active": False, "until": None, "reason": "Unavailable"},
        "pipeline": {
            "queue_size": 0,
            "next_scheduled_at": None,
            "retry_scheduled_count": 0,
            "failed_count": 0,
            "pending_approvals": 0,
            "drafted_count": 0,
            "last_published_at": None,
            "published_count_7d": 0,
        },
        "last_error": None,
    }


def _load_health_status_payload(user_id: str) -> Dict:
    def builder():
        db = config.get_database_client()
        now = datetime.now(timezone.utc)
        since = (now - timedelta(days=7)).isoformat()

        settings = app_utils.get_user_settings(user_id) or {}
        page_health = app_utils.get_active_page_health(user_id) or {}

        ai_source = "not_configured"
        ai_enabled = False
        if settings.get("ai_api_key") or settings.get("gemini_api_key"):
            ai_enabled = True
            ai_source = "user_settings"
        elif _is_truthy(os.getenv("ALLOW_ENV_AI_FALLBACK")):
            provider = (settings.get("ai_provider") or "gemini").strip().lower() or "gemini"
            env_key = {
                "gemini": os.getenv("GEMINI_API_KEY", ""),
                "claude": os.getenv("ANTHROPIC_API_KEY", ""),
                "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
                "openai": os.getenv("OPENAI_API_KEY", ""),
                "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
            }.get(provider) or os.getenv("GEMINI_API_KEY", "")
            if env_key:
                ai_enabled = True
                ai_source = "env_fallback"

        latest_error_row = (
            db.table("processed_content")
            .select("status, last_error, last_error_at, retry_count, next_retry_at")
            .eq("user_id", user_id)
            .order("last_error_at", desc=True)
            .limit(1)
            .execute()
        ).data
        latest_error_row = latest_error_row[0] if latest_error_row else None

        retry_scheduled = (
            db.table("processed_content")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "retry_scheduled")
            .execute()
        )
        failed = (
            db.table("processed_content")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "failed")
            .execute()
        )
        waiting_approval = (
            db.table("processed_content")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "waiting_approval")
            .execute()
        )
        drafted = (
            db.table("processed_content")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "drafted")
            .execute()
        )

        next_scheduled_rows = (
            db.table("scheduled_posts")
            .select("scheduled_time")
            .eq("user_id", user_id)
            .eq("status", "scheduled")
            .order("scheduled_time")
            .limit(1)
            .execute()
        ).data or []
        queue_size = (
            db.table("scheduled_posts")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("status", "scheduled")
            .execute()
        )

        latest_published_rows = (
            db.table("published_posts")
            .select("published_at")
            .eq("user_id", user_id)
            .order("published_at", desc=True)
            .limit(1)
            .execute()
        ).data or []
        published_7d = (
            db.table("published_posts")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("published_at", since)
            .execute()
        )

        retry_until = _parse_timestamp((latest_error_row or {}).get("next_retry_at"))
        latest_error_status = str((latest_error_row or {}).get("status") or "").strip().lower()
        cooldown_active = bool(
            latest_error_status == "retry_scheduled"
            and retry_until
            and retry_until > now
        )

        last_error = None
        if latest_error_row and latest_error_row.get("last_error"):
            status = str(latest_error_row.get("status") or "").strip().lower()
            message = str(latest_error_row.get("last_error") or "").strip()
            if status == "retry_scheduled":
                message = f"{message} \u2014 retry queued"
            last_error = {
                "status": status or "failed",
                "code": latest_error_row.get("last_error"),
                "message": message,
                "at": latest_error_row.get("last_error_at"),
                "retry_count": latest_error_row.get("retry_count") or 0,
                "next_retry_at": latest_error_row.get("next_retry_at"),
            }

        tokens = {
            "facebook": bool(page_health.get("connected")),
            "facebook_status": page_health.get("token_status") or ("healthy" if page_health.get("connected") else "missing"),
            "facebook_expires_at": page_health.get("token_expires_at"),
            "facebook_page_name": page_health.get("page_name") or "",
            "instagram_connected": bool(page_health.get("instagram_connected")),
            "ai": ai_enabled,
            "ai_source": ai_source,
            "pexels": bool(settings.get("pexels_api_key") or os.getenv("PEXELS_API_KEY")),
        }

        return {
            "ai_source": ai_source,
            "page": {
                "connected": bool(page_health.get("connected")),
                "page_id": page_health.get("page_id") or "",
                "page_name": page_health.get("page_name") or "",
                "status": page_health.get("status") or "missing",
            },
            "tokens": tokens,
            "cooldown": {
                "active": cooldown_active,
                "until": retry_until.isoformat() if retry_until else None,
                "reason": "Retry cooldown active" if cooldown_active else "Ready",
            },
            "pipeline": {
                "queue_size": _safe_count(queue_size),
                "next_scheduled_at": next_scheduled_rows[0].get("scheduled_time") if next_scheduled_rows else None,
                "retry_scheduled_count": _safe_count(retry_scheduled),
                "failed_count": _safe_count(failed),
                "pending_approvals": _safe_count(waiting_approval),
                "drafted_count": _safe_count(drafted),
                "last_published_at": latest_published_rows[0].get("published_at") if latest_published_rows else None,
                "published_count_7d": _safe_count(published_7d),
            },
            "last_error": last_error,
        }

    return _request_cache_value(f"_health_status::{user_id}", builder)


def _build_health_events(page_health: Dict, recent_rows: Dict) -> list[Dict]:
    events = []

    def push(event_type: str, message: str, at=None):
        events.append({
            "type": event_type,
            "message": message,
            "at": at,
            "_sort": _parse_timestamp(at) or datetime.min.replace(tzinfo=timezone.utc),
        })

    for row in recent_rows.get("published", []) or []:
        push("publish", f"Content published to {_format_platforms(row.get('platforms'))}", row.get("published_at"))

    for row in recent_rows.get("scheduled", []) or []:
        push(
            "schedule",
            f"Content scheduled for {_format_platforms(row.get('platforms'))}",
            row.get("created_at") or row.get("scheduled_time"),
        )

    for row in recent_rows.get("drafted", []) or []:
        push("generate", "New draft generated", row.get("generated_at") or row.get("created_at"))

    for row in recent_rows.get("approval", []) or []:
        push("approval", "Content sent for approval", row.get("approval_requested_at") or row.get("created_at"))

    for row in recent_rows.get("errors", []) or []:
        status = str(row.get("status") or "").strip().lower()
        if status == "retry_scheduled":
            message = "Publishing failed Ã¢â‚¬â€ retry scheduled"
        else:
            message = row.get("last_error") or "Publishing failed"
        push("error", message, row.get("last_error_at") or row.get("next_retry_at"))

    token_status = str(page_health.get("token_status") or "").strip().lower()
    if token_status == "expiring":
        push("token", "Facebook token expires soon", page_health.get("token_expires_at"))
    elif token_status == "expired":
        push("token", "Facebook token has expired", page_health.get("token_expires_at"))

    events.sort(key=lambda item: item["_sort"], reverse=True)
    for item in events:
        item.pop("_sort", None)
    return events


def _load_health_events_payload(user_id: str) -> list[Dict]:
    def builder():
        db = config.get_database_client()
        recent_rows = {
            "published": (
                db.table("published_posts")
                .select("published_at, platforms")
                .eq("user_id", user_id)
                .order("published_at", desc=True)
                .limit(10)
                .execute()
            ).data or [],
            "scheduled": (
                db.table("scheduled_posts")
                .select("created_at, scheduled_time, status, platforms")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            ).data or [],
            "drafted": (
                db.table("processed_content")
                .select("generated_at, created_at")
                .eq("user_id", user_id)
                .order("generated_at", desc=True)
                .limit(10)
                .execute()
            ).data or [],
            "approval": (
                db.table("processed_content")
                .select("approval_requested_at, created_at")
                .eq("user_id", user_id)
                .order("approval_requested_at", desc=True)
                .limit(10)
                .execute()
            ).data or [],
            "errors": (
                db.table("processed_content")
                .select("status, last_error, last_error_at, next_retry_at")
                .eq("user_id", user_id)
                .order("last_error_at", desc=True)
                .limit(10)
                .execute()
            ).data or [],
        }
        page_health = app_utils.get_active_page_health(user_id) or {}
        return _build_health_events(page_health=page_health, recent_rows=recent_rows)

    return _request_cache_value(f"_health_events::{user_id}", builder)


def _load_runtime_status_payload(user_id: str) -> Dict:
    def builder():
        db = config.get_database_client()
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        settings = app_utils.get_user_settings(user_id) or {}
        health_payload = _load_health_status_payload(user_id)

        daily_limit = int(settings.get("posts_per_day") or 3)
        published_today = (
            db.table("published_posts")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("published_at", today_start)
            .execute()
        )
        posts_today = _safe_count(published_today)

        page_connected = bool(health_payload.get("page", {}).get("connected"))
        ai_ready = bool((health_payload.get("tokens") or {}).get("ai"))
        cooldown_active = bool((health_payload.get("cooldown") or {}).get("active"))
        facebook_status = str((health_payload.get("tokens") or {}).get("facebook_status") or "missing").strip().lower()
        remaining = max(daily_limit - posts_today, 0)

        if not page_connected:
            can_post = False
            reason = "Connect a Facebook page to publish content."
        elif not ai_ready:
            can_post = False
            reason = "Add an AI key in Settings to generate publishable content."
        elif facebook_status == "expired":
            can_post = False
            reason = "Reconnect Facebook because the page token has expired."
        elif cooldown_active:
            can_post = False
            reason = health_payload.get("cooldown", {}).get("reason") or "Retry cooldown active."
        elif posts_today >= daily_limit:
            can_post = False
            reason = "Today's posting limit has been reached."
        else:
            can_post = True
            reason = "Publishing allowed right now."

        if facebook_status == "expired":
            ban_status = "expired"
            ban_reason = "Facebook token expired."
            severity = 3
        elif facebook_status == "expiring":
            ban_status = "watch"
            ban_reason = "Facebook token expires soon."
            severity = 1
        else:
            ban_status = "ok"
            ban_reason = "No account-level blocker detected."
            severity = 0

        return {
            "success": True,
            "timestamp": now.isoformat(),
            "can_post": can_post,
            "post_reason": reason,
            "rate_limiter": {
                "can_post": can_post,
                "posts_today": posts_today,
                "daily_limit": daily_limit,
                "remaining": remaining,
            },
            "ban_detector": {
                "status": ban_status,
                "reason": ban_reason,
                "severity": severity,
            },
            "health": "healthy" if can_post and ban_status == "ok" else "degraded",
        }

    return _request_cache_value(f"_runtime_status::{user_id}", builder)


def _load_setup_progress_payload(user_id: str) -> Dict:
    def builder():
        db = config.get_database_client()
        settings = app_utils.get_user_settings(user_id) or {}
        pages = app_utils.get_managed_pages_for_user(user_id, normalize_active=True)

        telegram_rows = (
            db.table("telegram_connections")
            .select("id, is_active")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .execute()
        ).data or []

        has_facebook = any(str(row.get("status") or "").lower() == "active" for row in pages)
        has_ai_key = bool(settings.get("ai_api_key") or settings.get("gemini_api_key"))
        has_telegram = bool(telegram_rows)

        steps = [
            {
                "id": "facebook",
                "label": "Connect Facebook page",
                "description": "Required to publish content",
                "action_label": "Connect Facebook",
                "action_url": "/oauth/facebook",
                "completed": has_facebook,
                "optional": False,
            },
            {
                "id": "ai_key",
                "label": "Add your AI API key",
                "description": "Required to generate content",
                "action_label": "Add key",
                "action_url": "/settings#ai",
                "completed": has_ai_key,
                "optional": False,
            },
            {
                "id": "telegram",
                "label": "Connect Telegram",
                "description": "Optional for approvals and summaries",
                "action_label": "Connect Telegram",
                "action_url": "/channels#telegram",
                "completed": has_telegram,
                "optional": True,
            },
        ]

        next_required_step = next(
            (step["id"] for step in steps if not step["optional"] and not step["completed"]),
            None,
        )
        return {
            "steps": steps,
            "all_required_complete": has_facebook and has_ai_key,
            "next_required_step": next_required_step,
        }

    return _request_cache_value(f"_setup_progress::{user_id}", builder)


def _normalize_bootstrap_page(raw_page: str) -> str:
    normalized = str(raw_page or "").strip().lower()
    return normalized if normalized in {"dashboard", "channels", "settings", "diagnostics", "studio"} else ""


def _json_from_route(result) -> Dict:
    if isinstance(result, tuple):
        response = result[0]
    else:
        response = result
    return response.get_json() if hasattr(response, "get_json") else {}


def _build_bootstrap_payload(user_id: str, page: str) -> Dict:
    from app.pages.routes import load_pages_payload
    from app.settings.routes import _load_settings_bootstrap_payload
    from app.studio.routes import (
        _load_dashboard_summary_payload,
        _load_studio_bootstrap_payload,
    )

    refresh_requested = _is_truthy(request.args.get("refresh"))
    cache_key = (user_id, page)
    request_cache_key = f"bootstrap::{user_id}::{page}::{int(refresh_requested)}"
    cached = getattr(g, request_cache_key, None)
    if cached is not None:
        return cached

    warm_payload = None if refresh_requested else _bootstrap_cache_get(cache_key)
    if warm_payload is not None:
        setattr(g, request_cache_key, warm_payload)
        return warm_payload

    errors: list[Dict[str, str]] = []
    stale_payload = _bootstrap_cache_get(cache_key, allow_stale=True)

    shell_payload = {
        "setup": _safe_bootstrap_value(
            "shell.setup",
            lambda: _load_setup_progress_payload(user_id),
            {"steps": [], "all_required_complete": False, "next_required_step": "facebook"},
            errors,
        ),
        "status": _safe_bootstrap_value(
            "shell.status",
            lambda: _load_runtime_status_payload(user_id),
            {
                "success": False,
                "can_post": False,
                "post_reason": "Dashboard status is temporarily unavailable.",
                "rate_limiter": {"can_post": False, "posts_today": 0, "daily_limit": 0, "remaining": 0},
                "ban_detector": {"status": "unknown", "reason": "Unavailable", "severity": 0},
                "health": "degraded",
            },
            errors,
        ),
    }
    payload: Dict[str, Any] = {"shell": shell_payload, "page": page}

    if page == "dashboard":
        payload["dashboard"] = {
            "summary": _safe_bootstrap_value(
                "dashboard.summary",
                lambda: _load_dashboard_summary_payload(user_id),
                {"pending": [], "scheduled": [], "published": [], "ready_count": 0},
                errors,
            ),
            "health": _safe_bootstrap_value(
                "dashboard.health",
                lambda: _load_health_status_payload(user_id),
                _default_health_payload(),
                errors,
            ),
            "events": [],
            "pages": _safe_bootstrap_value(
                "dashboard.pages",
                lambda: load_pages_payload(user_id),
                {"success": False, "pages": []},
                errors,
            ),
        }
    elif page == "channels":
        payload["channels"] = {
            "pages": _safe_bootstrap_value(
                "channels.pages",
                lambda: load_pages_payload(user_id),
                {"success": False, "pages": []},
                errors,
            ),
            "facebook": _safe_bootstrap_value(
                "channels.facebook",
                lambda: _json_from_route(get_facebook_status()),
                {"connected": False, "reason": "Unavailable"},
                errors,
            ),
            "instagram": _safe_bootstrap_value(
                "channels.instagram",
                lambda: _json_from_route(get_instagram_status()),
                {"connected": False, "reason": "Unavailable"},
                errors,
            ),
            "telegram_code": _safe_bootstrap_value(
                "channels.telegram_code",
                lambda: _json_from_route(telegram_get_code()),
                {"connected": False, "code": "", "deep_link": ""},
                errors,
            ),
            "telegram_status": _safe_bootstrap_value(
                "channels.telegram_status",
                lambda: _json_from_route(telegram_status()),
                {"connected": False},
                errors,
            ),
            "telegram_summary": _safe_bootstrap_value(
                "channels.telegram_summary",
                lambda: _json_from_route(telegram_summary_settings_get()),
                {"enabled": False, "daily_summary_time": "08:00"},
                errors,
            ),
        }
    elif page == "settings":
        payload["settings"] = _safe_bootstrap_value(
            "settings",
            lambda: _load_settings_bootstrap_payload(user_id),
            {},
            errors,
        )
    elif page == "diagnostics":
        payload["diagnostics"] = {
            "health": _safe_bootstrap_value(
                "diagnostics.health",
                lambda: _load_health_status_payload(user_id),
                _default_health_payload(),
                errors,
            ),
            "events": _safe_bootstrap_value(
                "diagnostics.events",
                lambda: _load_health_events_payload(user_id),
                [],
                errors,
            ),
        }
    elif page == "studio":
        payload["studio"] = {
            **_safe_bootstrap_value(
                "studio",
                lambda: _load_studio_bootstrap_payload(user_id),
                {
                    "profile": {},
                    "page_context": {},
                    "drafts": [],
                    "pending": [],
                    "scheduled": [],
                    "published": [],
                    "presets": {"niches": []},
                },
                errors,
            ),
            "status": _safe_bootstrap_value(
                "studio.status",
                lambda: _load_runtime_status_payload(user_id),
                {
                    "success": False,
                    "can_post": False,
                    "post_reason": "Studio status is temporarily unavailable.",
                    "rate_limiter": {"can_post": False, "posts_today": 0, "daily_limit": 0, "remaining": 0},
                    "ban_detector": {"status": "unknown", "reason": "Unavailable", "severity": 0},
                    "health": "degraded",
                },
                errors,
            ),
            "pages": _safe_bootstrap_value(
                "studio.pages",
                lambda: load_pages_payload(user_id),
                {"success": False, "pages": []},
                errors,
            ),
        }

    if errors and stale_payload is not None:
        stale_payload["_bootstrap"] = {"stale": True, "errors": errors}
        setattr(g, request_cache_key, stale_payload)
        return stale_payload

    payload["_bootstrap"] = {"stale": False, "errors": errors}
    if not errors:
        _bootstrap_cache_set(cache_key, payload)
    setattr(g, request_cache_key, payload)
    return payload


def _run_facebook_service_test(user_id: str) -> Dict:
    page_health = app_utils.get_active_page_health(user_id) or {}
    if not page_health.get("connected"):
        return {"success": False, "service": "facebook", "message": "No active Facebook page connected."}

    tokens = app_utils.load_tokens_for_user(user_id) or {}
    page_id = page_health.get("page_id") or tokens.get("page_id")
    page_token = tokens.get("page_token") or ""
    if not page_id or not page_token:
        return {"success": False, "service": "facebook", "message": "No usable Facebook page token was found."}

    response = requests.get(
        f"https://graph.facebook.com/{page_id}",
        params={"fields": "id,name", "access_token": page_token},
        timeout=8,
    )
    if response.status_code == 200:
        payload = response.json()
        return {
            "success": True,
            "service": "facebook",
            "message": "Facebook page is connected.",
            "details": {
                "page_id": payload.get("id") or page_id,
                "page_name": payload.get("name") or page_health.get("page_name") or "",
            },
        }
    return {"success": False, "service": "facebook", "message": response.text or "Facebook connection test failed."}


def _run_ai_service_test(user_id: str) -> Dict:
    from user_config import get_user_config

    runtime_profile = get_user_config(user_id)
    key = getattr(runtime_profile, "ai_api_key", "") or getattr(runtime_profile, "gemini_api_key", "")
    if not key:
        return {"success": False, "service": "ai", "message": "No AI provider key is configured for this account."}
    return {
        "success": True,
        "service": "ai",
        "message": "AI provider key is configured.",
        "details": {
            "provider": getattr(runtime_profile, "ai_provider", "gemini"),
            "model": getattr(runtime_profile, "ai_model", ""),
        },
    }


def _run_pexels_service_test(user_id: str) -> Dict:
    settings = app_utils.get_user_settings(user_id) or {}
    pexels_key = settings.get("pexels_api_key") or os.getenv("PEXELS_API_KEY", "")
    source = "user_settings" if settings.get("pexels_api_key") else "env"
    if not pexels_key:
        return {"success": False, "service": "pexels", "message": "No Pexels key is configured for this account."}

    response = requests.get(
        "https://api.pexels.com/v1/search",
        params={"query": "business", "per_page": 1},
        headers={"Authorization": pexels_key},
        timeout=8,
    )
    if response.status_code == 200:
        return {
            "success": True,
            "service": "pexels",
            "message": "Pexels connection succeeded.",
            "details": {"source": source},
        }
    return {"success": False, "service": "pexels", "message": response.text or "Pexels connection test failed."}


def _run_health_service_test(service: str, user_id: str) -> Dict:
    normalized = str(service or "").strip().lower()
    if normalized == "facebook":
        return _run_facebook_service_test(user_id)
    if normalized == "ai":
        return _run_ai_service_test(user_id)
    if normalized == "pexels":
        return _run_pexels_service_test(user_id)
    if normalized == "database":
        (
            config.get_database_client()
            .table("managed_pages")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return {"success": True, "service": "database", "message": "Database connection succeeded."}
    return {"success": False, "service": normalized or "unknown", "message": "Unknown service requested."}


# ============================================================
# Analytics & Insights
# ============================================================

@api_bp.route("/api/analytics/overview", methods=["GET"])
@api_login_required
def get_analytics_overview():
    try:
        client = config.get_supabase_client()
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        result = (
            client.table("published_posts")
            .select("likes, shares, comments, reach, published_at")
            .eq("user_id", current_user.id)
            .gte("published_at", since)
            .execute()
        )
        posts = result.data or []
        total_posts = len(posts)
        total_likes = sum(p.get("likes", 0) or 0 for p in posts)
        total_shares = sum(p.get("shares", 0) or 0 for p in posts)
        total_comments = sum(p.get("comments", 0) or 0 for p in posts)
        total_reach = sum(p.get("reach", 0) or 0 for p in posts)
        return _api_success(
            overview={
                "total_posts": total_posts,
                "total_likes": total_likes,
                "total_shares": total_shares,
                "total_comments": total_comments,
                "total_reach": total_reach,
                "avg_engagement": round(
                    (total_likes + total_shares + total_comments) / max(total_posts, 1), 1
                ),
            },
            period="7d",
        )
    except Exception as e:
        logger.error("Error fetching analytics: %s", e)
        return _api_error(str(e), 500)


@api_bp.route("/api/analytics/daily", methods=["GET"])
@api_login_required
def get_daily_analytics():
    try:
        client = config.get_supabase_client()
        days = int(request.args.get("days", 7))
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            client.table("published_posts")
            .select("published_at, likes, shares, comments, reach")
            .eq("user_id", current_user.id)
            .gte("published_at", since)
            .execute()
        )
        daily_data: Dict = {}
        for post in result.data or []:
            date = post["published_at"][:10]
            if date not in daily_data:
                daily_data[date] = {"posts": 0, "likes": 0, "shares": 0, "comments": 0, "reach": 0}
            daily_data[date]["posts"] += 1
            daily_data[date]["likes"] += post.get("likes", 0) or 0
            daily_data[date]["shares"] += post.get("shares", 0) or 0
            daily_data[date]["comments"] += post.get("comments", 0) or 0
            daily_data[date]["reach"] += post.get("reach", 0) or 0
        return _api_success(daily=[{"date": k, **v} for k, v in sorted(daily_data.items())])
    except Exception as e:
        logger.error("Error fetching daily analytics: %s", e)
        return _api_error(str(e), 500)


# ============================================================
# System Status
# ============================================================

@api_bp.route("/api/setup/progress", methods=["GET"])
@api_login_required
def get_setup_progress():
    try:
        return _api_success(**_load_setup_progress_payload(current_user.id))
    except Exception as exc:
        logger.error("Error loading setup progress: %s", exc)
        return _api_error(
            str(exc),
            500,
            steps=[],
            all_required_complete=False,
            next_required_step="facebook",
        )


@api_bp.route("/api/bootstrap", methods=["GET"])
@api_login_required
def get_bootstrap():
    try:
        page = _normalize_bootstrap_page(request.args.get("page", ""))
        return jsonify({"success": True, **_build_bootstrap_payload(current_user.id, page)})
    except Exception as exc:
        logger.error("Error loading bootstrap payload: %s", exc)
        return _api_error(str(exc), 500, page=_normalize_bootstrap_page(request.args.get("page", "")))

@api_bp.route("/api/status", methods=["GET"])
@api_login_required
def get_system_status():
    try:
        return jsonify(_load_runtime_status_payload(current_user.id))
    except Exception as e:
        logger.error("Error fetching status: %s", e)
        return _api_error(str(e), 500, health="error")


# ============================================================
# Health & Diagnostics
# ============================================================

@api_bp.route("/api/health/status", methods=["GET"])
@api_login_required
def get_health_detailed():
    try:
        payload = _load_health_status_payload(current_user.id)
        return _api_success(**payload)
    except Exception as e:
        return _api_error(str(e), 500)


@api_bp.route("/api/health/events", methods=["GET"])
@api_login_required
def get_health_events():
    try:
        return _api_success(events=_load_health_events_payload(current_user.id))
    except Exception as exc:
        return _api_error(str(exc), 500, events=[])


@api_bp.route("/api/health/test/<service>", methods=["GET"])
@api_login_required
def run_service_test(service: str):
    try:
        payload = _run_health_service_test(service, current_user.id)
        status = 200 if payload.get("success") else 400
        return jsonify({**payload, "success": bool(payload.get("success"))}), status
    except Exception as exc:
        return _api_error(str(exc), 500, service=service, message=str(exc))




# ============================================================
# Facebook & Instagram
# ============================================================

@api_bp.route("/api/facebook/status", methods=["GET"])
@api_login_required
def get_facebook_status():
    """Return connection status for the current user's Facebook page (DB-scoped)."""
    try:
        from app.utils import decrypt_value, get_active_managed_page_for_user

        page = get_active_managed_page_for_user(
            current_user.id,
            include_token=bool(request.args.get("test")),
        )
        if not page:
            return jsonify({"connected": False, "reason": "No Facebook page connected"})
        status_payload = {
            "connected": True,
            "page_id": page["page_id"],
            "page_name": page.get("page_name", ""),
            "status": page.get("status", "active"),
        }
        if request.args.get("test"):
            try:
                raw_token = decrypt_value(page["access_token"]) if page.get("access_token") else ""
                import requests as _req
                resp = _req.get(
                    f"https://graph.facebook.com/{page['page_id']}",
                    params={"access_token": raw_token, "fields": "id,name"},
                    timeout=8,
                )
                status_payload["test"] = {"ok": resp.status_code == 200}
            except Exception as exc:
                status_payload["test"] = {"ok": False, "error": str(exc)}
        return jsonify(status_payload)
    except Exception as e:
        logger.error("Facebook status error: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/facebook/disconnect", methods=["POST"])
@api_login_required
def disconnect_facebook():
    """Mark all of the current user's Facebook pages as inactive in the DB."""
    try:
        config.get_database_client().table("managed_pages").update({"status": "inactive"}).eq(
            "user_id", current_user.id
        ).execute()
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Disconnect error: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/instagram/status", methods=["GET"])
@api_login_required
def get_instagram_status():
    """Return Instagram connection status for the current user (DB-scoped)."""
    try:
        from app.utils import decrypt_value, get_active_managed_page_for_user

        page = get_active_managed_page_for_user(current_user.id, include_token=True)
        if not page:
            return jsonify({"connected": False, "reason": "No Facebook page connected"})
        stored_ig_id = page.get("instagram_account_id") or ""
        if stored_ig_id:
            return jsonify({
                "connected": True,
                "instagram_account_id": stored_ig_id,
                "facebook_page_id": page["page_id"],
            })
        # No IG account stored Ã¢â‚¬â€ try live lookup
        try:
            raw_token = decrypt_value(page["access_token"]) if page.get("access_token") else ""
            from facebook_oauth import get_instagram_account_for_page
            ig_info = get_instagram_account_for_page(page["page_id"], raw_token)
            if not ig_info:
                return jsonify({
                    "connected": False,
                    "facebook_page_id": page["page_id"],
                    "reason": "No Instagram Business Account linked to this Facebook Page.",
                })
            # Cache the IG account id for future calls
            config.get_database_client().table("managed_pages").update(
                {"instagram_account_id": ig_info["instagram_account_id"]}
            ).eq("user_id", current_user.id).eq("page_id", page["page_id"]).execute()
            return jsonify({
                "connected": True,
                "instagram_account_id": ig_info["instagram_account_id"],
                "username": ig_info.get("username", ""),
                "facebook_page_id": page["page_id"],
            })
        except Exception as exc:
            return jsonify({"connected": False, "reason": str(exc)})
    except Exception as e:
        logger.error("Error checking Instagram status: %s", e)
        return jsonify({"connected": False, "reason": str(e)}), 500


# ============================================================
# AI Test
# ============================================================

@api_bp.route("/api/ai/test", methods=["POST"])
@api_login_required
def test_ai_connection():
    try:
        from gemini_client import test_ai_connection as test_ai
        return jsonify(test_ai())
    except Exception as e:
        logger.error("AI test error: %s", e)
        return jsonify({"error": str(e)}), 500




# ============================================================
# License  (activate is PUBLIC Ã¢â‚¬â€ pre-registration use)
# ============================================================

@api_bp.route("/api/license/activate", methods=["POST"])
def activate_license():
    """Validate a Gumroad license key. Intentionally public Ã¢â‚¬â€ called before login."""
    try:
        payload, status = _validate_license_request(request.get_json(force=True))
        return jsonify(payload), status
    except ImportError:
        return jsonify({"valid": False, "reason": "License module not available"}), 500
    except Exception as e:
        return jsonify({"valid": False, "reason": str(e)}), 500


@api_bp.route("/api/license/status", methods=["GET"])
@api_login_required
def license_status():
    try:
        from license_validator import is_licensed, get_license_info
        info = get_license_info() or {}
        return jsonify({"licensed": is_licensed(), "email": info.get("email", ""), "uses": info.get("uses", 0)})
    except ImportError:
        return jsonify({"licensed": False, "reason": "License module not available"})


# Ã¢â€â‚¬Ã¢â€â‚¬ Telegram API endpoints Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@api_bp.route("/api/telegram/code", methods=["GET"])
@api_login_required
def telegram_get_code():
    """
    Return the user's Telegram unique activation code and deep-link.

    Creates a new code if one doesn't exist yet.
    Called by the onboarding wizard Telegram step to display the code.
    """
    try:
        from tasks.telegram_bot import get_or_create_unique_code, is_telegram_connected
        import os
        code = get_or_create_unique_code(current_user.id)
        bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "ContentFactoryBot")
        deep_link = f"https://t.me/{bot_username}?start={code}"
        connected = is_telegram_connected(current_user.id)
        return jsonify({
            "success": True,
            "ok": True,
            "code": code,
            "deep_link": deep_link,
            "bot_username": bot_username,
            "connected": connected,
        })
    except Exception as exc:
        logger.error("telegram_get_code error: %s", exc)
        return jsonify({"success": False, "ok": False, "error": str(exc)}), 500


@api_bp.route("/api/telegram/status", methods=["GET"])
@api_login_required
def telegram_status():
    """
    Poll endpoint for the onboarding wizard Telegram step.

    Returns { connected: true/false } Ã¢â‚¬â€ the wizard polls every 5s and
    auto-advances when connected=true.
    """
    try:
        from tasks.telegram_bot import is_telegram_connected
        connected = is_telegram_connected(current_user.id)
        return jsonify({"success": True, "connected": connected})
    except Exception as exc:
        logger.warning("telegram_status error: %s", exc)
        return jsonify({"success": False, "connected": False, "error": str(exc)})


@api_bp.route("/api/telegram/pause", methods=["POST"])
@api_login_required
def telegram_pause():
    """Pause automation for the current user (dashboard action)."""
    try:
        from tasks.telegram_bot import set_automation_paused
        data = request.get_json(silent=True) or {}
        paused = bool(data.get("paused", True))
        set_automation_paused(current_user.id, paused)
        return jsonify({"success": True, "ok": True, "paused": paused})
    except Exception as exc:
        return jsonify({"success": False, "ok": False, "error": str(exc)}), 500


@api_bp.route("/api/telegram/summary-settings", methods=["GET"])
@api_login_required
def telegram_summary_settings_get():
    """Return the user's daily summary time setting."""
    try:
        from app.utils import _get_supabase_client
        sb = _get_supabase_client()
        res = (
            sb.table("user_settings")
            .select("daily_summary_time")
            .eq("user_id", current_user.id)
            .limit(1)
            .execute()
        )
        daily_summary_time = None
        enabled = False
        if res.data:
            stored = str(res.data[0].get("daily_summary_time") or "").strip()
            if stored:
                daily_summary_time = stored[:5]
                enabled = True
        return jsonify(
            {
                "success": True,
                "ok": True,
                "enabled": enabled,
                "daily_summary_time": daily_summary_time or "08:00",
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "ok": False, "error": str(exc)}), 500


@api_bp.route("/api/telegram/summary-settings", methods=["POST"])
@api_login_required
def telegram_summary_settings_set():
    """
    Update the user's daily summary time.

    Body:
      { "enabled": true|false, "daily_summary_time": "HH:MM" }
    Backward compatible with time-only callers.
    """
    try:
        data = request.get_json(silent=True) or {}
        enabled = data.get("enabled", None)
        daily_summary_time = str(data.get("daily_summary_time") or "08:00").strip()[:5]
        # Validate HH:MM format
        parts = daily_summary_time.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            return jsonify({"ok": False, "error": "Invalid time format Ã¢â‚¬â€ use HH:MM"}), 400
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return jsonify({"ok": False, "error": "Time out of range"}), 400

        from app.utils import _get_supabase_client
        sb = _get_supabase_client()
        final_value = None if enabled is False else f"{h:02d}:{m:02d}"
        sb.table("user_settings").upsert({
            "user_id": current_user.id,
            "daily_summary_time": final_value,
        }).execute()
        return jsonify(
            {
                "success": True,
                "ok": True,
                "enabled": final_value is not None,
                "daily_summary_time": final_value or "08:00",
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "ok": False, "error": str(exc)}), 500
