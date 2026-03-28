"""Settings, config, and setup API routes — all tenant-scoped."""

from typing import Dict

from flask import Blueprint, jsonify, request, session, url_for
from flask_login import current_user

import config
from app.utils import (
    api_login_required,
    build_locale_niche_preset_updates,
    disabled_in_v1,
    get_available_presets,
    normalize_user_profile_updates,
    require_user_settings_update,
    seed_session_ui_language,
)

logger = config.get_logger("settings")

settings_bp = Blueprint("settings", __name__)
def _has_connected_facebook_page(user_id: str) -> bool:
    """Return True when the current user has at least one active Facebook page."""
    try:
        from app.utils import load_tokens_for_user
        return bool(load_tokens_for_user(user_id))
    except Exception as exc:
        logger.warning("Could not resolve Facebook connection state for %s: %s", user_id[:8], exc)
        return False


def _save_user_settings(updates: Dict) -> None:
    """Persist tenant-scoped settings to user_settings."""
    if not updates:
        return
    require_user_settings_update(current_user.id, updates)


def _json_success(**payload):
    data = {"success": True}
    data.update(payload)
    return jsonify(data)


def _json_error(message: str, status: int = 400, **payload):
    data = {"success": False, "error": message}
    data.update(payload)
    return jsonify(data), status


def _extract_ai_payload(data: Dict) -> Dict:
    """Normalize provider/model/key inputs from legacy and new settings payloads."""
    inferred_provider = ""
    if data.get("gemini_key"):
        inferred_provider = "gemini"
    elif data.get("openrouter_key"):
        inferred_provider = "openrouter"
    provider = (
        data.get("provider")
        or data.get("ai_provider")
        or inferred_provider
        or "gemini"
    )
    model = data.get("model") or data.get("ai_model") or ""
    api_key = (
        data.get("ai_key")
        or data.get("key")
        or data.get("gemini_key")
        or data.get("openrouter_key")
        or ""
    )
    provider_fallback = data.get("provider_fallback") or ""
    return {
        "provider": str(provider).strip().lower(),
        "model": str(model).strip(),
        "api_key": str(api_key).strip(),
        "provider_fallback": str(provider_fallback).strip().lower(),
    }


def _build_ai_settings_updates(data: Dict) -> Dict:
    """Build encrypted AI provider settings payload for user_settings."""
    from app.utils import encrypt_value

    payload = _extract_ai_payload(data)
    normalized_payload: Dict = {"ai_provider": payload["provider"]}
    if payload["model"]:
        normalized_payload["ai_model"] = payload["model"]
    if payload["provider_fallback"] or "provider_fallback" in data:
        normalized_payload["provider_fallback"] = payload["provider_fallback"]

    updates = normalize_user_profile_updates(normalized_payload)

    if payload["api_key"]:
        encrypted = encrypt_value(payload["api_key"])
        updates["ai_api_key"] = encrypted
        if payload["provider"] == "gemini":
            updates["gemini_api_key"] = encrypted
        else:
            updates["gemini_api_key"] = None

    return updates


def _build_supported_settings_updates(data: Dict) -> tuple[Dict, list[str]]:
    updates: Dict = {}
    warnings: list[str] = []

    profile_updates = normalize_user_profile_updates(data)
    if profile_updates:
        updates.update(profile_updates)

    ai_updates = _build_ai_settings_updates(data)
    if ai_updates:
        updates.update(ai_updates)

    if data.get("pexels_key"):
        updates["pexels_api_key"] = str(data["pexels_key"]).strip()

    if data.get("facebook_token") or data.get("facebook_page_id") or data.get("fb_token"):
        warnings.append("Facebook page connection is managed via the OAuth flow, not manual token storage.")

    return updates, warnings


def _get_user_setup_status(user_id: str) -> Dict:
    """
    Return tenant-scoped setup readiness derived from DB state only.

    This intentionally avoids global env heuristics for user-facing readiness.
    """
    from app.utils import get_user_settings

    settings = get_user_settings(user_id)
    has_fb = _has_connected_facebook_page(user_id)
    has_ai = bool(settings.get("ai_api_key") or settings.get("gemini_api_key"))
    has_images = bool(settings.get("pexels_api_key"))

    missing = []
    if not has_fb:
        missing.append("facebook")
    if not has_ai:
        missing.append("ai")
    if not has_images:
        missing.append("images")

    return {
        "complete": has_fb and has_ai,
        "facebook": has_fb,
        "ai": has_ai,
        "images": has_images,
        "missing": missing,
    }


