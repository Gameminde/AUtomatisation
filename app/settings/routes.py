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
        return jsonify({
            "facebook": bool(os.getenv("FACEBOOK_ACCESS_TOKEN")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
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
        existing["GEMINI_API_KEY"] = data["gemini_key"]
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
    mapping = {
        "ai_key": "GEMINI_API_KEY" if data.get("provider") == "gemini" else "OPENROUTER_API_KEY",
        "fb_token": "FACEBOOK_ACCESS_TOKEN",
        "pexels_key": "PEXELS_API_KEY",
    }
    for field, env_var in mapping.items():
        val = data.get(field, "").strip()
        if val:
            existing[env_var] = val
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
        if data.get("ai_key"):
            existing["GEMINI_API_KEY" if ai_provider == "gemini" else "OPENROUTER_API_KEY"] = data["ai_key"]
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
