"""Shared configuration and helpers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Load .env by default for local development
load_dotenv()

# Environment keys
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# v2.1: Approval Workflow Mode
APPROVAL_MODE = os.getenv("APPROVAL_MODE", "off").lower() == "on"

# OpenRouter API (multi-key failover)
OPENROUTER_API_KEYS = [
    os.getenv("OPENROUTER_API_KEY_1", ""),
    os.getenv("OPENROUTER_API_KEY_2", ""),
    os.getenv("OPENROUTER_API_KEY_3", ""),
]
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")

HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))
REQUEST_SLEEP_SECONDS = float(os.getenv("REQUEST_SLEEP_SECONDS", "2"))

DEFAULT_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "blockchain",
    "startup",
    "innovation",
    "software",
    "robotics",
]

TARGET_TIMEZONES = {
    "US_EST": "America/New_York",
    "US_PST": "America/Los_Angeles",
    "UK_GMT": "Europe/London",
}


def require_env(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def get_supabase_client():
    """
    Get database client (SQLite by default, Supabase if configured).
    
    This is the main entry point for database access in Content Factory v2.0.
    - Default: SQLite (local, no account needed)
    - Optional: Supabase (cloud, needs SUPABASE_URL and SUPABASE_KEY)
    
    Set DB_MODE=supabase in .env to use Supabase.
    """
    from database import get_db
    return get_db()


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger that writes to:
    - Console (colored output)
    - Module-specific log file (e.g., logs/scraper.log)
    - Master log file (logs/pipeline.log) for all events

    Features:
    - Automatic log rotation (5MB max, keep 3 backups)
    - Detailed timestamp format
    - Statistics tracking
    """
    from logging.handlers import RotatingFileHandler

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Detailed formatter for files
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-15s | %(funcName)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Compact formatter for console
    console_formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Module-specific log file with rotation (5MB max, keep 3 backups)
    log_file = LOG_DIR / f"{name}.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"  # 5MB
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)

    # Master pipeline log (all modules write here)
    master_log = LOG_DIR / "pipeline.log"
    master_handler = RotatingFileHandler(
        master_log, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"  # 10MB
    )
    master_handler.setFormatter(file_formatter)
    master_handler.setLevel(logging.INFO)

    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(console_formatter)
    stream_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(master_handler)
    logger.addHandler(stream_handler)

    return logger


def log_stats() -> dict:
    """Read and return statistics from log files."""
    stats = {"total_errors": 0, "total_warnings": 0, "total_info": 0, "modules": {}}

    for log_file in LOG_DIR.glob("*.log"):
        if log_file.name == "pipeline.log":
            continue

        module = log_file.stem
        stats["modules"][module] = {"errors": 0, "warnings": 0, "info": 0}

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "| ERROR" in line:
                        stats["modules"][module]["errors"] += 1
                        stats["total_errors"] += 1
                    elif "| WARNING" in line:
                        stats["modules"][module]["warnings"] += 1
                        stats["total_warnings"] += 1
                    elif "| INFO" in line:
                        stats["modules"][module]["info"] += 1
                        stats["total_info"] += 1
        except Exception:
            pass

    return stats


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def load_env(override: bool = False) -> None:
    """Reload environment variables from .env if present."""
    load_dotenv(override=override)