def _serialize_user_profile(user_id: str) -> Dict:
    """Return the resolved locale + AI profile for a user."""
    from user_config import get_user_config
    from app.utils import get_user_settings

    resolved = get_user_config(user_id)
    settings = get_user_settings(user_id) or {}
    return {
        "country_code": resolved.country_code,
        "timezone": resolved.timezone,
        "ui_language": resolved.ui_language,
        "content_language": resolved.content_language,
        "content_languages": resolved.content_languages,
        "content_tone": resolved.content_tone,
        "content_dialect": resolved.content_dialect,
        "content_mode": resolved.content_mode,
        "source_preset": resolved.source_preset,
        "niche_preset": resolved.niche_preset,
        "rss_feed_urls": resolved.rss_feed_urls,
        "ai_provider": resolved.ai_provider,
        "provider_fallback": resolved.provider_fallback,
        "ai_model": resolved.ai_model,
        "posts_per_day": resolved.posts_per_day,
        "posting_times": resolved.posting_times,
        "approval_mode": bool(settings.get("approval_mode")),
    }


def _load_settings_bootstrap_payload(user_id: str) -> Dict:
    """Return the startup payload needed by the settings page."""
    from user_config import get_user_config

    try:
        from ai_provider import list_providers

        providers = list_providers()
    except ImportError:
        providers = []

    return {
        "profile": _serialize_user_profile(user_id),
        "providers": providers,
        "presets": get_available_presets(),
        "feeds": get_user_config(user_id).rss_feed_urls,
    }


# ============================================================
# Config — API Keys, Database, Approval
# ============================================================

@settings_bp.route("/api/config/api-keys", methods=["GET", "POST"])
@api_login_required
def config_api_keys():
    if request.method == "GET":
        status = _get_user_setup_status(current_user.id)
        return jsonify({
            "facebook": status["facebook"],
            "gemini": status["ai"],
            "openrouter": False,
            "pexels": status["images"],
            "complete": status["complete"],
            "missing": status["missing"],
        })

    data = request.json or {}
    updates, warnings = _build_supported_settings_updates(data)
    try:
        _save_user_settings(updates)
    except RuntimeError as exc:
        return _json_error(str(exc), 500, warnings=warnings)
    if updates.get("ai_api_key"):
        logger.info("AI key stored encrypted in DB for user %s", current_user.id)

    logger.info("Tenant API keys updated in DB by user %s", current_user.id)
    return _json_success(
        message="Supported keys saved to your account.",
        warnings=warnings,
    )


@settings_bp.route("/api/settings/profile", methods=["GET", "POST"])
@api_login_required
def settings_profile():
    if request.method == "GET":
        profile = _load_settings_bootstrap_payload(current_user.id)["profile"]
        session_lang = str(session.get("ui_language") or "").strip().lower()
        if session_lang:
            profile["ui_language"] = session_lang
        return jsonify({"success": True, "profile": profile})

    data = request.get_json(force=True) or {}
    updates = normalize_user_profile_updates(data)
    if not updates:
        return _json_error("No valid profile fields provided", 400)

    try:
        _save_user_settings(updates)
        if updates.get("ui_language"):
            seed_session_ui_language(current_user.id, str(updates["ui_language"]))
    except RuntimeError as exc:
        return _json_error(str(exc), 500)
    profile = _serialize_user_profile(current_user.id)
    if session.get("ui_language"):
        profile["ui_language"] = str(session["ui_language"]).lower()
    return _json_success(profile=profile)


@settings_bp.route("/api/settings/presets", methods=["GET"])
@api_login_required
def get_settings_presets():
    return jsonify({"success": True, **get_available_presets()})


@settings_bp.route("/api/settings/presets/apply", methods=["POST"])
@api_login_required
def apply_settings_preset():
    data = request.get_json(force=True) or {}
    country_code = str(data.get("country_code") or config.DEFAULT_COUNTRY_CODE).strip().upper()
    niche_preset = str(data.get("niche_preset") or "").strip().lower() or None
    updates = build_locale_niche_preset_updates(country_code, niche_preset=niche_preset)
    try:
        _save_user_settings(updates)
    except RuntimeError as exc:
        return _json_error(str(exc), 500)
    return jsonify({"success": True, "profile": _serialize_user_profile(current_user.id)})



@settings_bp.route("/api/config/approval-mode", methods=["POST"])
@api_login_required
def config_approval_mode():
    data = request.json or {}
    enabled = bool(data.get("enabled", data.get("approval_mode", False)))

    try:
        _save_user_settings({"approval_mode": enabled})
    except Exception as exc:
        logger.warning("Could not persist approval_mode to user_settings: %s", exc)
        return _json_error(str(exc), 500)

    return _json_success(enabled=enabled, approval_mode=enabled)


