"""
license_validator — Gumroad license key validation.
Validates activation codes via Supabase `activation_codes` table.
"""
import os
from typing import Dict, Optional
import config

logger = config.get_logger("license_validator")


def validate_license(license_key: str, platform: Optional[str] = None) -> Dict:
    """
    Validate a license key against the Supabase activation_codes table.
    Returns {"valid": bool, "reason": str, ...}.
    """
    if not license_key:
        return {"valid": False, "reason": "No license key provided"}

    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            logger.warning("Supabase not configured — cannot validate license")
            return {"valid": False, "reason": "License validation requires Supabase configuration"}

        client = create_client(url, key)
        result = (
            client.table("activation_codes")
            .select("id, code, used, platform")
            .eq("code", license_key)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"valid": False, "reason": "License key not found"}

        code_row = rows[0]
        if code_row.get("used"):
            return {"valid": False, "reason": "License key already used"}

        if platform and code_row.get("platform") and code_row["platform"] != platform:
            return {"valid": False, "reason": "License key is for a different platform"}

        return {"valid": True, "reason": "ok", "code_id": code_row["id"]}

    except Exception as e:
        logger.error("License validation error: %s", e)
        return {"valid": False, "reason": str(e)}


def is_licensed() -> bool:
    """Check if the app has a valid license (basic check)."""
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))


def get_license_info() -> Optional[Dict]:
    """Return basic license info."""
    if not is_licensed():
        return None
    return {"email": "", "uses": 0, "plan": "gumroad"}
