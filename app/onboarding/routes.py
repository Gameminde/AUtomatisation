"""Onboarding wizard — 4-step guided setup for new users."""

from flask import (
    Blueprint, redirect, render_template, request,
    session, url_for, jsonify,
)
from flask_login import current_user, login_required

import config
from app.utils import (
    build_locale_niche_preset_updates,
    encrypt_value,
    get_available_presets,
    get_user_settings,
    normalize_user_profile_updates,
    require_user_settings_update,
    seed_session_ui_language,
)

logger = config.get_logger("onboarding")

onboarding_bp = Blueprint("onboarding", __name__, url_prefix="/onboarding")


def _save_user_settings(updates: dict) -> None:
    """Persist onboarding-scoped settings or raise on failure."""
    if not updates:
        return
    require_user_settings_update(current_user.id, updates)


def _step_from_settings(settings: dict) -> int:
    """Return the wizard step the user should be on (1–4)."""
    if settings.get("onboarding_complete"):
        return 5
    return int(settings.get("onboarding_step") or 1)


def _has_saved_ai_key(settings: dict) -> bool:
    return bool(settings.get("ai_api_key") or settings.get("gemini_api_key"))


def _serialize_profile(user_id: str) -> dict:
    from user_config import get_user_config

    resolved = get_user_config(user_id)
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
    }


@onboarding_bp.route("/", methods=["GET"])
@login_required
def wizard():
    """Legacy onboarding entrypoint now redirects users back to the dashboard."""
    return render_template(
        "onboarding.html",
        active_page="onboarding",
        redirect_url=url_for("web.page_dashboard"),
    )


@onboarding_bp.route("/step", methods=["POST"])
@login_required
def set_step():
    """
    AJAX endpoint — advance the user's persisted onboarding step.
    Body: { "step": 2 }
    """
    data = request.get_json(silent=True) or {}
    new_step = int(data.get("step", 1))
    new_step = max(1, min(new_step, 5))

    is_complete = new_step >= 5

    try:
        _save_user_settings({
        "onboarding_step": new_step,
        "onboarding_complete": is_complete,
        })
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    if is_complete:
        session[f"ob_done:{current_user.id}"] = True

    return jsonify({"ok": True, "step": new_step, "complete": is_complete})


@onboarding_bp.route("/save-gemini", methods=["POST"])
@login_required
def save_gemini():
    """
    AJAX endpoint — encrypt and persist the user's Gemini API key.
    Body: { "key": "AIza..." }
    """
    data = request.get_json(silent=True) or {}
    api_key = (data.get("key") or "").strip()

    if not api_key:
        return jsonify({"ok": False, "error": "No key provided"}), 400

    try:
        provider = str(data.get("provider") or "gemini").strip().lower()
        model = str(data.get("model") or "").strip()
        fallback_provider = str(data.get("provider_fallback") or "").strip().lower()
        encrypted = encrypt_value(api_key)
        updates = normalize_user_profile_updates(
            {
                "ai_provider": provider,
                "ai_model": model,
                "provider_fallback": fallback_provider,
            }
        )
        updates["ai_api_key"] = encrypted
        updates["gemini_api_key"] = encrypted if provider == "gemini" else None
        _save_user_settings(updates)
        logger.info("Saved AI key for user %s", current_user.id)
        return jsonify({"ok": True})
    except Exception as exc:
        logger.error("save_gemini error: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@onboarding_bp.route("/test-gemini", methods=["POST"])
@login_required
def test_gemini():
    """
    AJAX endpoint — test a Gemini key by making a minimal API call.
    Body: { "key": "AIza..." }
    """
    data = request.get_json(silent=True) or {}
    api_key = (data.get("key") or "").strip()
    if not api_key:
        return jsonify({"ok": False, "error": "No key provided"}), 400

    try:
        from ai_provider import test_ai_key as run_key_test

        provider = str(data.get("provider") or "gemini").strip().lower()
        model = str(data.get("model") or "").strip()
        result = run_key_test(provider=provider, api_key=api_key, model=model)
        return jsonify({"ok": result["valid"], "provider": result["provider"], "model": result["model"], "error": result["error"]})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


@onboarding_bp.route("/profile", methods=["GET", "POST"])
@login_required
def save_profile():
    """Load or persist onboarding profile fields before the new frontend lands."""
    if request.method == "GET":
        seed_session_ui_language(current_user.id)
        return jsonify({"ok": True, "profile": _serialize_profile(current_user.id)})

    data = request.get_json(silent=True) or {}
    updates = normalize_user_profile_updates(data)
    if not updates:
        return jsonify({"ok": False, "error": "No valid profile fields provided"}), 400

    try:
        _save_user_settings(updates)
        if updates.get("ui_language"):
            seed_session_ui_language(current_user.id, str(updates.get("ui_language")))
        return jsonify({"ok": True, "profile": _serialize_profile(current_user.id)})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@onboarding_bp.route("/presets", methods=["GET", "POST"])
@login_required
def onboarding_presets():
    """Expose locale and niche presets for onboarding without frontend coupling."""
    if request.method == "GET":
        return jsonify({"ok": True, **get_available_presets()})

    data = request.get_json(silent=True) or {}
    country_code = str(data.get("country_code") or config.DEFAULT_COUNTRY_CODE).strip().upper()
    niche_preset = str(data.get("niche_preset") or "").strip().lower() or None
    updates = build_locale_niche_preset_updates(country_code, niche_preset=niche_preset)
    try:
        _save_user_settings(updates)
        return jsonify({"ok": True, "profile": _serialize_profile(current_user.id)})
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@onboarding_bp.route("/complete", methods=["POST"])
@login_required
def complete():
    """Mark onboarding as complete and redirect to dashboard."""
    try:
        _save_user_settings({
            "onboarding_step": 5,
            "onboarding_complete": True,
        })
    except RuntimeError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    session[f"ob_done:{current_user.id}"] = True

    # Queue an immediate worker-owned pipeline run so the user gets first
    # content quickly without spawning threads inside the web process.
    pipeline_queued = False
    try:
        from tasks.runner import request_immediate_run
        request_immediate_run(current_user.id)
        pipeline_queued = True
    except Exception as exc:
        logger.warning("Could not queue immediate post-onboarding pipeline run: %s", exc)

    return jsonify({
        "ok": True,
        "redirect": url_for("web.page_dashboard"),
        "pipeline_queued": pipeline_queued,
    })


@onboarding_bp.route("/status", methods=["GET"])
@login_required
def status():
    """Return onboarding status for the current user."""
    settings = get_user_settings(current_user.id)
    return jsonify({
        "step": _step_from_settings(settings),
        "complete": bool(settings.get("onboarding_complete")),
        "has_fb": _has_facebook_page(),
        "has_gemini": _has_saved_ai_key(settings),
        "profile": _serialize_profile(current_user.id),
    })


def _has_facebook_page() -> bool:
    """Check if the current user has at least one connected Facebook page."""
    try:
        from app.utils import load_tokens_for_user
        return bool(load_tokens_for_user(current_user.id))
    except Exception:
        return False