@settings_bp.route("/api/config/rss-feeds", methods=["GET"])
@api_login_required
def get_rss_feeds():
    try:
        return _json_success(feeds=_load_settings_bootstrap_payload(current_user.id)["feeds"])
    except ImportError:
        return _json_error("scraper module not found", 500, feeds=[])


@settings_bp.route("/api/config/rss-feeds", methods=["POST"])
@api_login_required
def set_rss_feeds():
    try:
        data = request.get_json(force=True)
        urls = data.get("feeds", [])
        if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
            return _json_error("feeds must be a list of URL strings", 400)
        urls = [u.strip() for u in urls if u.strip()]
        _save_user_settings({"rss_feed_urls": ",".join(urls)})
        return _json_success(feeds=urls)
    except ImportError:
        return _json_error("scraper module not found", 500)
    except RuntimeError as exc:
        return _json_error(str(exc), 500)



# ============================================================
# Settings — Keys & AI provider
# ============================================================

@settings_bp.route("/api/settings/keys", methods=["POST"])
@api_login_required
def save_settings_keys():
    data = request.get_json(force=True)
    updates, warnings = _build_supported_settings_updates(data)
    try:
        _save_user_settings(updates)
    except RuntimeError as exc:
        return _json_error(str(exc), 500, warnings=warnings)

    return _json_success(message="Supported keys saved", warnings=warnings)


@settings_bp.route("/api/settings/test-ai", methods=["POST"])
@api_login_required
def test_ai_key():
    data = request.get_json(force=True)
    from ai_provider import test_ai_key as run_key_test

    payload = _extract_ai_payload(data)
    result = run_key_test(
        provider=payload["provider"],
        api_key=payload["api_key"],
        model=payload["model"],
    )
    return jsonify({
        "success": result["valid"],
        "valid": result["valid"],
        "error": result["error"],
        "provider": result["provider"],
        "model": result["model"],
    })


# ============================================================
# Setup Wizard
# ============================================================

@settings_bp.route("/api/setup/save", methods=["POST"])
@api_login_required
def save_setup():
    try:
        data = request.json or {}
        updates, warnings = _build_supported_settings_updates(data)
        _save_user_settings(updates)

        logger.info("Legacy setup payload mapped to tenant DB settings for user %s", current_user.id)
        return _json_success(redirect=url_for("onboarding.wizard"), warnings=warnings)
    except Exception as e:
        logger.error("Setup save error: %s", e)
        return _json_error(str(e), 500)


@settings_bp.route("/api/setup/check", methods=["GET"])
@api_login_required
def check_setup():
    return _json_success(**_get_user_setup_status(current_user.id))


# ============================================================
# Version & Providers
# ============================================================

@settings_bp.route("/api/version", methods=["GET"])
@api_login_required
def get_version_info():
    try:
        from version_checker import check_for_update
        return jsonify(check_for_update())
    except ImportError:
        return jsonify({"current": "2.1.1", "available": False})


@settings_bp.route("/api/providers", methods=["GET"])
@api_login_required
def get_ai_providers():
    try:
        from ai_provider import list_providers
        return jsonify({"providers": list_providers()})
    except ImportError:
        return jsonify({"providers": []})


@settings_bp.route("/api/ai/providers", methods=["GET"])
@api_login_required
def get_ai_providers_v2():
    return get_ai_providers()


# ============================================================
# Per-user Gemini key (stored encrypted in user_settings)
# ============================================================

@settings_bp.route("/api/settings/gemini-key", methods=["GET"])
@api_login_required
def get_gemini_key_status():
    """Return whether the current user has a saved Gemini key."""
    from app.utils import get_user_settings
    settings = get_user_settings(current_user.id)
    return jsonify({"has_key": bool(settings.get("ai_api_key") or settings.get("gemini_api_key"))})


@settings_bp.route("/api/settings/gemini-key", methods=["POST"])
@api_login_required
def save_gemini_key():
    """Encrypt and persist a Gemini API key for the current user."""
    data = request.get_json(force=True)
    if not (data.get("key") or "").strip():
        return jsonify({"ok": False, "error": "No key provided"}), 400
    try:
        _save_user_settings(_build_ai_settings_updates({"provider": "gemini", "ai_key": data.get("key"), "model": data.get("model")}))
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@settings_bp.route("/api/settings/gemini-key", methods=["DELETE"])
@api_login_required
def delete_gemini_key():
    """Remove the stored Gemini key for the current user."""
    try:
        _save_user_settings({"gemini_api_key": None, "ai_api_key": None})
        return jsonify({"ok": True})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
