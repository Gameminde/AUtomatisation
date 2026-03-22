"""Gunicorn entry point for production serving."""

import os
import threading
import time
import logging

from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

_pipeline_log = logging.getLogger("pipeline_scheduler")

PIPELINE_INTERVAL_SECONDS = int(os.getenv("PIPELINE_INTERVAL_SECONDS", "1800"))
PIPELINE_STARTUP_DELAY_SECONDS = int(os.getenv("PIPELINE_STARTUP_DELAY", "90"))


def _pipeline_scheduler_loop() -> None:
    _pipeline_log.info(
        "Pipeline scheduler started — first run in %ds, then every %ds",
        PIPELINE_STARTUP_DELAY_SECONDS,
        PIPELINE_INTERVAL_SECONDS,
    )
    time.sleep(PIPELINE_STARTUP_DELAY_SECONDS)
    while True:
        try:
            from auto_runner import run_all_users
            summary = run_all_users()
            _pipeline_log.info(
                "Pipeline cycle done: users=%d published=%d",
                summary.get("users", 0),
                summary.get("published_total", 0),
            )
        except Exception as exc:
            _pipeline_log.error("Pipeline scheduler error: %s", exc, exc_info=True)
        time.sleep(PIPELINE_INTERVAL_SECONDS)


_scheduler = threading.Thread(
    target=_pipeline_scheduler_loop,
    daemon=True,
    name="pipeline-scheduler",
)
_scheduler.start()
