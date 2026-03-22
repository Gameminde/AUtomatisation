"""
Content Factory — entry point.

All application logic lives in the `app/` package.
This file exists only to start the server and provide a top-level `app`
object so `python dashboard_app.py` and `gunicorn wsgi:app` both work.
"""

import logging
import os

from dotenv import load_dotenv

# Load .env BEFORE importing anything else
load_dotenv()

from app import create_app  # noqa: E402

app = create_app()

_log = logging.getLogger("dashboard_app")


def _start_pipeline_scheduler() -> None:
    """Start the APScheduler-based multi-tenant pipeline scheduler."""
    try:
        from tasks.runner import start_scheduler
        start_scheduler()
    except Exception as exc:
        _log.error("Could not start pipeline scheduler: %s", exc, exc_info=True)


def _start_telegram_bot() -> None:
    """Start the Telegram bot polling thread (no-op if token not set)."""
    try:
        from tasks.telegram_bot import start_telegram_bot
        start_telegram_bot()
    except Exception as exc:
        _log.warning("Telegram bot could not start: %s", exc)


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    print("=" * 60)
    print("Content Factory SaaS Dashboard")
    print("=" * 60)
    print(f"Starting server on http://localhost:{port}")
    print(f"Debug mode: {debug}")

    # Start background pipeline only in the main process (not reloader forks)
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        _start_pipeline_scheduler()
        _start_telegram_bot()

    app.run(host="0.0.0.0", port=port, debug=debug)
