"""
Instagram Publisher - Publish image posts to Instagram Business accounts.

Uses the Instagram Content Publishing API (Graph API v19.0).

Two-step flow:
1. POST /{ig-user-id}/media  → create media container (returns creation_id)
2. POST /{ig-user-id}/media_publish?creation_id={id} → publish

Requires:
- Instagram Business Account connected to a Facebook Page
- instagram_basic, instagram_content_publish permissions on the Page token

Note: Instagram requires a PUBLICLY accessible image URL (not a local file).
The dashboard serves images via /media/public/<filename> for this purpose.
"""

from __future__ import annotations

import os
import time
from typing import Dict, Optional, Tuple

import requests

import config

logger = config.get_logger("instagram_publisher")

GRAPH_API_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def _graph_url(path: str) -> str:
    return f"{GRAPH_BASE}/{path.lstrip('/')}"


def get_instagram_account_id(page_id: str, page_access_token: str) -> Optional[str]:
    """
    Discover the Instagram Business Account ID linked to a Facebook Page.

    Args:
        page_id: Facebook Page ID
        page_access_token: Page access token

    Returns:
        Instagram Business Account ID or None if not connected
    """
    url = _graph_url(page_id)
    params = {
        "fields": "instagram_business_account",
        "access_token": page_access_token,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        ig_account = data.get("instagram_business_account")
        if ig_account and ig_account.get("id"):
            return ig_account["id"]
        return None
    except Exception as e:
        logger.error("Failed to get Instagram account ID for page %s: %s", page_id, e)
        return None


def create_media_container(
    ig_user_id: str,
    page_access_token: str,
    image_url: str,
    caption: str,
) -> Optional[str]:
    """
    Step 1: Create an Instagram media container.

    Args:
        ig_user_id: Instagram Business Account ID
        page_access_token: Page access token (also valid for IG)
        image_url: Publicly accessible HTTPS URL of the image
        caption: Post caption (text + hashtags)

    Returns:
        Creation ID (container ID) or None on failure
    """
    url = _graph_url(f"{ig_user_id}/media")
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": page_access_token,
    }
    try:
        resp = requests.post(url, data=payload, timeout=60)
        data = resp.json()
        if not resp.ok or "error" in data:
            error_msg = data.get("error", {}).get("message", resp.text)
            logger.error("Instagram media container creation failed: %s", error_msg)
            raise RuntimeError(f"Instagram container error: {error_msg}")
        creation_id = data.get("id")
        if not creation_id:
            raise RuntimeError(f"No creation_id in response: {data}")
        logger.info("Instagram media container created: %s", creation_id)
        return creation_id
    except requests.RequestException as exc:
        raise RuntimeError(f"Instagram create_media_container request failed: {exc}") from exc


def publish_media_container(
    ig_user_id: str,
    page_access_token: str,
    creation_id: str,
) -> str:
    """
    Step 2: Publish the media container to Instagram.

    Args:
        ig_user_id: Instagram Business Account ID
        page_access_token: Page access token
        creation_id: Container ID from step 1

    Returns:
        Instagram post ID

    Raises:
        RuntimeError on API failure
    """
    # Instagram recommends waiting a moment before publishing
    time.sleep(2)

    url = _graph_url(f"{ig_user_id}/media_publish")
    payload = {
        "creation_id": creation_id,
        "access_token": page_access_token,
    }
    try:
        resp = requests.post(url, data=payload, timeout=60)
        data = resp.json()
        if not resp.ok or "error" in data:
            error_msg = data.get("error", {}).get("message", resp.text)
            logger.error("Instagram media_publish failed: %s", error_msg)
            raise RuntimeError(f"Instagram publish error: {error_msg}")
        post_id = data.get("id")
        if not post_id:
            raise RuntimeError(f"No post ID in response: {data}")
        logger.info("Instagram post published: %s", post_id)
        return post_id
    except requests.RequestException as exc:
        raise RuntimeError(f"Instagram media_publish request failed: {exc}") from exc


def get_ig_media_permalink(post_id: str, page_access_token: str) -> str:
    """
    Fetch the public permalink for an Instagram media object via Graph API.

    Returns empty string on failure (non-fatal — permalink is optional).
    """
    try:
        url = _graph_url(post_id)
        resp = requests.get(url, params={"fields": "permalink", "access_token": page_access_token}, timeout=15)
        data = resp.json()
        return data.get("permalink", "")
    except Exception as exc:
        logger.debug("Could not fetch IG permalink for %s: %s", post_id, exc)
        return ""


def publish_photo_to_instagram(
    ig_user_id: str,
    page_access_token: str,
    image_url: str,
    caption: str,
) -> str:
    """
    Full two-step Instagram photo publish flow.

    Args:
        ig_user_id: Instagram Business Account ID
        page_access_token: Page access token
        image_url: Publicly accessible HTTPS image URL
        caption: Post caption

    Returns:
        Instagram post ID

    Raises:
        RuntimeError on failure
    """
    logger.info("Publishing to Instagram (account %s)", ig_user_id)
    creation_id = create_media_container(ig_user_id, page_access_token, image_url, caption)
    post_id = publish_media_container(ig_user_id, page_access_token, creation_id)
    logger.info("Instagram publish complete: %s", post_id)
    return post_id


def get_public_image_url(image_path: str, base_url: str) -> Optional[str]:
    """
    Convert a local image path to a publicly accessible URL.

    The app serves images at /media/public/<filename>.
    base_url should be the public URL of this app (e.g. https://myapp.replit.app).

    Args:
        image_path: Local file path to the image
        base_url: Public base URL of this app

    Returns:
        Public HTTPS URL for the image, or None if path is invalid
    """
    from pathlib import Path
    img = Path(image_path)
    if not img.exists():
        logger.error("Image not found for Instagram: %s", image_path)
        return None
    base_url = base_url.rstrip("/")
    return f"{base_url}/media/public/{img.name}"


def get_app_base_url() -> str:
    """
    Get the public base URL of this app for Instagram image serving.

    Checks, in order:
    1. BASE_URL env var (user-configured, recommended for production)
    2. REPLIT_DEV_DOMAIN env var (Replit dev environment)
    3. Falls back to localhost (won't work for Instagram, but won't crash)
    """
    base_url = os.getenv("BASE_URL", "")
    if base_url:
        return base_url.rstrip("/")

    replit_domain = os.getenv("REPLIT_DEV_DOMAIN", "")
    if replit_domain:
        return f"https://{replit_domain}"

    return "http://localhost:5000"
