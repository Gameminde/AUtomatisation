"""Gunicorn entry point for production serving.

Background workers are started separately:
- ``python -m tasks.runner``
- ``python -m tasks.telegram_bot``
"""

# .env is loaded automatically by config.py at module import time.

from app import create_app

app = create_app()
