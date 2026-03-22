"""
engine package — automation and publishing pipeline modules.

Phase-1 structure: the core engine files are gathered here as a package.
All root-level engine modules are re-exported for backward compatibility so
that existing imports continue to work unchanged.

Engine modules included:
  - publisher       Content publishing to Facebook/Instagram
  - scheduler       Post scheduling logic
  - scraper         RSS/article scraping
  - ai_generator    AI content generation
  - gemini_client   Google Gemini / OpenRouter AI client
  - auto_runner     Main pipeline runner
  - rate_limiter    Facebook API rate limiting
  - ban_detector    Shadowban detection
  - analytics_tracker  Engagement syncing
  - instagram_publisher  Instagram Graph API publisher
  - facebook_oauth  Facebook OAuth helpers
"""

import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _lazy(module_name: str):
    """Return a lazy import proxy for a root-level engine module."""
    import importlib
    return importlib.import_module(module_name)


def get_publisher():
    return _lazy("publisher")


def get_scheduler():
    return _lazy("scheduler")


def get_scraper():
    return _lazy("scraper")


def get_ai_generator():
    return _lazy("ai_generator")


def get_gemini_client():
    return _lazy("gemini_client")


def get_auto_runner():
    return _lazy("auto_runner")


def get_rate_limiter():
    return _lazy("rate_limiter").get_rate_limiter()


def get_ban_detector():
    return _lazy("ban_detector").get_detector()


def get_analytics_tracker():
    return _lazy("analytics_tracker")


def get_instagram_publisher():
    return _lazy("instagram_publisher")


def get_facebook_oauth():
    return _lazy("facebook_oauth")
