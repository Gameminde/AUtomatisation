"""
Facebook OAuth Handler - One-click Facebook connection for Content Factory v2.0.

Features:
- OAuth 2.0 flow for Facebook Login
- Automatic token retrieval
- Page selection (user chooses which page to post to)
- Long-lived token exchange (60 days)
- Secure token storage with Fernet encryption
- Token expiry alerts

Setup required:
1. Create Facebook App at developers.facebook.com
2. Add "Facebook Login" product
3. Set OAuth redirect URI to: http://localhost:5000/oauth/facebook/callback
4. Copy App ID and App Secret to .env

Usage:
    from facebook_oauth import get_oauth_url, handle_callback, get_user_pages
    
    # Step 1: Get OAuth URL and redirect user
    url = get_oauth_url()
    
    # Step 2: Handle callback with code
    tokens = handle_callback(code)
    
    # Step 3: Get user's pages
    pages = get_user_pages(tokens['access_token'])
    
    # Step 4: Select page and get page access token
    page_token = get_page_token(tokens['access_token'], page_id)
"""

from __future__ import annotations

import os
import json
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

# CRITICAL: Load .env BEFORE any other local imports
load_dotenv()

import config

logger = config.get_logger("facebook_oauth")

# Facebook OAuth config - read AFTER load_dotenv()
FB_APP_ID = os.getenv("FB_APP_ID", "")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
FB_REDIRECT_URI = os.getenv("FB_REDIRECT_URI", "http://localhost:5000/oauth/facebook/callback")

# Debug log at startup
if FB_APP_ID:
    logger.info(f"✅ Facebook OAuth configured: App ID {FB_APP_ID[:6]}...")
else:
    logger.warning("⚠️ Facebook OAuth NOT configured: FB_APP_ID is empty")

# Permissions needed for posting
FB_PERMISSIONS = [
    "pages_show_list",       # List user's pages
    "pages_read_engagement",  # Read page engagement
    "pages_manage_posts",     # Create posts
    "read_insights",          # Analytics support
]

# Token storage
TOKEN_FILE = Path(__file__).parent / ".fb_tokens.json"

# Simple encryption key (in production, use proper key management)
def _get_encryption_key() -> bytes:
    """Get or create encryption key for token storage."""
    key_file = Path(__file__).parent / ".fb_key"
    if key_file.exists():
        return key_file.read_bytes()
    else:
        try:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            return key
        except ImportError:
            # Fallback: use base64 encoding (less secure but works without cryptography)
            return base64.b64encode(b"content-factory-v2-key-123456")


def _encrypt_token(token: str) -> str:
    """Encrypt token for storage."""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_encryption_key())
        return f.encrypt(token.encode()).decode()
    except ImportError:
        # Fallback: simple base64
        return base64.b64encode(token.encode()).decode()


def _decrypt_token(encrypted: str) -> str:
    """Decrypt stored token."""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_get_encryption_key())
        return f.decrypt(encrypted.encode()).decode()
    except ImportError:
        # Fallback: simple base64
        return base64.b64decode(encrypted.encode()).decode()


def get_oauth_url(state: str = "content_factory") -> str:
    """
    Generate Facebook OAuth URL for user authorization.
    
    Args:
        state: State parameter for CSRF protection
    
    Returns:
        URL to redirect user to for Facebook login
    """
    if not FB_APP_ID:
        raise ValueError("FB_APP_ID not configured in .env")
    
    params = {
        "client_id": FB_APP_ID,
        "redirect_uri": FB_REDIRECT_URI,
        "scope": ",".join(FB_PERMISSIONS),
        "response_type": "code",
        "state": state,
    }
    
    url = f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"
    logger.info("Generated OAuth URL for Facebook login")
    return url


