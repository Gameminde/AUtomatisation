"""
Content Factory — entry point.

All application logic lives in the `app/` package.
This file exists only to start the server and provide a top-level `app`
object so `python dashboard_app.py` and `gunicorn wsgi:app` both work.
"""

import logging
import os
import threading
import time

from dotenv import load_dotenv

# Load .env BEFORE importing anything else
load_dotenv()

from app import create_app  # noqa: E402

app = create_app()

_pipeline_log = logging.getLogger("pipeline_scheduler")

PIPELINE_INTERVAL_SECONDS = int(os.getenv("PIPELINE_INTERVAL_SECONDS", "1800"))
PIPELINE_STARTUP_DELAY_SECONDS = int(os.getenv("PIPELINE_STARTUP_DELAY", "90"))


def _pipeline_scheduler_loop() -> None:
    """
    Background daemon thread: run the automation pipeline for all active
    tenants every PIPELINE_INTERVAL_SECONDS (default 30 min).

    A startup delay gives the Flask app time to finish booting before the
    first pipeline run hits the database.
    """
    _pipeline_log.info(
        "Pipeline scheduler started — first run in %ds, then every %ds",
        PIPELINE_STARTUP_DELAY_SECONDS,
        PIPELINE_INTERVAL_SECONDS,
    )
    time.sleep(PIPELINE_STARTUP_DELAY_SECONDS)

    while True:
        try:
            from auto_runner import run_all_users  # noqa: PLC0415 — lazy import intentional
            summary = run_all_users()
            _pipeline_log.info(
                "Pipeline cycle done: users=%d published=%d",
                summary.get("users", 0),
                summary.get("published_total", 0),
            )
        except Exception as exc:
            _pipeline_log.error("Pipeline scheduler error: %s", exc, exc_info=True)

        time.sleep(PIPELINE_INTERVAL_SECONDS)


def _start_pipeline_scheduler() -> None:
    """Start the background pipeline thread if not already running."""
    thread = threading.Thread(
        target=_pipeline_scheduler_loop,
        daemon=True,
        name="pipeline-scheduler",
    )
    thread.start()
    _pipeline_log.info("Background pipeline scheduler thread started (daemon=True)")


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

    app.run(host="0.0.0.0", port=port, debug=debug)
