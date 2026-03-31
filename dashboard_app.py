"""
Content Factory — entry point.

All application logic lives in the `app/` package.
This file exists only to start the server and provide a top-level `app`
object so `python dashboard_app.py` and `gunicorn wsgi:app` both work.
Background workers must be started separately.
"""

import os

# .env is loaded automatically by config.py at module import time.
# No explicit load_dotenv() needed here.

from app import create_app  # noqa: E402

app = create_app()
app.config['LOGIN_DISABLED'] = True


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    print("=" * 60)
    print("Content Factory SaaS Dashboard")
    print("=" * 60)
    print(f"Starting server on http://localhost:{port}")
    print(f"Debug mode: {debug}")
    print("Background workers: start separately via `python -m tasks.runner` and `python -m tasks.telegram_bot`")

    app.run(host="0.0.0.0", port=port, debug=debug)
