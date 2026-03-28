"""Content Factory SaaS — Application factory."""

import os
import logging

from flask import Flask, jsonify, request, session
from flask_cors import CORS
from flask_login import LoginManager, current_user
from werkzeug.middleware.proxy_fix import ProxyFix

import config
from app.csrf import CSRFError, CSRFProtect
from models import User
from app.i18n import get_catalog, get_system_dir, normalize_locale, translate
from app.utils import _get_or_create_secret_key

logger = config.get_logger("dashboard")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _init_smart_defaults(app: Flask) -> None:
    """Apply smart scheduling defaults at startup (SQLite only)."""
    DEFAULT_PPD = 3
    DEFAULT_TIMES = config.TARGET_POSTING_PRESETS[config.DEFAULT_COUNTRY_CODE]["posting_times"]
    LEGACY_PPD = 2
    try:
        from database import get_db, SQLiteDB
        db = get_db()
        if not isinstance(db, SQLiteDB):
            return
        db.execute(
            "UPDATE managed_pages SET posts_per_day = CASE WHEN posts_per_day IS NULL OR posts_per_day = ? THEN ? ELSE posts_per_day END, posting_times = ? WHERE posting_times IS NULL",
            (LEGACY_PPD, DEFAULT_PPD, DEFAULT_TIMES),
        )
        db.execute(
            "UPDATE managed_pages SET posts_per_day = ? WHERE posts_per_day IS NULL AND posting_times IS NOT NULL",
            (DEFAULT_PPD,),
        )
        logger.info(
            "Smart defaults initialised (ppd=%d, times=%s; legacy ppd=%d treated as unconfigured)",
            DEFAULT_PPD, DEFAULT_TIMES, LEGACY_PPD,
        )
    except Exception as e:
        logger.warning("Smart defaults init failed: %s", e)


def _get_supabase_rest_client():
    """
    Return the cached Supabase REST service client.

    The auth module (login, register) MUST use Supabase directly — not the
    SQLite fallback — because the `users` and `activation_codes` tables only
    exist in Supabase.  Delegates to the process-level singleton in config.py.
    """
    try:
        return config.get_supabase_service_client()
    except Exception as exc:
        logger.warning("Could not get Supabase REST client: %s", exc)
        return None


