"""Shared utilities for the Content Factory app."""

import logging
import re
import os
import secrets as _secrets
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from flask import jsonify, request
from flask_login import current_user

import config


def disabled_in_v1(feature: str):
    """Return a standard SaaS V1 disabled-feature response."""
    return (
        jsonify(
            {
                "success": False,
                "ready": False,
                "enabled": False,
                "feature": feature,
                "error": f"{feature} is disabled in SaaS V1.",
                "code": "disabled_in_v1",
            }
        ),
        410,
    )


def api_login_required(f):
    """
    Auth guard for JSON API routes — the API-endpoint equivalent of Flask-Login's
    @login_required decorator.

    Flask-Login's built-in @login_required redirects unauthenticated requests to the
    login page (HTML redirect), which is appropriate for browser page routes but wrong
    for JSON API consumers who expect a 401 status code and a JSON error body.

    This decorator checks current_user.is_authenticated (the same Flask-Login session
    check used by @login_required) and returns {"error": "..."} / 401 instead of a
    redirect, preserving correct API semantics while sharing the same auth backend.

    SaaS V1 assumes authenticated JSON requests originate from the same-origin web UI
    over HTTPS with browser session cookies. The frontend sends
    `X-Requested-With: XMLHttpRequest`, and this decorator rejects explicit
    cross-origin Origin/Referer mismatches for mutating requests.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            requested_with = str(request.headers.get("X-Requested-With") or "").strip()
            if requested_with and requested_with != "XMLHttpRequest":
                return jsonify(
                    {
                        "success": False,
                        "error": "Same-origin browser request required",
                        "code": "csrf_origin_mismatch",
                    }
                ), 403

            host_origin = urlparse(request.host_url)
            trusted_netloc = host_origin.netloc
            trusted_scheme = host_origin.scheme

            def _is_same_origin(candidate: str) -> bool:
                try:
                    parsed = urlparse(candidate)
                except Exception:
                    return False
                return parsed.scheme == trusted_scheme and parsed.netloc == trusted_netloc

            origin = str(request.headers.get("Origin") or "").strip()
            referer = str(request.headers.get("Referer") or "").strip()
            if origin and not _is_same_origin(origin):
                return jsonify(
                    {
                        "success": False,
                        "error": "Cross-origin authenticated API writes are not allowed",
                        "code": "csrf_origin_mismatch",
                    }
                ), 403
            if referer and not _is_same_origin(referer):
                return jsonify(
                    {
                        "success": False,
                        "error": "Cross-origin authenticated API writes are not allowed",
                        "code": "csrf_origin_mismatch",
                    }
                ), 403
        return f(*args, **kwargs)
    return decorated


def _get_or_create_secret_key() -> str:
    """Auto-generate and persist a Flask secret key on first run."""
    env_key = os.getenv("FLASK_SECRET_KEY", "")
    if env_key:
        return env_key
    secret_file = Path(__file__).parent.parent / ".flask_secret"
    if secret_file.exists():
        return secret_file.read_text().strip()
    new_key = _secrets.token_hex(32)
    try:
        secret_file.write_text(new_key)
    except OSError:
        pass
    return new_key


def _read_env_file() -> Tuple[Path, Dict[str, str]]:
    env_path = Path(__file__).parent.parent / ".env"
    existing: Dict[str, str] = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    existing[key] = val
    return env_path, existing


def _write_env_file(env_path: Path, data: Dict[str, str]) -> None:
    with open(env_path, "w", encoding="utf-8") as f:
        for key, val in data.items():
            f.write(f"{key}={val}\n")


# ── Fernet encryption helpers ───────────────────────────────────────────────

def get_fernet_key() -> bytes:
    """
    Return a 32-byte Fernet key.

    Resolution order:
    1. FERNET_KEY environment variable (production / Replit secret)
    2. .fernet_key file in the project root (dev fallback — auto-generated)
    """
    env_key = os.getenv("FERNET_KEY", "").strip()
    if env_key:
        return env_key.encode()

    key_file = Path(__file__).parent.parent / ".fernet_key"
    if key_file.exists():
        return key_file.read_bytes().strip()

    from cryptography.fernet import Fernet
    new_key = Fernet.generate_key()
    try:
        key_file.write_bytes(new_key)
    except OSError:
        pass
    return new_key


def encrypt_value(plaintext: str) -> str:
    """Fernet-encrypt a string and return a URL-safe base64 token."""
    from cryptography.fernet import Fernet
    f = Fernet(get_fernet_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """Fernet-decrypt a token previously produced by encrypt_value()."""
    from cryptography.fernet import Fernet
    f = Fernet(get_fernet_key())
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


# ── Supabase client helper ──────────────────────────────────────────────────

def _get_supabase_client():
    """Return a cached Supabase service-role client (bypasses RLS).

    Delegates to config.get_supabase_service_client() which maintains
    a process-level singleton so the client is created only once.
    """
    return config.get_supabase_service_client()


# ── user_settings helpers ───────────────────────────────────────────────────

def _normalize_language_code(value: Optional[str]) -> Optional[str]:
    candidate = (value or "").strip().lower()
    if candidate in config.SUPPORTED_LANGUAGE_CODES:
        return candidate
    return None


def _normalize_language_list(raw_value) -> list[str]:
    if isinstance(raw_value, list):
        tokens = raw_value
    else:
        tokens = str(raw_value or "").split(",")

    normalized: list[str] = []
    for token in tokens:
        code = _normalize_language_code(str(token))
        if code and code not in normalized:
            normalized.append(code)
    return normalized


def _parse_csv_strings(raw_value) -> list[str]:
    if isinstance(raw_value, list):
        tokens = raw_value
    else:
        tokens = str(raw_value or "").split(",")
    return [str(token).strip() for token in tokens if str(token).strip()]


def build_locale_niche_preset_updates(
    country_code: str,
    niche_preset: Optional[str] = None,
) -> Dict:
    """
    Build a normalized user_settings payload from the configured locale/niche presets.
    """
    normalized_country = str(country_code or config.DEFAULT_COUNTRY_CODE).strip().upper()
    locale_preset = config.TARGET_POSTING_PRESETS.get(
        normalized_country,
        config.TARGET_POSTING_PRESETS[config.DEFAULT_COUNTRY_CODE],
    )
    source_preset = config.CONTENT_SOURCE_PRESETS.get(
        normalized_country,
        config.CONTENT_SOURCE_PRESETS[config.DEFAULT_COUNTRY_CODE],
    )

    updates = normalize_user_profile_updates(
        {
            "country_code": normalized_country,
            "timezone": locale_preset["timezone"],
            "content_language": locale_preset["default_content_language"],
            "content_languages": locale_preset["default_content_languages"].split(","),
            "content_tone": locale_preset["default_content_tone"],
        }
    )
    updates["posting_times"] = locale_preset["posting_times"]
    updates["posts_per_day"] = len(
        [token for token in locale_preset["posting_times"].split(",") if token.strip()]
    )
    updates["source_preset"] = source_preset["id"]
    updates["rss_feed_urls"] = ",".join(source_preset["local_rss_feeds"])

    normalized_niche = str(niche_preset or "").strip().lower()
    if normalized_niche and normalized_niche in config.NICHE_KEYWORD_PRESETS:
        niche_config = config.NICHE_KEYWORD_PRESETS[normalized_niche]
        updates["niche_preset"] = niche_config["id"]
        updates["niche_keywords"] = ",".join(niche_config["keywords"])

    return updates


def get_available_presets() -> Dict:
    """Return serializable locale and niche presets for API responses."""
    return {
        "countries": [
            {
                "country_code": country_code,
                "label": config.TARGET_POSTING_PRESETS[country_code]["label"],
                "timezone": config.TARGET_POSTING_PRESETS[country_code]["timezone"],
                "posting_times": config.TARGET_POSTING_PRESETS[country_code]["posting_times"],
                "content_languages": config.TARGET_POSTING_PRESETS[country_code]["default_content_languages"].split(","),
                "content_tone": config.TARGET_POSTING_PRESETS[country_code]["default_content_tone"],
                "rss_feeds": config.CONTENT_SOURCE_PRESETS[country_code]["local_rss_feeds"],
            }
            for country_code in config.TARGET_POSTING_PRESETS
        ],
        "niches": [
            {
                "id": preset_id,
                "label": preset["label"],
                "keywords": preset["keywords"],
            }
            for preset_id, preset in config.NICHE_KEYWORD_PRESETS.items()
        ],
    }


def normalize_user_profile_updates(data: Dict) -> Dict:
    """Normalize locale/profile settings before persisting them to user_settings."""
    updates: Dict = {}

    if "country_code" in data:
        country_code = str(data.get("country_code") or "").strip().upper()
        if country_code in config.TARGET_POSTING_PRESETS:
            updates["country_code"] = country_code
            if "timezone" not in data:
                updates["timezone"] = config.TARGET_POSTING_PRESETS[country_code]["timezone"]

    if "timezone" in data:
        timezone_name = str(data.get("timezone") or "").strip()
        if timezone_name:
            updates["timezone"] = timezone_name

    if "ui_language" in data:
        ui_language = _normalize_language_code(data.get("ui_language"))
        if ui_language:
            updates["ui_language"] = ui_language

    content_language = None
    if "content_language" in data:
        content_language = _normalize_language_code(data.get("content_language"))
        if content_language:
            updates["content_language"] = content_language

    content_languages = None
    if "content_languages" in data:
        normalized_languages = _normalize_language_list(data.get("content_languages"))
        if normalized_languages:
            content_languages = normalized_languages
            updates["content_languages"] = ",".join(normalized_languages)

    if content_language and not content_languages:
        content_languages = [content_language]
        updates["content_languages"] = content_language
    elif content_languages and "content_language" not in updates:
        updates["content_language"] = content_languages[0]

    if "content_dialect" in data:
        content_dialect = str(data.get("content_dialect") or "").strip()
        updates["content_dialect"] = content_dialect[:80] if content_dialect else ""

    if "content_tone" in data:
        content_tone = str(data.get("content_tone") or "").strip().lower()
        if content_tone in config.SUPPORTED_CONTENT_TONES:
            updates["content_tone"] = content_tone

    if "content_mode" in data:
        content_mode = str(data.get("content_mode") or "").strip().lower()
        if content_mode in {"single_language", "mixed"}:
            updates["content_mode"] = content_mode
    elif content_languages:
        updates["content_mode"] = "mixed" if len(content_languages) > 1 else "single_language"

    if "ai_provider" in data:
        ai_provider = str(data.get("ai_provider") or "").strip().lower()
        if ai_provider in config.SUPPORTED_AI_PROVIDERS:
            updates["ai_provider"] = ai_provider

    if "provider_fallback" in data:
        provider_fallback = str(data.get("provider_fallback") or "").strip().lower()
        if provider_fallback in config.SUPPORTED_AI_PROVIDERS:
            updates["provider_fallback"] = provider_fallback
        else:
            updates["provider_fallback"] = None

    if "ai_model" in data:
        updates["ai_model"] = str(data.get("ai_model") or "").strip()

    if "rss_feed_urls" in data:
        feeds = _parse_csv_strings(data.get("rss_feed_urls"))
        updates["rss_feed_urls"] = ",".join(feeds) if feeds else ""

    if "source_preset" in data:
        source_preset = str(data.get("source_preset") or "").strip().upper()
        if source_preset in config.CONTENT_SOURCE_PRESETS:
            updates["source_preset"] = source_preset

    if "niche_preset" in data:
        niche_preset = str(data.get("niche_preset") or "").strip().lower()
        if niche_preset in config.NICHE_KEYWORD_PRESETS:
            updates["niche_preset"] = niche_preset

    if "brand_color" in data:
        brand_color = str(data.get("brand_color") or "").strip()
        if (
            len(brand_color) == 7
            and brand_color.startswith("#")
            and all(ch in "0123456789abcdefABCDEF" for ch in brand_color[1:])
        ):
            updates["brand_color"] = brand_color.upper()

    return updates


def get_user_settings(user_id: str) -> Dict:
    """
    Load the user_settings row for the given user.
    Returns an empty dict if no row exists yet.

    Results are cached in flask.g for the duration of the request,
    so multiple calls within the same request don't hit the DB again.
    """
    # Try per-request cache first (only available inside a Flask request)
    try:
        from flask import g
        cache_key = f"_user_settings_{user_id}"
        cached = getattr(g, cache_key, None)
        if cached is not None:
            return cached
    except RuntimeError:
        # Outside Flask request context (e.g. background tasks)
        cache_key = None

    try:
        sb = _get_supabase_client()
        result = (
            sb.table("user_settings")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        settings = result.data[0] if result.data else {}
    except Exception as exc:
        logging.getLogger("utils").warning(
            "get_user_settings failed for user %s: %s",
            str(user_id)[:8],
            exc,
        )
        settings = {}

    # Store in per-request cache
    if cache_key is not None:
        try:
            from flask import g
            setattr(g, cache_key, settings)
        except RuntimeError:
            pass

    return settings


def seed_session_ui_language(
    user_id: str,
    explicit_language: Optional[str] = None,
) -> str:
    """
    Resolve and cache the user's UI language in the Flask session.

    Falls back to English when the user has no stored preference yet.
    """
    try:
        from flask import session
        from app.i18n import normalize_locale
    except RuntimeError:
        return "EN"

    configured_language = explicit_language
    if configured_language is None:
        configured_language = str((get_user_settings(user_id) or {}).get("ui_language") or "").strip()

    normalized = normalize_locale(str(configured_language or "").strip()) if configured_language else "EN"
    session["ui_language"] = normalized or "EN"
    return session["ui_language"]


def upsert_user_settings(user_id: str, updates: Dict) -> bool:
    """
    Upsert (insert or update) user_settings for the given user.
    Only the keys present in `updates` are written.
    """
    sb = _get_supabase_client()
    payload = {"user_id": user_id, **updates}
    dropped_columns = []

    while True:
        try:
            sb.table("user_settings").upsert(payload, on_conflict="user_id").execute()
            if dropped_columns:
                logging.getLogger("utils").warning(
                    "upsert_user_settings succeeded after dropping unsupported columns: %s",
                    ", ".join(dropped_columns),
                )
            return True
        except Exception as exc:
            message = str(exc)
            match = re.search(r"Could not find the '([^']+)' column", message)
            missing_column = match.group(1) if match else ""
            if missing_column and missing_column in payload and missing_column != "user_id":
                dropped_columns.append(missing_column)
                payload.pop(missing_column, None)
                if len(payload) <= 1:
                    logging.getLogger("utils").error("upsert_user_settings failed: %s", exc)
                    return False
                continue
            logging.getLogger("utils").error("upsert_user_settings failed: %s", exc)
            return False


def require_user_settings_update(user_id: str, updates: Dict) -> None:
    """Persist user settings or raise when the write could not be completed."""
    if not updates:
        return
    if not upsert_user_settings(user_id, updates):
        raise RuntimeError("Could not save user settings")


def _managed_page_created_at(row: Dict[str, Any]) -> datetime:
    created_at = _parse_iso_datetime(str(row.get("created_at") or ""))
    return created_at or datetime.min.replace(tzinfo=timezone.utc)


_MANAGED_PAGES_OPTIONAL_COLUMNS = {"last_synced_at", "token_expires_at"}
_managed_pages_missing_optional_columns: set[str] = set()


def _extract_missing_managed_pages_column(exc: Exception) -> Optional[str]:
    """Return the missing managed_pages column name from a DB error message."""
    match = re.search(r"column managed_pages\.([a-zA-Z0-9_]+) does not exist", str(exc))
    if not match:
        return None
    return str(match.group(1) or "").strip() or None


def _request_cache_get(key: str):
    try:
        from flask import g

        return getattr(g, key, None)
    except RuntimeError:
        return None


def _request_cache_set(key: str, value) -> None:
    try:
        from flask import g

        setattr(g, key, value)
    except RuntimeError:
        pass


def get_managed_pages_for_user(
    user_id: str,
    *,
    include_token: bool = False,
    client=None,
    normalize_active: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return a user's managed pages with at most one active row.

    Older worktrees could leave multiple pages marked ``active``. When that
    happens we deterministically keep the newest active row and deactivate the
    rest so downstream publish/token helpers never pick an arbitrary page.
    """
    cache_key = None
    if client is None:
        cache_key = f"_managed_pages::{user_id}::{int(include_token)}::{int(normalize_active)}"
        cached = _request_cache_get(cache_key)
        if cached is not None:
            return [dict(row) for row in cached]

    db = client or config.get_database_client()
    requested_fields = [
        "page_id",
        "page_name",
        "instagram_account_id",
        "posts_per_day",
        "posting_times",
        "language",
        "status",
        "last_synced_at",
        "created_at",
        "token_expires_at",
    ]
    if include_token:
        requested_fields.append("access_token")

    selected_fields = [
        field
        for field in requested_fields
        if field not in _managed_pages_missing_optional_columns
    ]

    while True:
        try:
            result = (
                db.table("managed_pages")
                .select(", ".join(selected_fields))
                .eq("user_id", user_id)
                .execute()
            )
            break
        except Exception as exc:
            missing_column = _extract_missing_managed_pages_column(exc)
            if (
                missing_column
                and missing_column in _MANAGED_PAGES_OPTIONAL_COLUMNS
                and missing_column in selected_fields
            ):
                _managed_pages_missing_optional_columns.add(missing_column)
                selected_fields = [
                    field for field in selected_fields if field != missing_column
                ]
                logging.getLogger("utils").warning(
                    "managed_pages column %s is missing in the current DB schema; retrying without it",
                    missing_column,
                )
                continue
            raise

    rows = []
    for row in result.data or []:
        normalized = dict(row)
        for field in requested_fields:
            normalized.setdefault(field, None)
        rows.append(normalized)
    rows.sort(
        key=lambda row: (
            str(row.get("status") or "").lower() == "active",
            _managed_page_created_at(row),
            str(row.get("page_id") or ""),
        ),
        reverse=True,
    )

    if not normalize_active:
        if cache_key is not None:
            _request_cache_set(cache_key, [dict(row) for row in rows])
        return rows

    active_rows = [row for row in rows if str(row.get("status") or "").lower() == "active"]
    if len(active_rows) <= 1:
        if cache_key is not None:
            _request_cache_set(cache_key, [dict(row) for row in rows])
        return rows

    primary_page = active_rows[0]
    for row in active_rows[1:]:
        page_id = str(row.get("page_id") or "").strip()
        if not page_id:
            continue
        db.table("managed_pages").update({"status": "inactive"}).eq("user_id", user_id).eq(
            "page_id", page_id
        ).execute()
        row["status"] = "inactive"

    logging.getLogger("utils").warning(
        "Normalized multiple active managed_pages rows for user %s; kept %s active",
        user_id[:8],
        str(primary_page.get("page_id") or "")[:16],
    )
    if cache_key is not None:
        _request_cache_set(cache_key, [dict(row) for row in rows])
    return rows


