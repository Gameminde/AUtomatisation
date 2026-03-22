"""Onboarding wizard — 4-step guided setup for new users."""

import os
from flask import (
    Blueprint, redirect, render_template, request,
    session, url_for, jsonify,
)
from flask_login import current_user, login_required

import config
from app.utils import (
    decrypt_value, encrypt_value,
    get_user_settings, upsert_user_settings,
)

logger = config.get_logger("onboarding")

onboarding_bp = Blueprint("onboarding", __name__, url_prefix="/onboarding")


def _step_from_settings(settings: dict) -> int:
    """Return the wizard step the user should be on (1–4)."""
    if settings.get("onboarding_complete"):
        return 5
    return int(settings.get("onboarding_step") or 1)


@onboarding_bp.route("/", methods=["GET"])
@login_required
def wizard():
    """Render the onboarding wizard at the user's current step."""
    settings = get_user_settings(current_user.id)
    step = _step_from_settings(settings)

    if step >= 5:
        session[f"ob_done:{current_user.id}"] = True
        return redirect(url_for("web.page_dashboard"))

    has_fb = _has_facebook_page()
    has_gemini = bool(settings.get("gemini_api_key"))

    return render_template(
        "onboarding.html",
        step=step,
        has_fb=has_fb,
        has_gemini=has_gemini,
        active_page="onboarding",
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

    upsert_user_settings(current_user.id, {
        "onboarding_step": new_step,
        "onboarding_complete": is_complete,
    })

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
        encrypted = encrypt_value(api_key)
        upsert_user_settings(current_user.id, {"gemini_api_key": encrypted})
        logger.info("Saved Gemini key for user %s", current_user.id)
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
        import requests as _req
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models"
            f"?key={api_key}&pageSize=1"
        )
        resp = _req.get(url, timeout=10)
        if resp.status_code == 200:
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": f"HTTP {resp.status_code}"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})


def _trigger_pipeline_background(user_id: str) -> None:
    """Run the full pipeline for *user_id* in a daemon thread (fire-and-forget)."""
    try:
        from engine.user_config import UserConfig
        from tasks.runner import _run_pipeline_for_user
        uc = UserConfig.from_db(user_id)
        _run_pipeline_for_user(uc)
    except Exception as exc:
        logger.warning("Immediate post-onboarding pipeline run failed: %s", exc)


@onboarding_bp.route("/complete", methods=["POST"])
@login_required
def complete():
    """Mark onboarding as complete and redirect to dashboard."""
    upsert_user_settings(current_user.id, {
        "onboarding_step": 5,
        "onboarding_complete": True,
    })
    session[f"ob_done:{current_user.id}"] = True

    # Trigger an immediate pipeline run so the user gets first content within
    # minutes, rather than waiting up to 30 minutes for the scheduled cycle.
    import threading
    threading.Thread(
        target=_trigger_pipeline_background,
        args=(current_user.id,),
        daemon=True,
        name=f"pipeline-init-{current_user.id[:8]}",
    ).start()

    return jsonify({"ok": True, "redirect": url_for("web.page_dashboard")})


@onboarding_bp.route("/status", methods=["GET"])
@login_required
def status():
    """Return onboarding status for the current user."""
    settings = get_user_settings(current_user.id)
    return jsonify({
        "step": _step_from_settings(settings),
        "complete": bool(settings.get("onboarding_complete")),
        "has_fb": _has_facebook_page(),
        "has_gemini": bool(settings.get("gemini_api_key")),
    })


def _has_facebook_page() -> bool:
    """Check if the current user has at least one connected Facebook page."""
    try:
        from app.utils import _get_supabase_client
        sb = _get_supabase_client()
        result = (
            sb.table("managed_pages")
            .select("id")
            .eq("user_id", current_user.id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception:
        return False
