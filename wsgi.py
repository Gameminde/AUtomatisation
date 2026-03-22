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


def _start_telegram_bot() -> None:
    """Start the Telegram bot polling thread (no-op if token not set)."""
    try:
        from tasks.telegram_bot import start_telegram_bot
        start_telegram_bot()
    except Exception as exc:
        _log.warning("Telegram bot could not start: %s", exc)


_start_pipeline_scheduler()
_start_telegram_bot()
