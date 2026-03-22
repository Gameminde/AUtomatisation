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

    _app.register_blueprint(auth_bp)
    _app.register_blueprint(web_bp)
    _app.register_blueprint(api_bp)
    _app.register_blueprint(pages_bp)
    _app.register_blueprint(studio_bp)
    _app.register_blueprint(settings_bp)

    # ── Startup tasks ──────────────────────────────────────────────────────
    with _app.app_context():
        _init_smart_defaults(_app)

    return _app