def exchange_code_for_token(code: str) -> Dict:
    """
    Exchange authorization code for access token.
    
    Args:
        code: Authorization code from Facebook callback
    
    Returns:
        Dict with access_token, token_type, expires_in
    """
    if not FB_APP_ID or not FB_APP_SECRET:
        raise ValueError("FB_APP_ID and FB_APP_SECRET required")
    
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "redirect_uri": FB_REDIRECT_URI,
        "code": code,
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise ValueError(f"Facebook error: {data['error']['message']}")
        
        logger.info("✅ Exchanged code for access token")
        return data
        
    except requests.RequestException as e:
        logger.error(f"Token exchange failed: {e}")
        raise


def get_long_lived_token(short_token: str) -> Dict:
    """
    Exchange short-lived token for long-lived token (60 days).
    
    Args:
        short_token: Short-lived access token
    
    Returns:
        Dict with access_token, token_type, expires_in
    """
    if not FB_APP_ID or not FB_APP_SECRET:
        raise ValueError("FB_APP_ID and FB_APP_SECRET required")
    
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "fb_exchange_token": short_token,
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise ValueError(f"Facebook error: {data['error']['message']}")
        
        logger.info("✅ Got long-lived token (60 days)")
        return data
        
    except requests.RequestException as e:
        logger.error(f"Long-lived token exchange failed: {e}")
        raise


