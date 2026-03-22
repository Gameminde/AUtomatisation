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
        logger.info("Smart defaults initialised (ppd=%d, times=%s; legacy ppd=%d treated as unconfigured)", DEFAULT_PPD, DEFAULT_TIMES, LEGACY_PPD)
    except Exception as e:
        logger.warning("Smart defaults init failed: %s", e)


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
        try:
            client = config.get_supabase_client()
            result = (
                client.table("users")
                .select("id, email, is_active")
                .eq("id", user_id)
                .execute()
            )
            if result.data:
                d = result.data[0]
                return User(d["id"], d["email"], d.get("is_active", True))
        except Exception:
            pass
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

    _app.register_blueprint(auth_bp)
    _app.register_blueprint(web_bp)
    _app.register_blueprint(api_bp)

    # ── Startup tasks ──────────────────────────────────────────────────────
    with _app.app_context():
        _init_smart_defaults(_app)

    return _app
