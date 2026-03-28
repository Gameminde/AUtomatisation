"""Encrypt plaintext managed_pages.access_token values in Supabase.

This script uses the same Fernet helpers as app/utils.py so the runtime can
decrypt migrated tokens without any further transformation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List

from cryptography.fernet import Fernet
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def get_fernet_key() -> bytes:
    """Mirror app/utils.py resolution order exactly."""
    env_key = os.getenv("FERNET_KEY", "").strip()
    if env_key:
        return env_key.encode()

    key_file = ROOT / ".fernet_key"
    if key_file.exists():
        return key_file.read_bytes().strip()

    new_key = Fernet.generate_key()
    key_file.write_bytes(new_key)
    return new_key


def encrypt_value(plaintext: str) -> str:
    return Fernet(get_fernet_key()).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    return Fernet(get_fernet_key()).decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Encrypt plaintext managed_pages.access_token values in Supabase."
    )
    parser.add_argument(
        "--supabase-url",
        default=os.getenv("SUPABASE_URL", ""),
        help="Supabase project URL. Defaults to SUPABASE_URL env var.",
    )
    parser.add_argument(
        "--supabase-key",
        default=os.getenv("SUPABASE_KEY", ""),
        help="Supabase service-role or secret key. Defaults to SUPABASE_KEY env var.",
    )
    return parser.parse_args()


def _headers(api_key: str, extra: Dict[str, str] | None = None) -> Dict[str, str]:
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def _request(
    method: str,
    url: str,
    api_key: str,
    payload: Dict | None = None,
) -> tuple[int, str]:
    data = None
    headers: Dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Prefer"] = "return=representation"
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=_headers(api_key, headers),
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, response.read().decode("utf-8")


def fetch_all_pages(base_url: str, api_key: str) -> List[Dict]:
    limit = 1000
    offset = 0
    rows: List[Dict] = []
    while True:
        path = (
            f"{base_url}/rest/v1/managed_pages?"
            "select=id,page_id,page_name,access_token"
            f"&order=id.asc&limit={limit}&offset={offset}"
        )
        _, body = _request("GET", path, api_key)
        batch = json.loads(body) if body else []
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def update_access_token(base_url: str, api_key: str, row_id: str, access_token: str) -> None:
    path = (
        f"{base_url}/rest/v1/managed_pages?"
        f"id=eq.{urllib.parse.quote(row_id)}"
    )
    _request("PATCH", path, api_key, payload={"access_token": access_token})


def is_fernet_encrypted(value: str) -> bool:
    if not value:
        return False
    try:
        decrypt_value(value)
        return True
    except Exception:
        return False


def main() -> int:
    load_dotenv()
    args = parse_args()
    if not args.supabase_url or not args.supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")

    # Ensure the runtime Fernet key exists before we write anything.
    key = get_fernet_key()
    print(f"Fernet key ready: length={len(key)} bytes; source={'env' if os.getenv('FERNET_KEY') else '.fernet_key'}")

    pages = fetch_all_pages(args.supabase_url.rstrip("/"), args.supabase_key)
    encrypted = 0
    already_encrypted = 0
    skipped_empty = 0

    for row in pages:
        token = row.get("access_token") or ""
        if not token:
            skipped_empty += 1
            continue
        if is_fernet_encrypted(token):
            already_encrypted += 1
            continue
        update_access_token(
            args.supabase_url.rstrip("/"),
            args.supabase_key,
            row["id"],
            encrypt_value(token),
        )
        encrypted += 1

    verify_rows = fetch_all_pages(args.supabase_url.rstrip("/"), args.supabase_key)
    verify_plaintext = 0
    verify_decrypt_ok = 0
    for row in verify_rows:
        token = row.get("access_token") or ""
        if not token:
            continue
        if is_fernet_encrypted(token):
            verify_decrypt_ok += 1
        else:
            verify_plaintext += 1

    print(
        json.dumps(
            {
                "managed_pages_total": len(pages),
                "encrypted_now": encrypted,
                "already_encrypted": already_encrypted,
                "skipped_empty": skipped_empty,
                "verify_decrypt_ok": verify_decrypt_ok,
                "verify_plaintext_remaining": verify_plaintext,
            },
            indent=2,
        )
    )
    return 0 if verify_plaintext == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
