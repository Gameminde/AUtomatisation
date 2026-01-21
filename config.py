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
    """Create a Supabase client using env vars."""
    from supabase import create_client

    url = require_env("SUPABASE_URL")
    key = require_env("SUPABASE_KEY")
    return create_client(url, key)


def get_logger(name: str) -> logging.Logger:
    """Return a logger that writes to console and a module log file."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_file = LOG_DIR / f"{name}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def load_env(override: bool = False) -> None:
    """Reload environment variables from .env if present."""
    load_dotenv(override=override)
