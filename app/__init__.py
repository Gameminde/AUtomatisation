"""Content Factory SaaS — Application factory."""

import os
import logging

from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager, current_user

import config
from models import User
from app.utils import _get_or_create_secret_key

logger = config.get_logger("dashboard")


def _init_smart_defaults(app: Flask) -> None:
    """Apply smart scheduling defaults at startup (SQLite only)."""
    DEFAULT_PPD = 3
    DEFAULT_TIMES = "08:00,13:00,19:00"
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
    Return a raw Supabase REST client using the service key.

    The auth module (login, register) MUST use Supabase directly — not the
    SQLite fallback — because the `users` and `activation_codes` tables only
    exist in Supabase.  This helper bypasses the DB_MODE env var.
    """
    from supabase import create_client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception as exc:
        logger.warning("Could not create Supabase REST client: %s", exc)
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
    CORS(_app)

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
    API_KEY = os.getenv("DASHBOARD_API_KEY", "")

    @_app.context_processor
    def inject_dashboard_config():
        return {"dashboard_api_key": API_KEY, "current_user": current_user}

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

    # ── Onboarding gate ────────────────────────────────────────────────────
    # Authenticated users who haven't finished onboarding are redirected to
    # /onboarding before reaching any protected page.  API routes, static
    # files, and the auth/onboarding routes themselves are excluded.
    _GATE_SKIP_PREFIXES = (
        "/onboarding", "/auth/", "/static/", "/media/",
        "/login", "/register", "/logout", "/design-system",
        "/api/", "/oauth/",
    )

    from flask import request as _req, redirect as _redir, url_for as _ufor, session as _sess
    from flask_login import current_user as _cu
    from app.utils import get_user_settings as _get_us

    @_app.before_request
    def _onboarding_gate():
        path = _req.path
        if any(path.startswith(p) for p in _GATE_SKIP_PREFIXES) or path == "/":
            return None
        if not _cu.is_authenticated:
            return None
        if _sess.get("onboarding_complete"):
            return None
        try:
            settings = _get_us(_cu.id)
            if settings.get("onboarding_complete"):
                _sess["onboarding_complete"] = True
                return None
            _sess["onboarding_complete"] = False
            return _redir(_ufor("onboarding.wizard"))
        except Exception as _exc:
            logger.warning("Onboarding gate check failed: %s", _exc)
            return None

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

    @_app.route("/logout")
    def _logout_alias():
        return redirect(_url_for("auth.logout"))

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