def get_user_pages(access_token: str) -> List[Dict]:
    """
    Get list of Facebook Pages the user manages.
    
    Args:
        access_token: User's access token
    
    Returns:
        List of page dicts with id, name, access_token
    """
    url = "https://graph.facebook.com/v19.0/me/accounts"
    params = {
        "access_token": access_token,
        "fields": "id,name,access_token,picture",
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        pages = data.get("data", [])
        logger.info(f"✅ Found {len(pages)} managed pages")
        return pages
        
    except requests.RequestException as e:
        logger.error(f"Failed to get user pages: {e}")
        raise


def get_page_token(user_token: str, page_id: str) -> str:
    """
    Get page access token for a specific page.
    
    Args:
        user_token: User's access token
        page_id: Facebook Page ID
    
    Returns:
        Page access token (never expires)
    """
    url = f"https://graph.facebook.com/v19.0/{page_id}"
    params = {
        "access_token": user_token,
        "fields": "access_token",
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        page_token = data.get("access_token")
        if not page_token:
            raise ValueError("No access token returned for page")
        
        logger.info(f"✅ Got page access token for {page_id}")
        return page_token
        
    except requests.RequestException as e:
        logger.error(f"Failed to get page token: {e}")
        raise


def handle_callback(code: str) -> Dict:
    """
    Complete OAuth flow: exchange code → long-lived token → get pages.
    
    Args:
        code: Authorization code from callback
    
    Returns:
        Dict with tokens and pages list
    """
    # Step 1: Exchange code for short-lived token
    token_data = exchange_code_for_token(code)
    short_token = token_data.get("access_token")
    
    # Step 2: Exchange for long-lived token
    long_lived_data = get_long_lived_token(short_token)
    long_token = long_lived_data.get("access_token")
    expires_in = long_lived_data.get("expires_in", 5184000)  # Default 60 days
    
    # Step 3: Get user's pages
    pages = get_user_pages(long_token)
    
    # Step 4: Calculate expiry date
    expiry_date = datetime.now() + timedelta(seconds=expires_in)
    
    result = {
        "user_token": long_token,
        "expires_at": expiry_date.isoformat(),
        "expires_in_days": expires_in // 86400,
        "pages": pages,
    }
    
    logger.info(f"✅ OAuth complete: {len(pages)} pages, expires in {result['expires_in_days']} days")
    return result


def save_tokens(page_id: str, page_name: str, page_token: str, user_token: str, expires_at: str) -> None:
    """
    Save tokens securely to file.
    
    Args:
        page_id: Selected page ID
        page_name: Page name for display
        page_token: Page access token
        user_token: User's long-lived token
        expires_at: Token expiry date ISO string
    """
    data = {
        "page_id": page_id,
        "page_name": page_name,
        "page_token": _encrypt_token(page_token),
        "user_token": _encrypt_token(user_token),
        "expires_at": expires_at,
        "saved_at": datetime.now().isoformat(),
    }
    
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)
    
    # Also update .env for backward compatibility
    env_file = Path(__file__).parent / ".env"
    _update_env_file(env_file, {
        "FACEBOOK_ACCESS_TOKEN": page_token,
        "FACEBOOK_PAGE_ID": page_id,
    })
    
    logger.info(f"✅ Saved tokens for page: {page_name}")


def load_tokens() -> Optional[Dict]:
    """
    Load saved tokens.
    
    Returns:
        Dict with decrypted tokens, or None if not found
    """
    if not TOKEN_FILE.exists():
        return None
    
    try:
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
        
        # Decrypt tokens
        data["page_token"] = _decrypt_token(data["page_token"])
        data["user_token"] = _decrypt_token(data["user_token"])
        
        return data
        
    except Exception as e:
        logger.error(f"Failed to load tokens: {e}")
        return None


def get_token_status() -> Dict:
    """
    Get current token status and expiry info.
    
    Returns:
        Dict with connection status
    """
    tokens = load_tokens()
    
    if not tokens:
        return {
            "connected": False,
            "page_name": None,
            "expires_at": None,
            "days_remaining": None,
            "warning": None,
        }
    
    # Calculate days remaining
    expires_at = datetime.fromisoformat(tokens["expires_at"])
    now = datetime.now()
    days_remaining = (expires_at - now).days
    
    # Check for warnings
    warning = None
    if days_remaining <= 0:
        warning = "Token expired! Please reconnect."
    elif days_remaining <= 7:
        warning = f"Token expires in {days_remaining} days. Consider reconnecting soon."
    
    return {
        "connected": True,
        "page_id": tokens["page_id"],
        "page_name": tokens["page_name"],
        "expires_at": tokens["expires_at"],
        "days_remaining": max(0, days_remaining),
        "warning": warning,
    }


def _update_env_file(env_path: Path, updates: Dict[str, str]) -> None:
    """Update .env file with new values."""
    existing = {}
    
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    existing[key.strip()] = value.strip()
    
    existing.update(updates)
    
    with open(env_path, "w") as f:
        for key, value in existing.items():
            f.write(f"{key}={value}\n")


def test_connection() -> Dict:
    """
    Test if Facebook connection is working.
    
    Returns:
        Dict with test results
    """
    tokens = load_tokens()
    
    if not tokens:
        return {"success": False, "error": "No tokens saved"}
    
    try:
        # Try to get page info
        url = f"https://graph.facebook.com/v19.0/{tokens['page_id']}"
        params = {
            "access_token": tokens["page_token"],
            "fields": "name,followers_count",
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "page_name": data.get("name"),
            "followers": data.get("followers_count", 0),
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def is_configured() -> bool:
    """Check if Facebook OAuth is configured (App ID and Secret set)."""
    # Read dynamically to avoid issues with module import order
    app_id = os.getenv("FB_APP_ID", "")
    app_secret = os.getenv("FB_APP_SECRET", "")
    return bool(app_id and app_secret)


if __name__ == "__main__":
    print("🔐 Facebook OAuth Test\n")
    
    if not is_configured():
        print("❌ Facebook OAuth not configured")
        print("   Set FB_APP_ID and FB_APP_SECRET in .env")
        print("\n   To create a Facebook App:")
        print("   1. Go to developers.facebook.com")
        print("   2. Create new App → Business")
        print("   3. Add 'Facebook Login' product")
        print(f"   4. Set redirect URI: {FB_REDIRECT_URI}")
    else:
        print("✅ Facebook OAuth configured")
        
        status = get_token_status()
        if status["connected"]:
            print(f"   Page: {status['page_name']}")
            print(f"   Expires: {status['days_remaining']} days")
            if status["warning"]:
                print(f"   ⚠️ {status['warning']}")
        else:
            print("   Not connected - use dashboard to connect")
