"""
License Validator — Multi-platform license key verification for Content Factory.

Supports:
    - Gumroad
    - LemonSqueezy
    - Paddle (coming soon)
    - Offline / self-hosted keys

Validates license keys against the chosen platform's API and caches
the result locally so the app works offline after initial activation.

Usage:
    from license_validator import require_license, is_licensed

    # Check at startup
    if not is_licensed():
        activate_or_exit()
"""

from __future__ import annotations

import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import config

logger = config.get_logger("license")

# ── Configuration ───────────────────────────────────────────────────
# Platform: "gumroad", "lemonsqueezy", "paddle", "offline"
LICENSE_PLATFORM = os.getenv("LICENSE_PLATFORM", "gumroad").lower()

# Platform-specific settings
GUMROAD_PRODUCT_ID = os.getenv("GUMROAD_PRODUCT_ID", "YOUR_PRODUCT_PERMALINK")
LEMONSQUEEZY_API_KEY = os.getenv("LEMONSQUEEZY_API_KEY", "")
LEMONSQUEEZY_STORE_ID = os.getenv("LEMONSQUEEZY_STORE_ID", "")
PADDLE_VENDOR_ID = os.getenv("PADDLE_VENDOR_ID", "")
PADDLE_AUTH_CODE = os.getenv("PADDLE_AUTH_CODE", "")

# Offline keys — comma-separated list of pre-approved keys
OFFLINE_KEYS = [k.strip() for k in os.getenv("OFFLINE_VALID_KEYS", "").split(",") if k.strip()]

MAX_ACTIVATIONS = int(os.getenv("LICENSE_MAX_ACTIVATIONS", "3"))
LICENSE_FILE = Path(__file__).parent / ".license"

# Platform API URLs
PLATFORM_URLS = {
    "gumroad": "https://api.gumroad.com/v2/licenses/verify",
    "lemonsqueezy": "https://api.lemonsqueezy.com/v1/licenses/validate",
}

# ── Cache helpers ───────────────────────────────────────────────────


def _fingerprint() -> str:
    """Generate a stable machine fingerprint (non-PII)."""
    import platform
    raw = f"{platform.node()}-{platform.system()}-{os.getenv('USERNAME', os.getenv('USER', 'unknown'))}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_cached_license() -> Optional[Dict]:
    """Load locally cached license data."""
    if not LICENSE_FILE.exists():
        return None
    try:
        data = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
        if data.get("fingerprint") != _fingerprint():
            logger.warning("Machine fingerprint mismatch — re-activation needed")
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _save_license_cache(data: Dict) -> None:
    """Persist license data locally."""
    data["fingerprint"] = _fingerprint()
    data["cached_at"] = datetime.now(timezone.utc).isoformat()
    try:
        LICENSE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("✅ License cached locally")
    except OSError as e:
        logger.warning("Could not cache license: %s", e)


# ── Platform Validators ─────────────────────────────────────────────


def _validate_gumroad(key: str) -> Dict:
    """Verify via Gumroad Licenses API."""
    import requests

    resp = requests.post(
        PLATFORM_URLS["gumroad"],
        data={
            "product_id": GUMROAD_PRODUCT_ID,
            "license_key": key,
            "increment_uses_count": True,
        },
        timeout=15,
    )

    data = resp.json()
    if not data.get("success"):
        return {"valid": False, "reason": "Invalid license key"}

    purchase = data.get("purchase", {})
    if purchase.get("refunded") or purchase.get("chargebacked"):
        return {"valid": False, "reason": "License revoked (refund/chargeback)"}

    uses = data.get("uses", 0)
    if uses > MAX_ACTIVATIONS:
        return {"valid": False, "reason": f"Too many activations ({uses}/{MAX_ACTIVATIONS})"}

    return {
        "valid": True,
        "platform": "gumroad",
        "email": purchase.get("email", ""),
        "license_key": key,
        "created_at": purchase.get("created_at", ""),
        "uses": uses,
    }


def _validate_lemonsqueezy(key: str) -> Dict:
    """Verify via LemonSqueezy Licenses API."""
    import requests

    resp = requests.post(
        PLATFORM_URLS["lemonsqueezy"],
        json={"license_key": key, "instance_name": _fingerprint()},
        headers={"Accept": "application/json"},
        timeout=15,
    )

    data = resp.json()
    if not data.get("valid"):
        meta = data.get("meta", {})
        return {"valid": False, "reason": meta.get("error", "Invalid license key")}

    meta = data.get("meta", {})
    instance = data.get("instance", {})

    return {
        "valid": True,
        "platform": "lemonsqueezy",
        "email": meta.get("customer_email", ""),
        "license_key": key,
        "created_at": instance.get("created_at", ""),
        "product_name": meta.get("product_name", ""),
        "variant_name": meta.get("variant_name", ""),
    }


