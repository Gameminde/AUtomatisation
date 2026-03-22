"""Shared utilities for the Content Factory app."""

import os
import secrets as _secrets
from functools import wraps
from pathlib import Path
from typing import Dict, Tuple

from flask import jsonify
from flask_login import current_user


def api_login_required(f):
    """Decorator for JSON API routes: returns 401 JSON instead of redirect."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


def _get_or_create_secret_key() -> str:
    """Auto-generate and persist a Flask secret key on first run."""
    env_key = os.getenv("FLASK_SECRET_KEY", "")
    if env_key:
        return env_key
    secret_file = Path(__file__).parent.parent / ".flask_secret"
    if secret_file.exists():
        return secret_file.read_text().strip()
    new_key = _secrets.token_hex(32)
    try:
        secret_file.write_text(new_key)
    except OSError:
        pass
    return new_key


def _read_env_file() -> Tuple[Path, Dict[str, str]]:
    env_path = Path(__file__).parent.parent / ".env"
    existing: Dict[str, str] = {}
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    existing[key] = val
    return env_path, existing


def _write_env_file(env_path: Path, data: Dict[str, str]) -> None:
    with open(env_path, "w", encoding="utf-8") as f:
        for key, val in data.items():
            f.write(f"{key}={val}\n")
