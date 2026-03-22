"""Settings, config, and setup API routes — all tenant-scoped."""

import os
from pathlib import Path
from typing import Dict

from flask import Blueprint, jsonify, request
from flask_login import current_user

import config
from app.utils import api_login_required, _read_env_file, _write_env_file

logger = config.get_logger("settings")

settings_bp = Blueprint("settings", __name__)


# ============================================================
# Config — API Keys, Database, Approval
# ============================================================

@settings_bp.route("/api/config/api-keys", methods=["GET", "POST"])
@api_login_required
def config_api_keys():
    if request.method == "GET":
        from app.utils import get_user_settings
        settings = get_user_settings(current_user.id)
        return jsonify({
            "facebook": bool(os.getenv("FACEBOOK_ACCESS_TOKEN")),
            "gemini": bool(settings.get("gemini_api_key")),
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
            "pexels": bool(os.getenv("PEXELS_API_KEY")),
        })
    data = request.json or {}
    env_path, existing = _read_env_file()
    if data.get("facebook_token"):
        existing["FACEBOOK_ACCESS_TOKEN"] = data["facebook_token"]
    if data.get("facebook_page_id"):
        existing["FACEBOOK_PAGE_ID"] = data["facebook_page_id"]
    if data.get("gemini_key"):
        from app.utils import encrypt_value, upsert_user_settings
        encrypted = encrypt_value(data["gemini_key"])
        upsert_user_settings(current_user.id, {"gemini_api_key": encrypted})
        logger.info("Gemini key stored encrypted in DB for user %s", current_user.id)
    if data.get("openrouter_key"):
        existing["OPENROUTER_API_KEY"] = data["openrouter_key"]
    if data.get("pexels_key"):
        existing["PEXELS_API_KEY"] = data["pexels_key"]
    _write_env_file(env_path, existing)
    logger.info("API keys updated by user %s", current_user.id)
    return jsonify({"success": True, "message": "Keys saved. Restart dashboard to apply."})


@settings_bp.route("/api/config/database", methods=["GET", "POST"])
@api_login_required
def config_database():
    if request.method == "GET":
        return jsonify({"db_mode": os.getenv("DB_MODE", "sqlite").lower(), "supabase_configured": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))})
    data = request.json or {}
    mode = (data.get("mode") or "sqlite").lower()
    env_path, existing = _read_env_file()
    if mode == "supabase":
        if data.get("supabase_url"):
            existing["SUPABASE_URL"] = data["supabase_url"]
        if data.get("supabase_key"):
            existing["SUPABASE_KEY"] = data["supabase_key"]
        existing["DB_MODE"] = "supabase"
    else:
        existing["DB_MODE"] = "sqlite"
    _write_env_file(env_path, existing)
    return jsonify({"success": True, "db_mode": existing.get("DB_MODE", "sqlite")})


@settings_bp.route("/api/config/approval-mode", methods=["POST"])
@api_login_required
def config_approval_mode():
    data = request.json or {}
    enabled = bool(data.get("enabled"))

    # Write per-user setting to user_settings (multi-tenant source of truth)
    try:
        from app.utils import _get_supabase_client
        sb = _get_supabase_client()
        sb.table("user_settings").upsert({
            "user_id": current_user.id,
            "approval_mode": enabled,
        }).execute()
    except Exception as exc:
        import logging
        logging.getLogger("settings").warning("Could not persist approval_mode to user_settings: %s", exc)

    # Also update global env for backward-compat with any non-tenant code paths
    env_path, existing = _read_env_file()
    existing["APPROVAL_MODE"] = "on" if enabled else "off"
    _write_env_file(env_path, existing)
    return jsonify({"success": True, "enabled": enabled})


@settings_bp.route("/api/config/rss-feeds", methods=["GET"])
@api_login_required
def get_rss_feeds():
    try:
        from scraper import get_feeds
        return jsonify({"feeds": get_feeds()})
    except ImportError:
        return jsonify({"feeds": [], "error": "scraper module not found"}), 500


@settings_bp.route("/api/config/rss-feeds", methods=["POST"])
@api_login_required
def set_rss_feeds():
    try:
        from scraper import set_feeds
        data = request.get_json(force=True)
        urls = data.get("feeds", [])
        if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
            return jsonify({"error": "feeds must be a list of URL strings"}), 400
        urls = [u.strip() for u in urls if u.strip()]
        if not urls:
            return jsonify({"error": "At least one feed URL required"}), 400
        set_feeds(urls)
        return jsonify({"success": True, "feeds": urls})
    except ImportError:
        return jsonify({"error": "scraper module not found"}), 500


@settings_bp.route("/api/config/prompts", methods=["GET"])
@api_login_required
def get_ai_prompts():
    try:
        from ai_generator import get_prompts
        return jsonify(get_prompts())
    except ImportError:
        return jsonify({"error": "ai_generator module not found"}), 500


@settings_bp.route("/api/config/prompts", methods=["POST"])
@api_login_required
def set_ai_prompts():
    try:
        from ai_generator import set_prompts
        data = request.get_json(force=True)
        batch = data.get("batch")
        single = data.get("single")
        if batch is None and single is None:
            return jsonify({"error": "Provide 'batch' and/or 'single' prompt text"}), 400
        set_prompts(batch=batch, single=single)
        return jsonify({"success": True})
    except ImportError:
        return jsonify({"error": "ai_generator module not found"}), 500


