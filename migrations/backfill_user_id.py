"""Backfill NULL user_id values for the current single-user Supabase project."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List

from dotenv import load_dotenv


TABLES = [
    "managed_pages",
    "raw_articles",
    "processed_content",
    "scheduled_posts",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill user_id on legacy rows for a single-user project."
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


def _headers(api_key: str, *, count: bool = False, write: bool = False) -> Dict[str, str]:
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if count:
        headers["Prefer"] = "count=exact"
    if write:
        headers["Content-Type"] = "application/json"
        headers["Prefer"] = "return=representation"
    return headers


def _request(
    method: str,
    url: str,
    api_key: str,
    payload: Dict | None = None,
    *,
    count: bool = False,
) -> tuple[int, Dict[str, str], str]:
    data = None
    headers = _headers(api_key, count=count, write=payload is not None)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, headers=headers, data=data, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, dict(response.headers), response.read().decode("utf-8")


def _count_from_headers(headers: Dict[str, str]) -> int:
    content_range = headers.get("Content-Range", "")
    if "/" not in content_range:
        return 0
    return int(content_range.split("/")[-1])


def fetch_users(base_url: str, api_key: str) -> List[Dict]:
    url = f"{base_url}/rest/v1/users?select=id,email,is_active&order=created_at.asc&limit=10"
    _, _, body = _request("GET", url, api_key)
    return json.loads(body) if body else []


def count_null_user_id(base_url: str, api_key: str, table: str) -> int:
    url = f"{base_url}/rest/v1/{table}?select=id&user_id=is.null"
    _, headers, _ = _request("GET", url, api_key, count=True)
    return _count_from_headers(headers)


def backfill_table(base_url: str, api_key: str, table: str, user_id: str) -> int:
    url = f"{base_url}/rest/v1/{table}?user_id=is.null"
    _, _, body = _request("PATCH", url, api_key, payload={"user_id": user_id})
    rows = json.loads(body) if body else []
    return len(rows)


def main() -> int:
    load_dotenv()
    args = parse_args()
    if not args.supabase_url or not args.supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required")

    base_url = args.supabase_url.rstrip("/")
    users = fetch_users(base_url, args.supabase_key)
    if len(users) != 1:
        raise RuntimeError(
            f"Expected exactly 1 row in public.users for safe backfill, found {len(users)}"
        )

    target_user = users[0]
    target_user_id = target_user["id"]
    summary: Dict[str, Dict[str, int | str]] = {
        "target_user": {
            "id": target_user_id,
            "is_active": int(bool(target_user.get("is_active", True))),
        }
    }

    for table in TABLES:
        before = count_null_user_id(base_url, args.supabase_key, table)
        updated = backfill_table(base_url, args.supabase_key, table, target_user_id) if before else 0
        after = count_null_user_id(base_url, args.supabase_key, table)
        summary[table] = {
            "null_user_id_before": before,
            "rows_updated": updated,
            "null_user_id_after": after,
        }

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
