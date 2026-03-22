"""Gunicorn entry point for production serving."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

_log = logging.getLogger("wsgi")


def _start_pipeline_scheduler() -> None:
    """Start the APScheduler-based multi-tenant pipeline scheduler."""
    try:
        from tasks.runner import start_scheduler
        start_scheduler()
    except Exception as exc:
        _log.error("Could not start pipeline scheduler: %s", exc, exc_info=True)


_start_pipeline_scheduler()