@settings_bp.route("/api/config/posts-limit", methods=["POST"])
@api_login_required
def set_posts_limit():
    try:
        import json
        data = request.get_json()
        limit = data.get("limit", 3)
        config_file = Path(__file__).parent.parent.parent / ".user_config.json"
        config_data: Dict = {}
        if config_file.exists():
            with open(config_file, "r") as f:
                config_data = json.load(f)
        config_data["posts_per_day"] = limit
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        return jsonify({"success": True, "limit": limit})
    except Exception as e:
        logger.error("Config error: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Settings — Keys & AI provider
# ============================================================

@settings_bp.route("/api/settings/keys", methods=["POST"])
@api_login_required
def save_settings_keys():
    data = request.get_json(force=True)
    env_path, existing = _read_env_file()
    ai_key = (data.get("ai_key") or "").strip()
    if ai_key and data.get("provider") == "gemini":
        from app.utils import encrypt_value, upsert_user_settings
        upsert_user_settings(current_user.id, {"gemini_api_key": encrypt_value(ai_key)})
        logger.info("Gemini key stored encrypted in DB for user %s", current_user.id)
    elif ai_key:
        existing["OPENROUTER_API_KEY"] = ai_key
    if data.get("fb_token"):
        existing["FACEBOOK_ACCESS_TOKEN"] = data["fb_token"].strip()
    if data.get("pexels_key"):
        existing["PEXELS_API_KEY"] = data["pexels_key"].strip()
    if data.get("provider"):
        existing["AI_PROVIDER"] = data["provider"]
    _write_env_file(env_path, existing)
    return jsonify({"success": True, "message": "Keys saved"})


@settings_bp.route("/api/settings/test-ai", methods=["POST"])
@api_login_required
def test_ai_key():
    data = request.get_json(force=True)
    key = data.get("key", "").strip()
    if not key or len(key) < 10:
        return jsonify({"success": False, "error": "Key too short"})
    return jsonify({"success": True, "message": "Key format looks valid"})


# ============================================================
# Setup Wizard
# ============================================================

@settings_bp.route("/api/setup/save", methods=["POST"])
@api_login_required
def save_setup():
    try:
        data = request.json or {}
        env_path, existing = _read_env_file()
        if data.get("fb_token"):
            existing["FACEBOOK_ACCESS_TOKEN"] = data["fb_token"]
        ai_provider = data.get("ai_provider", "gemini")
        ai_key = (data.get("ai_key") or "").strip()
        if ai_key:
            if ai_provider == "gemini":
                from app.utils import encrypt_value, upsert_user_settings
                upsert_user_settings(current_user.id, {"gemini_api_key": encrypt_value(ai_key)})
                logger.info("Gemini key stored encrypted in DB for user %s", current_user.id)
            else:
                existing["OPENROUTER_API_KEY"] = ai_key
        if data.get("pexels_key"):
            existing["PEXELS_API_KEY"] = data["pexels_key"]
        _write_env_file(env_path, existing)
        logger.info("Setup saved by user %s", current_user.id)
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Setup save error: %s", e)
        return jsonify({"error": str(e)}), 500


@settings_bp.route("/api/setup/check", methods=["GET"])
@api_login_required
def check_setup():
    fb_ok = bool(os.getenv("FACEBOOK_ACCESS_TOKEN"))
    ai_ok = bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENROUTER_API_KEY"))
    return jsonify({"complete": fb_ok and ai_ok, "facebook": fb_ok, "ai": ai_ok, "images": bool(os.getenv("PEXELS_API_KEY"))})


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


@settings_bp.route("/api/providers/test", methods=["POST"])
@api_login_required
def test_ai_provider():
    try:
        from ai_provider import get_provider
        data = request.get_json(force=True)
        client_obj = get_provider(data.get("provider", "gemini"))
        return jsonify(client_obj.test_connection())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ============================================================
# Per-user Gemini key (stored encrypted in user_settings)
# ============================================================

@settings_bp.route("/api/settings/gemini-key", methods=["GET"])
@api_login_required
def get_gemini_key_status():
    """Return whether the current user has a saved Gemini key."""
    from app.utils import get_user_settings
    settings = get_user_settings(current_user.id)
    return jsonify({"has_key": bool(settings.get("gemini_api_key"))})


@settings_bp.route("/api/settings/gemini-key", methods=["POST"])
@api_login_required
def save_gemini_key():
    """Encrypt and persist a Gemini API key for the current user."""
    from app.utils import encrypt_value, upsert_user_settings
    data = request.get_json(force=True)
    api_key = (data.get("key") or "").strip()
    if not api_key:
        return jsonify({"ok": False, "error": "No key provided"}), 400
    try:
        encrypted = encrypt_value(api_key)
        upsert_user_settings(current_user.id, {"gemini_api_key": encrypted})
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@settings_bp.route("/api/settings/gemini-key", methods=["DELETE"])
@api_login_required
def delete_gemini_key():
    """Remove the stored Gemini key for the current user."""
    from app.utils import upsert_user_settings
    upsert_user_settings(current_user.id, {"gemini_api_key": None})
    return jsonify({"ok": True})
