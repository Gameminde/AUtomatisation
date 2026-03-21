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
        .select("id,content_id,scheduled_time,status,platforms")
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
    # Insert into published_posts with explicit per-platform status
    client.table("published_posts").insert(
        {
            "content_id": content_id,
            "facebook_post_id": post_id,
            "facebook_status": "published",
            "platforms": "facebook",
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

        # ── Determine platform targets for this scheduled row ──────────
        platforms_field = (item.get("platforms") or "facebook").lower()
        publish_to_facebook = "facebook" in platforms_field
        publish_to_instagram = "instagram" in platforms_field

        # ── Build message text (shared across platforms) ───────────────
        arabic_text = content.get("arabic_text", "")
        image_path = content.get("image_path", "")
        hashtags = content.get("hashtags", [])
        hashtag_str = " ".join(hashtags) if hashtags else ""

        if arabic_text and image_path and os.path.exists(image_path):
            cta_ar = "ما رأيكم؟ شاركونا في التعليقات! 💬"
            message = f"{arabic_text}\n\n{cta_ar}\n\n{hashtag_str}".strip()
        else:
            hook = content.get("hook", "")
            body = content.get("generated_text", "")
            cta = content.get("call_to_action", "")
            message = f"{hook}\n\n{body}\n\n{cta}\n\n{hashtag_str}".strip()

        # ── Per-platform results (tracked independently) ───────────────
        fb_post_id: str = ""
        fb_ok: bool = False
        ig_ok: bool = False

        # ── Facebook publish (isolated try — does NOT block IG) ────────
        if publish_to_facebook:
            try:
                if image_path and os.path.exists(image_path):
                    logger.info("📷 Publishing to Facebook with image: %s", image_path)
                    fb_post_id = publish_photo_post(message, image_path)
                else:
                    logger.info("📝 Publishing text-only to Facebook")
                    fb_post_id = publish_text_post(message)

                mark_published(content["id"], fb_post_id)
                record_publication(content["id"], fb_post_id)
                fb_ok = True
                logger.info("✅ Published %s -> FB: %s", content_id[:8], fb_post_id)
            except Exception as fb_exc:
                logger.error("❌ Facebook publish failed for %s: %s", content_id[:8], fb_exc)
                action, error_code = error_handler.classify_error(fb_exc)
                retry_count = content.get("retry_count", 0)
                error_handler.execute_action(action, content_id, error_code, retry_count)
                # Persist facebook_status='failed' so the UI can show it
                try:
                    from database import get_db
                    db = get_db()
                    with db.get_connection() as conn:
                        conn.execute(
                            "INSERT INTO published_posts (content_id, facebook_status, platforms)"
                            " VALUES (?, 'failed', 'facebook')",
                            (content["id"],),
                        )
                except Exception:
                    pass

        # ── Instagram publish (isolated — does NOT depend on FB) ─────
        ig_error: str = ""
        if publish_to_instagram:
            ig_result = _publish_to_instagram_if_configured(content, fb_post_id)
            ig_ok = ig_result["success"]
            ig_error = ig_result.get("error") or ""
            if not ig_ok:
                logger.warning("⚠️ Instagram publish failed for %s: %s", content_id[:8], ig_error)
            # Persist instagram_status='failed' when IG was selected but failed
            if not ig_ok and ig_error:
                try:
                    client = config.get_supabase_client()
                    if fb_post_id:
                        client.table("published_posts").update(
                            {"instagram_status": "failed"}
                        ).eq("content_id", content["id"]).eq(
                            "facebook_post_id", fb_post_id
                        ).execute()
                except Exception:
                    pass

        # ── Update content status & schedule row based on outcomes ─────
        any_ok = fb_ok or ig_ok
        if any_ok:
            # At least one platform succeeded — mark as published
            if publish_to_instagram and not publish_to_facebook:
                # IG-only: mirror mark_published lifecycle
                try:
                    config.get_supabase_client().table("processed_content").update(
                        {"status": "published"}
                    ).eq("id", content["id"]).execute()
                except Exception as state_err:
                    logger.warning("Could not update content status for IG-only post: %s", state_err)

            # Partial failure still counts as published (at least one succeeded)
            final_status = "published"
            error_handler.update_success_status(content["id"])
            published += 1
            logger.info(
                "📊 %s: FB=%s IG=%s → schedule=%s",
                content_id[:8],
                "✓" if fb_ok else ("skip" if not publish_to_facebook else "✗"),
                "✓" if ig_ok else ("skip" if not publish_to_instagram else "✗"),
                final_status,
            )
        else:
            # All selected platforms failed — mark as failed
            final_status = "failed"
            logger.error("❌ All platforms failed for %s", content_id[:8])

        update_schedule_status(schedule_id, final_status)

        # Rate limiting pause
        time.sleep(config.REQUEST_SLEEP_SECONDS)

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


def _publish_to_instagram_if_configured(content: Dict, fb_post_id: str) -> Dict:
    """
    Attempt to publish content to Instagram.
    Always returns a structured result dict — never raises.

    Returns:
        {"success": bool, "post_id": str|None, "error": str|None}
    """
    from facebook_oauth import load_tokens, get_instagram_account_for_page
    from instagram_publisher import publish_photo_to_instagram, get_public_image_url, get_app_base_url

    def _fail(reason: str) -> Dict:
        logger.warning("Instagram publish skipped/failed: %s", reason)
        return {"success": False, "post_id": None, "error": reason}

    tokens = load_tokens()
    if not tokens:
        return _fail("no Facebook tokens configured")

    page_id = tokens.get("page_id")
    page_token = tokens.get("page_token")

    # Use stored IG account ID first, fall back to live discovery
    ig_user_id = tokens.get("instagram_account_id", "")
    if not ig_user_id:
        ig_info = get_instagram_account_for_page(page_id, page_token)
        if not ig_info:
            return _fail("no Instagram Business Account linked to this Facebook Page")
        ig_user_id = ig_info["instagram_account_id"]

    image_path = content.get("image_path", "")
    if not image_path:
        return _fail("no image available (Instagram requires an image)")

    base_url = get_app_base_url()
    image_url = get_public_image_url(image_path, base_url)
    if not image_url:
        return _fail(f"image file missing: {image_path}")

    # Build caption
    arabic_text = content.get("arabic_text", "")
    hook = content.get("hook", "")
    body = content.get("generated_text", "")
    cta = content.get("call_to_action", "")
    hashtags = " ".join(content.get("hashtags") or [])
    caption = (arabic_text or f"{hook}\n\n{body}\n\n{cta}").strip()
    if hashtags:
        caption = f"{caption}\n\n{hashtags}"

    try:
        ig_post_id = publish_photo_to_instagram(ig_user_id, page_token, image_url, caption)
    except Exception as api_err:
        return _fail(str(api_err))

    logger.info("✅ Instagram publish %s -> IG: %s", content["id"][:8], ig_post_id)

    # Update/create published_posts row with IG post ID + per-platform status
    try:
        client = config.get_supabase_client()
        if fb_post_id:
            # Cross-post: update existing FB row
            row = (
                client.table("published_posts")
                .select("id, platforms")
                .eq("content_id", content["id"])
                .eq("facebook_post_id", fb_post_id)
                .limit(1)
                .execute()
            )
            if row.data:
                existing_platforms = row.data[0].get("platforms", "facebook")
                combined = "facebook,instagram" if "facebook" in existing_platforms else "instagram"
                client.table("published_posts").update({
                    "instagram_post_id": ig_post_id,
                    "instagram_status": "published",
                    "platforms": combined,
                }).eq("id", row.data[0]["id"]).execute()
        else:
            # IG-only: insert new row
            import uuid as _uuid
            client.table("published_posts").insert({
                "id": str(_uuid.uuid4()),
                "content_id": content["id"],
                "instagram_post_id": ig_post_id,
                "instagram_status": "published",
                "platforms": "instagram",
            }).execute()
    except Exception as db_err:
        logger.warning("Could not update published_posts with Instagram post ID: %s", db_err)

    return {"success": True, "post_id": ig_post_id, "error": None}


if __name__ == "__main__":
    from process_lock import acquire_global_lock, release_global_lock
    
    if acquire_global_lock():
        try:
            publish_due_posts()
        finally:
            release_global_lock()
    else:
        logger.warning("🚫 Automation already running (lock held). Exiting.")
