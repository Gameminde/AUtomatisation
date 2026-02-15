"""Version checker — non-blocking remote update check.

Set UPDATE_CHECK_URL to a JSON endpoint returning:
    {"latest": "2.2.0", "changelog": "...", "download_url": "..."}

Disable entirely with DISABLE_UPDATE_CHECK=true.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

import requests

import config

logger = config.get_logger("version_checker")

CURRENT_VERSION = "2.1.1"
UPDATE_CHECK_URL = os.environ.get(
    "UPDATE_CHECK_URL",
    "",  # No default — must be configured by vendor
)
DISABLED = os.environ.get("DISABLE_UPDATE_CHECK", "false").lower() == "true"


def _parse_version(v: str) -> tuple:
    """Parse '2.1.1' into (2, 1, 1) for comparison."""
    try:
        return tuple(int(p) for p in v.strip().split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def check_for_update() -> Dict:
    """
    Check whether a newer version is available.

    Returns:
        Dict with keys: available (bool), current, latest, changelog, download_url.
        On error returns available=False silently.
    """
    result: Dict = {
        "available": False,
        "current": CURRENT_VERSION,
        "latest": CURRENT_VERSION,
        "changelog": "",
        "download_url": "",
    }

    if DISABLED or not UPDATE_CHECK_URL:
        return result

    try:
        resp = requests.get(UPDATE_CHECK_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        latest = data.get("latest", CURRENT_VERSION)
        result["latest"] = latest
        result["changelog"] = data.get("changelog", "")
        result["download_url"] = data.get("download_url", "")
        result["available"] = _parse_version(latest) > _parse_version(CURRENT_VERSION)

        if result["available"]:
            logger.info("🆕 Update available: %s → %s", CURRENT_VERSION, latest)

    except Exception as e:
        logger.debug("Update check failed (non-critical): %s", e)

    return result


if __name__ == "__main__":
    print(f"Current version: {CURRENT_VERSION}")
    info = check_for_update()
    if info["available"]:
        print(f"Update available: {info['latest']}")
        print(f"Changelog: {info['changelog']}")
    else:
        print("You are up to date." if UPDATE_CHECK_URL else "No update URL configured.")
