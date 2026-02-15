"""
Publisher Module - Publish content to Facebook with duplicate prevention.

Features:
- Text post publishing
- Photo post publishing
- Reel/video publishing
- Duplicate prevention via PublicationTracker
- Retry logic for transient failures
- Rate limiting compliance

Author: Content Factory Team
Version: 2.0.0
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Dict, Optional

import requests

import config
from retry_utils import retry_with_backoff  # noqa: F401 - available for future use
from publication_tracker import can_publish_content, record_publication, get_tracker
from rate_limiter import can_post_now
from ban_detector import should_pause_automation
import error_handler  # v2.1: Smart Retry

logger = config.get_logger("publisher")


GRAPH_API_VERSION = "v19.0"


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{path.lstrip('/')}"


def publish_text_post(message: str) -> str:
    access_token = config.require_env("FACEBOOK_ACCESS_TOKEN")
    page_id = config.require_env("FACEBOOK_PAGE_ID")
    url = _graph_url(f"{page_id}/feed")
    payload = {"message": message, "access_token": access_token}
    try:
        resp = requests.post(url, data=payload, timeout=config.HTTP_TIMEOUT_SECONDS)
        if not resp.ok:
            # Log detailed Facebook error
            error_info = resp.json() if resp.text else {"error": resp.text}
            logger.error("Facebook API error: %s", error_info)
            raise RuntimeError(f"Facebook post failed: {resp.status_code} - {error_info}")
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Facebook post failed: {exc}") from exc
    data = resp.json()
    post_id = data.get("id")
    if not post_id:
        raise RuntimeError("Facebook response missing post id")
    return post_id


def publish_photo_post(message: str, image_path: str) -> str:
    """
    Publish a post with a photo to Facebook.

    Args:
        message: Caption for the photo
        image_path: Local path to the image file

    Returns:
        Post ID
    """
    access_token = config.require_env("FACEBOOK_ACCESS_TOKEN")
    page_id = config.require_env("FACEBOOK_PAGE_ID")
    url = _graph_url(f"{page_id}/photos")

    try:
        with open(image_path, "rb") as image_file:
            files = {"source": image_file}
            data = {
                "message": message,
                "access_token": access_token,
            }
            resp = requests.post(url, data=data, files=files, timeout=60)
            resp.raise_for_status()
    except FileNotFoundError:
        raise RuntimeError(f"Image not found: {image_path}")
    except requests.RequestException as exc:
        raise RuntimeError(f"Facebook photo post failed: {exc}") from exc

    result = resp.json()
    post_id = result.get("post_id") or result.get("id")
    if not post_id:
        raise RuntimeError(f"Facebook response missing post id: {result}")

    logger.info("Published photo post: %s", post_id)
    return post_id


# Note: Reel publishing removed in v2.0 (Gumroad simplified version)
# Focus on photo posts with Arabic text for maximum engagement


def fetch_due_posts(limit: int = 5):
    client = config.get_supabase_client()
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    response = (
        client.table("scheduled_posts")
        .select("id,content_id,scheduled_time,status")
        .lte("scheduled_time", now)
        .eq("status", "scheduled")
        .order("scheduled_time")
        .limit(limit)
        .execute()
    )
    return response.data or []


def fetch_content(content_id: str) -> Optional[Dict]:
    client = config.get_supabase_client()
    response = (
        client.table("processed_content")
        .select("id,post_type,generated_text,script_for_reel,hook,call_to_action,hashtags,image_path,arabic_text")
        .eq("id", content_id)
        .single()
        .execute()
    )
    return response.data


def mark_published(content_id: str, post_id: str) -> None:
    client = config.get_supabase_client()
    # Insert into published_posts
    client.table("published_posts").insert(
        {
            "content_id": content_id,
            "facebook_post_id": post_id,
        }
    ).execute()
    
    # v2.1.1: Also save fb_post_id to processed_content (anti double-publish)
    client.table("processed_content").update({
        "fb_post_id": post_id,
        "status": "published"
    }).eq("id", content_id).execute()


def update_schedule_status(schedule_id: str, status: str) -> None:
    client = config.get_supabase_client()
    client.table("scheduled_posts").update({"status": status}).eq("id", schedule_id).execute()


def cas_update_content_status(content_id: str, expected_status: str, new_status: str) -> bool:
    """
    v2.1.1: Compare-And-Swap update for thread-safe state transitions.
    
    Only updates if current status matches expected_status.
    Returns True if update was successful, False if someone else changed the status.
    """
    client = config.get_supabase_client()
    
    result = client.table("processed_content").update({
        "status": new_status
    }).eq("id", content_id).eq("status", expected_status).execute()
    
    # If no rows were updated, someone else changed the status
    if not result.data:
        logger.debug("CAS failed for %s: expected=%s, new=%s", content_id[:8], expected_status, new_status)
        return False
    
    return True


def publish_due_posts(limit: int = 5) -> int:
    """
    Publish scheduled posts that are due.

    Features:
    - Checks for duplicates before publishing
    - Records publications to prevent re-publishing
    - Handles failures gracefully
    - Adaptive rate limiting based on page maturity
    - Auto-pause on shadowban detection

    Args:
        limit: Maximum posts to publish in this run

    Returns:
        Number of posts successfully published
    """
    # v2.1.1: Process retries first
    try:
        from scheduler import process_retries
        process_retries()
    except Exception as e:
        logger.warning(f"Retry processing failed: {e}")

    # Check for shadowban before publishing
    if should_pause_automation():
        logger.warning("🛑 Automation paused due to shadowban detection")
        return 0
    
    # v2.1: Check for cooldown mode
    if error_handler.is_in_cooldown():
        logger.warning("🛑 System in cooldown mode - skipping publish")
        return 0
    
    # Check rate limits
    can_post, reason = can_post_now()
    if not can_post:
        logger.warning(f"⏸️ Rate limit: {reason}")
        return 0
    
    due_posts = fetch_due_posts(limit=limit)
    published = 0
    skipped = 0

    for item in due_posts:
        schedule_id = item["id"]
        content_id = item["content_id"]

        # Check if content can be published (duplicate check)
        can_publish, reason = can_publish_content(content_id)
        if not can_publish:
            logger.warning("⏭️ Skipping %s: %s", content_id[:8], reason)
            update_schedule_status(schedule_id, "failed")  # Use 'failed' as 'skipped' is not in DB constraint
            skipped += 1
            continue

        content = fetch_content(content_id)
        if not content:
            logger.error("Content not found: %s", content_id)
            update_schedule_status(schedule_id, "failed")
            continue
        
        # v2.1.1: Anti Double-Publish - skip API if already posted
        existing_fb_post_id = content.get("fb_post_id")
        if existing_fb_post_id:
            logger.warning("⏭️ Skipping %s: already posted as %s (anti double-publish)", content_id[:8], existing_fb_post_id)
            update_schedule_status(schedule_id, "published")
            published += 1
            continue
        
        # v2.1.1: CAS transition to 'publishing' (thread-safe)
        # Accept both 'scheduled' and 'media_ready' statuses (process_retries may have just updated)
        content_status = content.get("status", "")
        if content_status not in ["scheduled", "media_ready", "retry_scheduled"]:
            logger.warning("⏭️ Skipping %s: status is '%s' (not schedulable)", content_id[:8], content_status)
            skipped += 1
            continue
        
        if not cas_update_content_status(content_id, content_status, "publishing"):
            logger.warning("⏭️ Skipping %s: CAS failed (another process may have claimed it)", content_id[:8])
            skipped += 1
            continue

        try:
            if content["post_type"] == "text":
                # Check if we have Arabic text (preferred for Arab audience)
                arabic_text = content.get("arabic_text", "")
                image_path = content.get("image_path", "")
                hashtags = content.get("hashtags", [])
                hashtag_str = " ".join(hashtags) if hashtags else ""

                # Use Arabic text when available (matches image text)
                if arabic_text and image_path and os.path.exists(image_path):
                    # Arabic post with image - use Arabic text as main message
                    cta_ar = "ما رأيكم؟ شاركونا في التعليقات! 💬"
                    message = f"{arabic_text}\n\n{cta_ar}\n\n{hashtag_str}".strip()
                    logger.info("📷🇸🇦 Publishing ARABIC post with image")
                    post_id = publish_photo_post(message, image_path)
                else:
                    # Fallback to English content
                    hook = content.get("hook", "")
                    body = content.get("generated_text", "")
                    cta = content.get("call_to_action", "")
                    message = f"{hook}\n\n{body}\n\n{cta}\n\n{hashtag_str}".strip()

                    if image_path and os.path.exists(image_path):
                        logger.info("📷 Publishing with image: %s", image_path)
                        post_id = publish_photo_post(message, image_path)
                    else:
                        logger.info("📝 Publishing text-only post")
                        post_id = publish_text_post(message)
            else:
                # v2.0: All content is photo posts (Reels removed for simplicity)
                logger.warning("Unknown post type - treating as text post")
                hook = content.get("hook", "")
                body = content.get("generated_text", "")
                cta = content.get("call_to_action", "")
                hashtags = content.get("hashtags", [])
                hashtag_str = " ".join(hashtags) if hashtags else ""
                message = f"{hook}\n\n{body}\n\n{cta}\n\n{hashtag_str}".strip()
                
                image_path = content.get("image_path", "")
                if image_path and os.path.exists(image_path):
                    post_id = publish_photo_post(message, image_path)
                else:
                    post_id = publish_text_post(message)

            # Record successful publication
            mark_published(content["id"], post_id)
            record_publication(content["id"], post_id)  # Update tracker
            update_schedule_status(schedule_id, "published")
            
            # v2.1: Update success status in error_handler
            error_handler.update_success_status(content["id"])

            published += 1
            logger.info("✅ Published %s -> FB: %s", content_id[:8], post_id)

            # Rate limiting pause
            time.sleep(config.REQUEST_SLEEP_SECONDS)

        except Exception as exc:
            logger.error("❌ Publish failed for %s: %s", schedule_id, exc)
            
            # v2.1: Smart error handling
            action, error_code = error_handler.classify_error(exc)
            retry_count = content.get("retry_count", 0) if content else 0
            should_retry = error_handler.execute_action(action, content_id, error_code, retry_count)
            
            if not should_retry:
                update_schedule_status(schedule_id, "failed")

    logger.info("📊 Publishing complete: %d published, %d skipped", published, skipped)
    return published


def publish_with_duplicate_check(content_id: str) -> Optional[str]:
    """
    Publish a specific content item with duplicate checking.

    Args:
        content_id: Content ID to publish

    Returns:
        Facebook post ID if successful, None otherwise
    """
    # Check if can publish
    can_publish, reason = can_publish_content(content_id)
    if not can_publish:
        logger.warning("Cannot publish %s: %s", content_id[:8], reason)
        return None

    content = fetch_content(content_id)
    if not content:
        logger.error("Content not found: %s", content_id)
        return None

    try:
        if content["post_type"] == "text":
            hook = content.get("hook", "")
            body = content.get("generated_text", "")
            cta = content.get("call_to_action", "")
            message = f"{hook}\n\n{body}\n\n{cta}"
            post_id = publish_text_post(message)
        else:
            logger.warning("Only text posts supported currently")
            return None

        # Record publication
        mark_published(content_id, post_id)
        record_publication(content_id, post_id)

        logger.info("✅ Published %s -> FB: %s", content_id[:8], post_id)
        return post_id

    except Exception as exc:
        logger.error("❌ Publish failed: %s", exc)
        return None


def publish_content_by_id(content_id: str) -> Dict:
    """
    Publish a specific content by ID - for dashboard API.
    
    Args:
        content_id: UUID of content to publish
    
    Returns:
        Dict with success status and details
    """
    try:
        # Check rate limiter
        can_post, reason = can_post_now()
        if not can_post:
            return {"success": False, "error": f"Rate limited: {reason}"}
        
        # Check ban detector
        if should_pause_automation():
            return {"success": False, "error": "Automation paused due to potential shadowban"}
        
        # Fetch content
        content = fetch_content(content_id)
        if not content:
            return {"success": False, "error": "Content not found"}
            
        # v2.1.1: Anti Double-Publish - skip API if already posted
        existing_fb_post_id = content.get("fb_post_id")
        if existing_fb_post_id:
            logger.warning("⏭️ Skipping %s: already posted as %s (anti double-publish)", content_id[:8], existing_fb_post_id)
            return {"success": True, "post_id": existing_fb_post_id, "note": "Already published"}
        
        # v2.1.1: CAS transition to 'publishing' (thread-safe)
        # Note: manual publish can bypass 'scheduled' state check if forcing, but for safety let's respect it
        # Or better: check if status is valid for publishing
        if content.get("status") not in ["scheduled", "waiting_approval", "media_ready", "drafted", "failed", "retry_scheduled"]:
             return {"success": False, "error": f"Invalid status for publishing: {content.get('status')}"}
             
        # Manually transition to publishing (no strict CAS on 'scheduled' here as dashboard can force publish)
        # But we should still lock it
        client = config.get_supabase_client()
        client.table("processed_content").update({"status": "publishing"}).eq("id", content_id).execute()
        
        # Build message
        hook = content.get("hook", "")
        body = content.get("generated_text", "")
        cta = content.get("call_to_action", "")
        hashtags = " ".join(content.get("hashtags", []))
        message = f"{hook}\n\n{body}\n\n{cta}\n\n{hashtags}"
        
        # Publish based on type
        image_path = content.get("image_path")  # Use image_path from DB (canvas)
        
        if image_path and os.path.exists(image_path):
            post_id = publish_photo_post(message, image_path)
        else:
            post_id = publish_text_post(message)
        
        if post_id:
            # Record publication (mark_published handles status update to 'published')
            mark_published(content_id, post_id)
            record_publication(content_id, post_id)
            
            # v2.1: Success status
            error_handler.update_success_status(content_id)
            
            logger.info("✅ Published content %s -> FB: %s", content_id[:8], post_id)
            return {"success": True, "post_id": post_id, "facebook_url": f"https://facebook.com/{post_id}"}
        else:
            # Revert status if failed (mark_published not called)
            client.table("processed_content").update({"status": "failed"}).eq("id", content_id).execute()
            return {"success": False, "error": "Facebook API returned no post ID"}
            
    except Exception as e:
        logger.error("❌ Publish error: %s", e)
        # Revert status if failed
        try:
            config.get_supabase_client().table("processed_content").update({"status": "failed", "last_error": str(e)}).eq("id", content_id).execute()
        except:
            pass
        return {"success": False, "error": str(e)}


def get_publication_status() -> Dict:
    """Get current publication status and stats."""
    tracker = get_tracker()
    return tracker.get_publication_stats()


if __name__ == "__main__":
    from process_lock import acquire_global_lock, release_global_lock
    
    if acquire_global_lock():
        try:
            publish_due_posts()
        finally:
            release_global_lock()
    else:
        logger.warning("🚫 Automation already running (lock held). Exiting.")