def create_app() -> Flask:
    """Application factory — returns a configured Flask app instance."""
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    _app = Flask(
        "content_factory",
        template_folder=os.path.join(_root, "templates"),
        static_folder=os.path.join(_root, "static"),
    )
    _app.secret_key = _get_or_create_secret_key()
    secure_cookies = _env_flag("SESSION_SECURE_COOKIES", default=False)
    trust_proxy_headers = _env_flag("TRUST_PROXY_HEADERS", default=False)
    _app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=secure_cookies,
        REMEMBER_COOKIE_SECURE=secure_cookies,
    )
    if secure_cookies:
        _app.config["PREFERRED_URL_SCHEME"] = "https"
    if trust_proxy_headers:
        _app.wsgi_app = ProxyFix(_app.wsgi_app, x_proto=1, x_host=1)
    CORS(_app)
    csrf = CSRFProtect()
    csrf.init_app(_app)

    # ── Flask-Login ────────────────────────────────────────────────────────
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = ""
    login_manager.init_app(_app)

    @login_manager.user_loader
    def load_user(user_id: str):
        """
        Load a user from Supabase by ID.  Falls back gracefully if Supabase is
        not configured (returns None → unauthenticated).
        """
        try:
            supabase = _get_supabase_rest_client()
            if supabase is None:
                return None
            result = (
                supabase.table("users")
                .select("id, email, is_active")
                .eq("id", user_id)
                .execute()
            )
            if result.data:
                d = result.data[0]
                return User(d["id"], d["email"], d.get("is_active", True))
        except Exception as exc:
            logger.warning("user_loader error: %s", exc)
        return None

    # ── Context processor ──────────────────────────────────────────────────
    @_app.context_processor
    def inject_dashboard_config():
        raw_language = str(session.get("ui_language") or "").strip()
        system_language = normalize_locale(raw_language) if raw_language else ""
        if not system_language and current_user and getattr(current_user, "is_authenticated", False):
            try:
                from app.utils import get_user_settings

                settings = get_user_settings(current_user.id)
                configured_language = str(settings.get("ui_language") or "").strip()
                system_language = normalize_locale(configured_language) if configured_language else ""
                # Cache in session so subsequent requests skip the DB call
                if system_language:
                    session["ui_language"] = system_language
            except Exception as exc:
                logger.warning("Could not resolve session language for %s: %s", current_user.id[:8], exc)
                system_language = ""
        if not system_language:
            system_language = "EN"

        def _t(text, **params):
            return translate(text, system_language, **params)

        return {
            "current_user": current_user,
            "system_language": system_language,
            "system_dir": get_system_dir(system_language),
            "i18n_catalog": get_catalog(),
            "t": _t,
        }

    # ── Register blueprints ────────────────────────────────────────────────
    from app.auth.routes import auth_bp
    from app.dashboard.routes import web_bp
    from app.api.routes import api_bp
    from app.pages.routes import pages_bp
    from app.studio.routes import studio_bp
    from app.settings.routes import settings_bp
    from app.onboarding.routes import onboarding_bp

    _app.register_blueprint(auth_bp)
    _app.register_blueprint(web_bp)
    _app.register_blueprint(api_bp)
    _app.register_blueprint(pages_bp)
    _app.register_blueprint(studio_bp)
    _app.register_blueprint(settings_bp)
    _app.register_blueprint(onboarding_bp)
    csrf.exempt(api_bp)
    csrf.exempt(pages_bp)
    csrf.exempt(studio_bp)
    csrf.exempt(settings_bp)
    csrf.exempt(onboarding_bp)

    @_app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        message = getattr(error, "description", str(error)) or "CSRF token is missing or invalid."
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": message, "code": "csrf_invalid"}), 400
        return message, 400

    # ── Onboarding gate ────────────────────────────────────────────────────
    # Authenticated users who haven't finished onboarding are redirected to
    # /onboarding before reaching any protected page.  API routes, static
    # files, and the auth/onboarding routes themselves are excluded.
    # Setup now happens inline on the dashboard via /api/setup/progress, so
    # authenticated users are no longer redirected to /onboarding.

    # ── Top-level auth aliases (/login → /auth/login etc.) ─────────────────
    # Allows canonical short URLs in links/templates while keeping the blueprint
    # prefix (/auth/*) as the authoritative route for url_for() calls.
    from flask import redirect, url_for as _url_for, send_from_directory

    @_app.route("/design-system")
    def _design_system():
        return send_from_directory(_root, "design_system.html")

    @_app.route("/login")
    def _login_alias():
        return redirect(_url_for("auth.login"))

    @_app.route("/register")
    def _register_alias():
        return redirect(_url_for("auth.register"))

    @_app.route("/logout", methods=["GET", "POST"])
    def _logout_alias():
        if request.method == "POST":
            return redirect(_url_for("auth.logout"), code=307)
        return redirect(_url_for("auth.login"))

    # ── Startup tasks ──────────────────────────────────────────────────────
    with _app.app_context():
        _init_smart_defaults(_app)
        _validate_db_config(_app)

    return _app


def _validate_db_config(app: Flask) -> None:
    """
    Validate that the database/auth backend configuration is consistent.

    Phase 1 (multi-tenant SaaS) requires Supabase for:
      - The `users` table (login sessions / user_loader)
      - The `activation_codes` table (Gumroad registration gate)
      - All tenant data tables (user_id-scoped rows)

    SQLite mode is supported for single-user local development only.
    In SQLite mode the auth endpoints (/auth/login, /auth/register) will
    always fail because the users/activation_codes tables only exist in
    Supabase.  A clear startup warning is logged to surface this early.
    """
    db_mode = os.getenv("DB_MODE", "sqlite").lower()
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()

    if db_mode == "supabase":
        if not supabase_url or not supabase_key:
            logger.error(
                "STARTUP ERROR: DB_MODE=supabase but SUPABASE_URL or SUPABASE_KEY is missing. "
                "Auth and all API routes will fail. Set both in your environment secrets."
            )
        else:
            logger.info(
                "✅ DB mode: Supabase (multi-tenant). "
                "All tenant data and auth routed through %s", supabase_url
            )
    else:
        if supabase_url or supabase_key:
            logger.warning(
                "⚠️  DB_MODE=sqlite but SUPABASE_URL/SUPABASE_KEY are set. "
                "Auth routes require Supabase — set DB_MODE=supabase to enable login."
            )
        else:
            logger.warning(
                "⚠️  DB_MODE=sqlite (single-user dev mode). "
                "Auth (login/register/activation) is DISABLED — Supabase is required for SaaS. "
                "Set SUPABASE_URL, SUPABASE_KEY, and DB_MODE=supabase to enable multi-tenant mode."
            )
