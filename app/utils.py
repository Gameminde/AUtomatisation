"""Shared utilities for the Content Factory app."""

import logging
import os
import secrets as _secrets
from functools import wraps
from pathlib import Path
from typing import Dict, Optional, Tuple

from flask import jsonify
from flask_login import current_user


def api_login_required(f):
    """
    Auth guard for JSON API routes — the API-endpoint equivalent of Flask-Login's
    @login_required decorator.

    Flask-Login's built-in @login_required redirects unauthenticated requests to the
    login page (HTML redirect), which is appropriate for browser page routes but wrong
    for JSON API consumers who expect a 401 status code and a JSON error body.

    This decorator checks current_user.is_authenticated (the same Flask-Login session
    check used by @login_required) and returns {"error": "..."} / 401 instead of a
    redirect, preserving correct API semantics while sharing the same auth backend.
    """
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


# ── Fernet encryption helpers ───────────────────────────────────────────────

def get_fernet_key() -> bytes:
    """
    Return a 32-byte Fernet key.

    Resolution order:
    1. FERNET_KEY environment variable (production / Replit secret)
    2. .fernet_key file in the project root (dev fallback — auto-generated)
    """
    env_key = os.getenv("FERNET_KEY", "").strip()
    if env_key:
        return env_key.encode()

    key_file = Path(__file__).parent.parent / ".fernet_key"
    if key_file.exists():
        return key_file.read_bytes().strip()

    from cryptography.fernet import Fernet
    new_key = Fernet.generate_key()
    try:
        key_file.write_bytes(new_key)
    except OSError:
        pass
    return new_key


def encrypt_value(plaintext: str) -> str:
    """Fernet-encrypt a string and return a URL-safe base64 token."""
    from cryptography.fernet import Fernet
    f = Fernet(get_fernet_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """Fernet-decrypt a token previously produced by encrypt_value()."""
    from cryptography.fernet import Fernet
    f = Fernet(get_fernet_key())
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")


# ── Supabase client helper ──────────────────────────────────────────────────

def _get_supabase_client():
    """Return a Supabase service-role client (bypasses RLS)."""
    from supabase import create_client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set.")
    return create_client(url, key)


# ── user_settings helpers ───────────────────────────────────────────────────

def get_user_settings(user_id: str) -> Dict:
    """
    Load the user_settings row for the given user.
    Returns an empty dict if no row exists yet.
    """
    try:
        sb = _get_supabase_client()
        result = (
            sb.table("user_settings")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]
    except Exception:
        pass
    return {}


def upsert_user_settings(user_id: str, updates: Dict) -> bool:
    """
    Upsert (insert or update) user_settings for the given user.
    Only the keys present in `updates` are written.
    """
    try:
        sb = _get_supabase_client()
        payload = {"user_id": user_id, **updates}
        sb.table("user_settings").upsert(payload, on_conflict="user_id").execute()
        return True
    except Exception as exc:
        import logging
        logging.getLogger("utils").error("upsert_user_settings failed: %s", exc)
        return False


def load_tokens_for_user(user_id: str) -> Optional[Dict]:
    """
    Load the active Facebook page token for a user from `managed_pages`.
    Returns a dict compatible with the legacy `load_tokens()` signature:
    {"page_id": ..., "page_token": ..., "instagram_account_id": ...}
    or None if no active page is found.
    """
    try:
        sb = _get_supabase_client()
        result = (
            sb.table("managed_pages")
            .select("page_id, page_name, access_token, instagram_account_id, status")
            .eq("user_id", user_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        row = result.data[0]
        encrypted_token = row.get("access_token") or ""
        page_token = decrypt_value(encrypted_token) if encrypted_token else ""
        return {
            "page_id": row["page_id"],
            "page_name": row.get("page_name", ""),
            "page_token": page_token,
            "instagram_account_id": row.get("instagram_account_id") or "",
            "user_token": page_token,
        }
    except Exception as exc:
        logging.getLogger("utils").error("load_tokens_for_user failed: %s", exc)
        return None


def get_gemini_key_for_user(user_id: str) -> Optional[str]:
    """
    Return the decrypted Gemini API key for a user from user_settings.
    Falls back to the GEMINI_API_KEY env var if no per-user key is stored.
    This is what the engine should call instead of reading config.GEMINI_API_KEY.
    """
    try:
        settings = get_user_settings(user_id)
        encrypted = settings.get("gemini_api_key")
        if encrypted:
            return decrypt_value(encrypted)
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "") or None


def save_fb_page_for_user(
    user_id: str,
    page_id: str,
    page_name: str,
    page_token: str,
    instagram_account_id: str = "",
) -> bool:
    """
    Save a Facebook page access token to managed_pages, scoped to user_id.
    The token is Fernet-encrypted before storage.
    """
    try:
        sb = _get_supabase_client()
        encrypted_token = encrypt_value(page_token)
        existing = (
            sb.table("managed_pages")
            .select("id")
            .eq("page_id", page_id)
            .eq("user_id", user_id)
            .execute()
        )
        payload: Dict = {
            "page_id": page_id,
            "page_name": page_name,
            "access_token": encrypted_token,
            "user_id": user_id,
            "status": "active",
        }
        if instagram_account_id:
            payload["instagram_account_id"] = instagram_account_id

        if existing.data:
            sb.table("managed_pages").update(payload).eq("page_id", page_id).eq("user_id", user_id).execute()
        else:
            sb.table("managed_pages").insert(payload).execute()
        return True
    except Exception as exc:
        import logging
        logging.getLogger("utils").error("save_fb_page_for_user failed: %s", exc)
        return False