def get_active_managed_page_for_user(
    user_id: str,
    *,
    include_token: bool = False,
    client=None,
) -> Optional[Dict[str, Any]]:
    """Return the user's single active managed page after normalization."""
    cache_key = None
    if client is None:
        cache_key = f"_active_managed_page::{user_id}::{int(include_token)}"
        cached = _request_cache_get(cache_key)
        if cached is not None:
            return dict(cached) if cached else None

    pages = get_managed_pages_for_user(
        user_id,
        include_token=include_token,
        client=client,
        normalize_active=True,
    )
    active_page = next(
        (row for row in pages if str(row.get("status") or "").lower() == "active"),
        None,
    )
    if cache_key is not None:
        _request_cache_set(cache_key, dict(active_page) if active_page else {})
    return active_page


def load_tokens_for_user(user_id: str) -> Optional[Dict]:
    """
    Load the active Facebook page token for a user from `managed_pages`.
    Returns a dict compatible with the legacy `load_tokens()` signature:
    {"page_id": ..., "page_token": ..., "instagram_account_id": ...}
    or None if no active page is found.
    """
    try:
        row = get_active_managed_page_for_user(user_id, include_token=True)
        if not row:
            return None
        encrypted_token = row.get("access_token") or ""
        page_token = decrypt_value(encrypted_token) if encrypted_token else ""
        return {
            "page_id": row["page_id"],
            "page_name": row.get("page_name", ""),
            "page_token": page_token,
            "instagram_account_id": row.get("instagram_account_id") or "",
            "user_token": page_token,
            # Schedule settings from managed_pages (page-level, canonical source)
            "posts_per_day": row.get("posts_per_day"),
            "posting_times": row.get("posting_times"),
            "page_language": (row.get("language") or "").lower(),
        }
    except Exception as exc:
        logging.getLogger("utils").error("load_tokens_for_user failed: %s", exc)
        return None


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    """Parse an ISO-ish timestamp string into an aware UTC datetime."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def get_active_page_health(user_id: str) -> Dict:
    """
    Return health metadata for the user's active Facebook page connection.

    The result is safe for UI/API use and does not include the decrypted token.
    """
    default_payload: Dict = {
        "connected": False,
        "page_id": "",
        "page_name": "",
        "status": "missing",
        "instagram_connected": False,
        "token_expires_at": None,
        "token_status": "missing",
        "token_expired": False,
        "token_days_remaining": None,
        "connected_at": None,
    }
    cache_key = f"_active_page_health::{user_id}"
    cached = _request_cache_get(cache_key)
    if cached is not None:
        return dict(cached)
    try:
        row = get_active_managed_page_for_user(user_id, include_token=False)
        if not row:
            _request_cache_set(cache_key, dict(default_payload))
            return default_payload
        now = datetime.now(timezone.utc)
        expires_at = _parse_iso_datetime(row.get("token_expires_at") or "")
        token_status = "unknown"
        token_expired = False
        token_days_remaining = None

        if expires_at is None:
            token_status = "unknown"
        else:
            seconds_remaining = (expires_at - now).total_seconds()
            token_days_remaining = round(seconds_remaining / 86400, 1)
            token_expired = seconds_remaining <= 0
            if token_expired:
                token_status = "expired"
            elif seconds_remaining <= 7 * 86400:
                token_status = "expiring"
            else:
                token_status = "healthy"

        payload = {
            "connected": True,
            "page_id": row.get("page_id") or "",
            "page_name": row.get("page_name") or "",
            "status": row.get("status") or "active",
            "instagram_connected": bool(row.get("instagram_account_id")),
            "token_expires_at": expires_at.isoformat() if expires_at else None,
            "token_status": token_status,
            "token_expired": token_expired,
            "token_days_remaining": token_days_remaining,
            "connected_at": row.get("created_at"),
        }
        _request_cache_set(cache_key, dict(payload))
        return payload
    except Exception as exc:
        logging.getLogger("utils").error("get_active_page_health failed: %s", exc)
        payload = {**default_payload, "error": str(exc)}
        _request_cache_set(cache_key, dict(payload))
        return payload


def get_gemini_key_for_user(user_id: str) -> Optional[str]:
    """
    Return the decrypted Gemini API key for a user from user_settings.
    Falls back to the GEMINI_API_KEY env var if no per-user key is stored.
    This is what the engine should call instead of reading config.GEMINI_API_KEY.
    """
    settings = {}
    try:
        settings = get_user_settings(user_id)
        provider = (settings.get("ai_provider") or "gemini").strip().lower()
        encrypted = settings.get("gemini_api_key")
        if not encrypted and provider == "gemini":
            encrypted = settings.get("ai_api_key")
        if encrypted:
            return decrypt_value(encrypted)
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "") or None


def get_ai_key_for_user(user_id: str) -> Optional[str]:
    """Return the decrypted provider key for a user, falling back to provider env vars."""
    settings = {}
    try:
        settings = get_user_settings(user_id)
        encrypted = settings.get("ai_api_key") or settings.get("gemini_api_key")
        if encrypted:
            return decrypt_value(encrypted)
    except Exception:
        pass

    provider = (settings.get("ai_provider") or "gemini").strip().lower()
    env_name = {
        "gemini": "GEMINI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "grok": "OPENROUTER_API_KEY",
        "groq": "OPENROUTER_API_KEY",
        "deepseek": "OPENROUTER_API_KEY",
        "minimax": "OPENROUTER_API_KEY",
        "glm": "OPENROUTER_API_KEY",
        "nvidia": "OPENROUTER_API_KEY",
    }.get(provider)
    if not env_name:
        return None
    value = os.getenv(env_name, "")
    if value:
        return value
    if env_name == "OPENROUTER_API_KEY":
        for fallback_name in ("OPENROUTER_API_KEY_1", "OPENROUTER_API_KEY_2", "OPENROUTER_API_KEY_3"):
            fallback_value = os.getenv(fallback_name, "")
            if fallback_value:
                return fallback_value
    return None


def save_fb_page_for_user(
    user_id: str,
    page_id: str,
    page_name: str,
    page_token: Optional[str],
    instagram_account_id: str = "",
    token_expires_in_seconds: int = 0,
    posts_per_day: Optional[int] = None,
    posting_times: Optional[str] = None,
    language: Optional[str] = None,
    status: str = "active",
) -> bool:
    """
    Save a Facebook page access token to managed_pages, scoped to user_id.
    The token is Fernet-encrypted before storage.

    Parameters
    ----------
    token_expires_in_seconds : int
        OAuth-provided ``expires_in`` value in seconds.  When non-zero, the
        actual OAuth expiry is used for monitoring accuracy.  Defaults to 0,
    in which case a 60-day fallback is used (Facebook long-lived tokens
    typically expire after ~60 days).
    """
    try:
        client = config.get_database_client()
        normalized_status = str(status or "active").strip().lower() or "active"
        existing = (
            client.table("managed_pages")
            .select("page_id, access_token")
            .eq("page_id", page_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        payload: Dict = {
            "page_id": page_id,
            "page_name": page_name,
            "user_id": user_id,
            "status": normalized_status,
        }
        if page_token:
            from datetime import datetime, timedelta, timezone as _tz

            if token_expires_in_seconds and token_expires_in_seconds > 0:
                token_expires_at = (
                    datetime.now(_tz.utc) + timedelta(seconds=token_expires_in_seconds)
                ).isoformat()
            else:
                token_expires_at = (datetime.now(_tz.utc) + timedelta(days=60)).isoformat()

            payload["access_token"] = encrypt_value(page_token)
            payload["token_expires_at"] = token_expires_at
        elif not existing.data:
            payload["access_token"] = encrypt_value("")
            payload["token_expires_at"] = None

        if instagram_account_id:
            payload["instagram_account_id"] = instagram_account_id
        if posts_per_day is not None:
            payload["posts_per_day"] = posts_per_day
        if posting_times is not None:
            payload["posting_times"] = posting_times
        if language is not None:
            payload["language"] = str(language).strip().lower()

        if normalized_status == "active":
            for row in get_managed_pages_for_user(
                user_id,
                client=client,
                normalize_active=False,
            ):
                existing_page_id = str(row.get("page_id") or "").strip()
                if existing_page_id and existing_page_id != page_id and str(row.get("status") or "").lower() == "active":
                    client.table("managed_pages").update({"status": "inactive"}).eq(
                        "user_id", user_id
                    ).eq("page_id", existing_page_id).execute()

        if existing.data:
            client.table("managed_pages").update(payload).eq("page_id", page_id).eq("user_id", user_id).execute()
        else:
            client.table("managed_pages").insert(payload).execute()
        return True
    except Exception as exc:
        logging.getLogger("utils").error("save_fb_page_for_user failed: %s", exc)
        return False
