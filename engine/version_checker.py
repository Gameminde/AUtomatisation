"""version_checker — App version update checker stub."""
import config

APP_VERSION = "2.1.1"

logger = config.get_logger("version_checker")


def check_for_update() -> dict:
    return {"current": APP_VERSION, "latest": APP_VERSION, "available": False, "release_notes": ""}
