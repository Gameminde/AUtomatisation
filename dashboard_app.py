"""
Content Factory — entry point.

All application logic lives in the `app/` package.
This file exists only to start the server and provide a top-level `app`
object so `python dashboard_app.py` and `gunicorn wsgi:app` both work.
"""

import os
from dotenv import load_dotenv

# Load .env BEFORE importing anything else
load_dotenv()

from app import create_app  # noqa: E402

app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    print("=" * 60)
    print("🚀 Content Factory SaaS Dashboard")
    print("=" * 60)
    print(f"🌐 Starting server on http://localhost:{port}")
    print(f"📊 Debug mode: {debug}")

    app.run(host="0.0.0.0", port=port, debug=debug)