def _validate_paddle(key: str) -> Dict:
    """Verify via Paddle Licenses API (v1 classic)."""
    import requests

    resp = requests.post(
        "https://vendors.paddle.com/api/2.0/product/verify_license",
        data={
            "vendor_id": PADDLE_VENDOR_ID,
            "vendor_auth_code": PADDLE_AUTH_CODE,
            "license_code": key,
        },
        timeout=15,
    )

    data = resp.json()
    if not data.get("success"):
        return {"valid": False, "reason": data.get("error", {}).get("message", "Invalid key")}

    response = data.get("response", {})
    if response.get("uses", 0) > MAX_ACTIVATIONS:
        return {"valid": False, "reason": f"Too many activations ({response['uses']}/{MAX_ACTIVATIONS})"}

    return {
        "valid": True,
        "platform": "paddle",
        "email": response.get("customer_email", ""),
        "license_key": key,
        "uses": response.get("uses", 0),
    }


def _validate_offline(key: str) -> Dict:
    """Validate against pre-configured offline keys."""
    # Check SHA-256 hash or exact match
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    for valid_key in OFFLINE_KEYS:
        if key == valid_key or key_hash == valid_key:
            return {
                "valid": True,
                "platform": "offline",
                "email": "offline@local",
                "license_key": key[:8] + "****",
            }

    return {"valid": False, "reason": "Invalid offline key"}


# Map platform names to their validators
_VALIDATORS = {
    "gumroad": _validate_gumroad,
    "lemonsqueezy": _validate_lemonsqueezy,
    "lemon": _validate_lemonsqueezy,  # alias
    "paddle": _validate_paddle,
    "offline": _validate_offline,
    "self-hosted": _validate_offline,  # alias
}


# ── Public API ──────────────────────────────────────────────────────


def validate_license(key: str, platform: str = None) -> Dict:
    """
    Verify a license key against the configured platform.

    Args:
        key: The license key.
        platform: Override platform (default: LICENSE_PLATFORM env var).

    Returns:
        {"valid": True/False, "reason": "...", "platform": "...", ...}
    """
    platform = (platform or LICENSE_PLATFORM).lower().strip()
    key = key.strip()

    validator = _VALIDATORS.get(platform)
    if not validator:
        supported = ", ".join(sorted(set(_VALIDATORS.keys()) - {"lemon", "self-hosted"}))
        return {"valid": False, "reason": f"Unsupported platform '{platform}'. Supported: {supported}"}

    try:
        import requests  # noqa: F401 — ensure requests is available
    except ImportError:
        if platform != "offline":
            return {"valid": False, "reason": "requests library not installed — use 'pip install requests'"}

    try:
        result = validator(key)

        if result.get("valid"):
            _save_license_cache(result)
            logger.info("✅ License activated via %s for %s", platform, result.get("email", "unknown"))

        return result

    except Exception as e:
        logger.error("License validation error (%s): %s", platform, e)
        # Fall back to cached license if we can't reach the API
        cached = _load_cached_license()
        if cached and cached.get("valid"):
            logger.info("📦 Using cached license (offline mode)")
            return cached
        return {"valid": False, "reason": f"Verification failed: {e}"}


def is_licensed() -> bool:
    """Check if a valid license is cached locally."""
    cached = _load_cached_license()
    return cached is not None and cached.get("valid", False)


def get_license_info() -> Optional[Dict]:
    """Get cached license info (email, platform, activation date, etc.)."""
    return _load_cached_license()


def deactivate() -> bool:
    """Remove the local license cache (for machine transfer)."""
    try:
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()
            logger.info("🗑️ License deactivated on this machine")
        return True
    except OSError as e:
        logger.error("Could not deactivate: %s", e)
        return False


def require_license() -> None:
    """
    Block execution unless licensed. Used at startup.

    Prompts user for license key via stdin if not cached.
    """
    if is_licensed():
        info = get_license_info()
        logger.info("🔑 Licensed to %s via %s", info.get("email", "unknown"), info.get("platform", "unknown"))
        return

    print("\n" + "=" * 55)
    print("   🔑 Content Factory — License Activation")
    print("=" * 55)
    print(f"\nPlatform: {LICENSE_PLATFORM.title()}")
    print("Enter your license key to activate.\n")

    for attempt in range(3):
        key = input("License key: ").strip()
        if not key:
            continue

        result = validate_license(key)
        if result["valid"]:
            print(f"\n✅ Activated! Welcome, {result.get('email', '')}.")
            print("=" * 55 + "\n")
            return
        else:
            remaining = 2 - attempt
            print(f"\n❌ {result['reason']}")
            if remaining > 0:
                print(f"   {remaining} attempt(s) remaining.\n")

    print("\n🚫 Activation failed. Please check your license key.")
    print("   Support: YOUR_SUPPORT_EMAIL\n")
    raise SystemExit(1)
