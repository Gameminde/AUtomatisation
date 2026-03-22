"""Web (HTML page) routes for the Content Factory dashboard."""

import re
from pathlib import Path

from flask import (
    Blueprint, abort, redirect, render_template,
    request, send_file, session, url_for,
)
from flask_login import login_required

web_bp = Blueprint("web", __name__)


# ── Dashboard pages ────────────────────────────────────────────────────────

@web_bp.route("/")
def page_landing():
    from flask_login import current_user
    if current_user and current_user.is_authenticated:
        return redirect(url_for("web.page_dashboard"))
    return render_template("landing.html")


@web_bp.route("/app/dashboard")
@login_required
def page_dashboard():
    return render_template("dashboard_v3.html", active_page="dashboard")


@web_bp.route("/studio")
@login_required
def page_studio():
    return render_template("studio_v3.html", active_page="studio")


@web_bp.route("/templates")
@login_required
def page_templates():
    return render_template("templates_v3.html", active_page="templates")


@web_bp.route("/settings")
@login_required
def page_settings():
    return render_template("settings_v3.html", active_page="settings")


@web_bp.route("/health")
@login_required
def page_health():
    return render_template("health_v3.html", active_page="health")


@web_bp.route("/setup")
@login_required
def page_setup():
    return render_template("setup_v3.html", active_page="setup")


# ── Public media serving (needed by Instagram CDN — no auth) ──────────────

@web_bp.route("/media/public/<path:filename>")
def serve_media_public(filename: str):
    """
    Serve a local generated/downloaded image publicly (no auth required).
    Used by Instagram publishing which needs a public HTTPS image URL.
    Only serves files from generated_images/ and downloaded_images/.
    """
    if not re.match(r"^[\w\-. ]+\.(jpg|jpeg|png|webp|gif)$", filename, re.IGNORECASE):
        abort(400)
    base_dir = Path(__file__).parent.parent.parent.resolve()
    for allowed_dir in ["generated_images", "downloaded_images"]:
        candidate = (base_dir / allowed_dir / filename).resolve()
        if candidate.exists() and candidate.parent == (base_dir / allowed_dir).resolve():
            return send_file(str(candidate))
    abort(404)


# ── Facebook OAuth flow (user must be logged in to connect their page) ─────

@web_bp.route("/oauth/facebook")
@login_required
def oauth_facebook_start():
    """Start Facebook OAuth flow — redirect to Facebook login."""
    import os as _os
    import config
    logger = config.get_logger("dashboard")
    try:
        from facebook_oauth import get_oauth_url, is_configured

        _fb_app_id = _os.getenv("FB_APP_ID", "")
        _fb_app_secret = _os.getenv("FB_APP_SECRET", "")
        _is_conf = is_configured()

        logger.info(
            "OAuth Debug: FB_APP_ID='%s...' FB_APP_SECRET='%s...' is_configured=%s",
            _fb_app_id[:6], _fb_app_secret[:6], _is_conf,
        )

        if not _is_conf:
            from flask import jsonify
            return jsonify({
                "error": "Facebook OAuth not configured",
                "help": "Set FB_APP_ID and FB_APP_SECRET in .env",
                "debug": {
                    "FB_APP_ID_empty": not _fb_app_id,
                    "FB_APP_SECRET_empty": not _fb_app_secret,
                    "is_configured": _is_conf,
                },
            }), 400

        url = get_oauth_url()
        return redirect(url)

    except Exception as e:
        logger.error("OAuth start error: %s", e)
        from flask import jsonify
        return jsonify({"error": str(e)}), 500


@web_bp.route("/oauth/facebook/callback")
@login_required
def oauth_facebook_callback():
    """Handle Facebook OAuth callback."""
    import config
    logger = config.get_logger("dashboard")
    try:
        from facebook_oauth import handle_callback

        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            return render_template("setup_v3.html", active_page="setup", oauth_error=error)
        if not code:
            return render_template(
                "setup_v3.html", active_page="setup",
                oauth_error="No authorization code received",
            )

        result = handle_callback(code)
        session["fb_oauth_result"] = result
        return redirect(url_for("web.oauth_select_page"))

    except Exception as e:
        logger.error("OAuth callback error: %s", e)
        return render_template("setup_v3.html", active_page="setup", oauth_error=str(e))


@web_bp.route("/oauth/facebook/select-page", methods=["GET", "POST"])
@login_required
def oauth_select_page():
    """Page selection after OAuth."""
    import config
    logger = config.get_logger("dashboard")

    if request.method == "GET":
        result = session.get("fb_oauth_result")
        if not result:
            return redirect(url_for("web.oauth_facebook_start"))
        return render_template(
            "pages_v3.html",
            active_page="setup",
            oauth_pages=result.get("pages", []),
            user_token=result.get("user_token"),
            expires_at=result.get("expires_at"),
        )

    try:
        from facebook_oauth import get_page_token, get_instagram_account_for_page
        from flask_login import current_user as _cu
        from app.utils import save_fb_page_for_user

        page_id = request.form.get("page_id")
        page_name = request.form.get("page_name")
        result = session.get("fb_oauth_result")

        if not result or not page_id:
            return redirect(url_for("web.page_setup"))

        page_token = get_page_token(result["user_token"], page_id)

        ig_account_id = ""
        try:
            ig_info = get_instagram_account_for_page(page_id, page_token)
            if ig_info:
                ig_account_id = ig_info.get("instagram_account_id", "")
        except Exception:
            pass

        save_fb_page_for_user(
            user_id=_cu.id,
            page_id=page_id,
            page_name=page_name or "My Page",
            page_token=page_token,
            instagram_account_id=ig_account_id,
            token_expires_in_seconds=int(result.get("expires_in") or 0),
        )
        session.pop("fb_oauth_result", None)
        logger.info("Connected page %s for user %s", page_name, _cu.id)

        # If user came from onboarding, return them there; otherwise dashboard
        next_url = request.args.get("next") or url_for("onboarding.wizard")
        return redirect(next_url)

    except Exception as e:
        logger.error("Page selection error: %s", e)
        return render_template("setup_v3.html", active_page="setup", oauth_error=str(e))
