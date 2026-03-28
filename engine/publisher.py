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

import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

import config
from retry_utils import retry_with_backoff  # noqa: F401 - available for future use
from publication_tracker import can_publish_content, record_publication, get_tracker
from rate_limiter import can_post_now
from ban_detector import should_pause_automation
import error_handler  # v2.1: Smart Retry

logger = config.get_logger("publisher")


GRAPH_API_VERSION = "v19.0"
AUTO_PUBLISHABLE_FORMATS = {"post", "carousel"}
DRAFT_ONLY_FORMATS = {"story_sequence", "reel_script"}


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{path.lstrip('/')}"


def _normalize_post_type(post_type: Optional[str]) -> str:
    candidate = str(post_type or "post").strip().lower()
    if candidate in {"text", "photo"}:
        return "post"
    return candidate


def _coerce_hashtags(raw_value) -> List[str]:
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return [token.strip() for token in raw_value.split() if token.strip().startswith("#")]
    return []


def _parse_structured_payload(content: Dict) -> Dict:
    generated_text = content.get("generated_text")
    if isinstance(generated_text, dict):
        return generated_text
    if not isinstance(generated_text, str):
        return {}
    stripped = generated_text.strip()
    if not stripped.startswith("{"):
        return {}
    try:
        payload = json.loads(stripped)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _build_standard_message(content: Dict) -> str:
    hashtags = _coerce_hashtags(content.get("hashtags"))
    hashtag_str = " ".join(hashtags) if hashtags else ""
    arabic_text = content.get("arabic_text", "")
    image_path = content.get("image_path", "")
    if arabic_text and image_path and os.path.exists(image_path):
        cta_ar = "ما رأيكم؟ شاركونا في التعليقات! 💬"
        return f"{arabic_text}\n\n{cta_ar}\n\n{hashtag_str}".strip()

    hook = content.get("hook", "")
    body = content.get("generated_text", "")
    cta = content.get("call_to_action", "")
    return f"{hook}\n\n{body}\n\n{cta}\n\n{hashtag_str}".strip()


def _get_brand_color(user_id: Optional[str]) -> str:
    if not user_id:
        return "#F9C74F"
    try:
        from app.utils import get_user_settings

        settings = get_user_settings(user_id) or {}
        return str(settings.get("brand_color") or "#F9C74F")
    except Exception:
        return "#F9C74F"


def _draft_format_label(post_type: str) -> str:
    if post_type == "story_sequence":
        return "story"
    if post_type == "reel_script":
        return "reel"
    return post_type


def _mark_content_draft_ready(content_id: str, schedule_id: str, user_id: Optional[str]) -> None:
    client = config.get_database_client()
    content_query = client.table("processed_content").update({"status": "draft_ready"}).eq("id", content_id)
    schedule_query = client.table("scheduled_posts").update({"status": "draft_ready"}).eq("id", schedule_id)
    if user_id:
        content_query = content_query.eq("user_id", user_id)
        schedule_query = schedule_query.eq("user_id", user_id)
    content_query.execute()
    schedule_query.execute()


def _notify_draft_ready(user_id: Optional[str], post_type: str) -> None:
    if not user_id:
        return
    try:
        from tasks.telegram_bot import telegram_notify_draft_ready

        telegram_notify_draft_ready(user_id, _draft_format_label(post_type))
    except Exception as exc:
        logger.debug("Draft-ready notification skipped: %s", exc)


def _resolve_facebook_credentials(
    access_token: str = "",
    page_id: str = "",
) -> tuple[str, str]:
    """
    Resolve Facebook credentials for low-level publish helpers.

    Explicit parameters always win. Legacy single-user callers can still rely on
    env vars. Multi-tenant flows should pass credentials explicitly.
    """
    resolved_token = access_token or config.require_env("FACEBOOK_ACCESS_TOKEN")
    resolved_page_id = page_id or config.require_env("FACEBOOK_PAGE_ID")
    return resolved_token, resolved_page_id


def publish_text_post(
    message: str,
    access_token: str = "",
    page_id: str = "",
) -> str:
    access_token, page_id = _resolve_facebook_credentials(access_token, page_id)
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


def publish_photo_post(
    message: str,
    image_path: str,
    access_token: str = "",
    page_id: str = "",
) -> str:
    """
    Publish a post with a photo to Facebook.

    Args:
        message: Caption for the photo
        image_path: Local path to the image file
        access_token: Page access token (falls back to env var)
        page_id: Facebook page ID (falls back to env var)

    Returns:
        Post ID
    """
    access_token, page_id = _resolve_facebook_credentials(access_token, page_id)
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


def publish_carousel_post(
    caption: str,
    slides: List[Dict],
    access_token: str = "",
    page_id: str = "",
    user_id: Optional[str] = None,
) -> str:
    """Publish a Facebook carousel by uploading unpublished images first."""
    access_token, page_id = _resolve_facebook_credentials(access_token, page_id)
    if not slides:
        raise RuntimeError("Carousel publish failed: no slides were provided.")

    from engine.image_generator import generate_carousel_placeholder, generate_carousel_slide

    brand_color = _get_brand_color(user_id)
    uploaded_media_ids: List[str] = []

    for index, slide in enumerate(slides[:5], start=1):
        slide_number = int(slide.get("slide_number") or index)
        headline = str(slide.get("headline") or "").strip() or f"Slide {slide_number}"
        body = str(slide.get("body") or "").strip()

        try:
            slide_path = generate_carousel_slide(
                headline=headline,
                body=body,
                slide_number=slide_number,
                brand_color=brand_color,
            )
        except Exception as exc:
            logger.warning("Carousel slide generation failed for slide %s: %s", slide_number, exc)
            slide_path = generate_carousel_placeholder(
                headline=headline,
                slide_number=slide_number,
                brand_color=brand_color,
            )

        upload_url = _graph_url(f"{page_id}/photos")
        try:
            with open(slide_path, "rb") as image_file:
                resp = requests.post(
                    upload_url,
                    data={"published": "false", "access_token": access_token},
                    files={"source": image_file},
                    timeout=60,
                )
                resp.raise_for_status()
        except FileNotFoundError as exc:
            raise RuntimeError(f"Carousel slide image not found: {slide_path}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Facebook carousel image upload failed: {exc}") from exc

        upload_result = resp.json()
        media_id = upload_result.get("id")
        if not media_id:
            raise RuntimeError(f"Facebook carousel upload missing media id: {upload_result}")
        uploaded_media_ids.append(media_id)

    feed_payload = {"message": caption, "access_token": access_token}
    for index, media_id in enumerate(uploaded_media_ids):
        feed_payload[f"attached_media[{index}]"] = json.dumps({"media_fbid": media_id})

    try:
        resp = requests.post(_graph_url(f"{page_id}/feed"), data=feed_payload, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Facebook carousel publish failed: {exc}") from exc

    result = resp.json()
    post_id = result.get("id")
    if not post_id:
        raise RuntimeError(f"Facebook carousel publish missing post id: {result}")
    logger.info("Published carousel post: %s", post_id)
    return post_id


def publish_reel(
    video_url: str,
    description: str,
    access_token: str = "",
    page_id: str = "",
) -> str:
    """
    Backward-compatible Reel/video publish helper.

    The current product focuses on text/photo workflows, but keeping this thin
    wrapper preserves older automation entry points and tests.
    """
    access_token, page_id = _resolve_facebook_credentials(access_token, page_id)
    url = _graph_url(f"{page_id}/videos")
    payload = {
        "file_url": video_url,
        "description": description,
        "access_token": access_token,
    }
    try:
        resp = requests.post(url, data=payload, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Facebook reel post failed: {exc}") from exc

    data = resp.json()
    post_id = data.get("id")
    if not post_id:
        raise RuntimeError(f"Facebook response missing post id: {data}")
    return post_id


def fetch_due_posts(limit: int = 5, user_id: Optional[str] = None):
    """Return scheduled posts that are due, optionally scoped to a single tenant."""
    client = config.get_database_client()
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    query = (
        client.table("scheduled_posts")
        .select("id,content_id,scheduled_time,status,platforms,user_id")
        .lte("scheduled_time", now)
        .eq("status", "scheduled")
        .order("scheduled_time")
        .limit(limit)
    )
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.execute()
    return response.data or []


def fetch_content(content_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
    client = config.get_database_client()
    query = (
        client.table("processed_content")
        .select("id,post_type,generated_text,hook,call_to_action,hashtags,image_path,arabic_text,status,fb_post_id")
        .eq("id", content_id)
    )
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.single().execute()
    return response.data


def mark_published(content_id: str, post_id: str, user_id: Optional[str] = None) -> None:
    client = config.get_database_client()
    insert_data = {
        "content_id": content_id,
        "facebook_post_id": post_id,
        "facebook_status": "published",
        "platforms": "facebook",
    }
    if user_id:
        insert_data["user_id"] = user_id
    existing_query = client.table("published_posts").select("id").eq(
        "facebook_post_id", post_id
    )
    if user_id:
        existing_query = existing_query.eq("user_id", user_id)
    existing = existing_query.limit(1).execute()
    if existing.data:
        update_query = client.table("published_posts").update(insert_data).eq(
            "id", existing.data[0]["id"]
        )
        update_query.execute()
    else:
        client.table("published_posts").insert(insert_data).execute()

    # v2.1.1: Also save fb_post_id to processed_content (anti double-publish)
    update_query = client.table("processed_content").update({
        "fb_post_id": post_id,
        "status": "published"
    }).eq("id", content_id)
    if user_id:
        update_query = update_query.eq("user_id", user_id)
    update_query.execute()


def update_schedule_status(schedule_id: str, status: str, user_id: Optional[str] = None) -> None:
    client = config.get_database_client()
    query = client.table("scheduled_posts").update({"status": status}).eq("id", schedule_id)
    if user_id:
        query = query.eq("user_id", user_id)
    query.execute()


def cas_update_content_status(content_id: str, expected_status: str, new_status: str,
                              user_id: Optional[str] = None) -> bool:
    """
    v2.1.1: Compare-And-Swap update for thread-safe state transitions.
    Optionally scoped to a tenant (user_id) for multi-tenant safety.
    Only updates if current status matches expected_status.
    Returns True if update was successful, False if someone else changed the status.
    """
    client = config.get_database_client()
    query = client.table("processed_content").update({
        "status": new_status
    }).eq("id", content_id).eq("status", expected_status)
    if user_id:
        query = query.eq("user_id", user_id)
    result = query.execute()
    if not result.data:
        logger.debug("CAS failed for %s: expected=%s, new=%s", content_id[:8], expected_status, new_status)
        return False
    return True


def publish_due_posts(limit: int = 5, user_id: Optional[str] = None) -> int:
    """
    Publish scheduled posts that are due.

    Args:
        limit: Maximum posts to publish in this run
        user_id: Tenant ID — only publish this user's scheduled posts.
                 When None the function is unsafe for multi-tenant use; always
                 pass current_user.id from the request context.

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
    if should_pause_automation(user_id=user_id):
        logger.warning("🛑 Automation paused due to shadowban detection")
        return 0

    # v2.1: Check for cooldown mode
    if error_handler.is_in_cooldown():
        logger.warning("🛑 System in cooldown mode - skipping publish")
        return 0

    # Check rate limits
    can_post, reason = can_post_now(user_id=user_id)
    if not can_post:
        logger.warning(f"⏸️ Rate limit: {reason}")
        return 0

    due_posts = fetch_due_posts(limit=limit, user_id=user_id)
    published = 0
    skipped = 0

    for item in due_posts:
        schedule_id = item["id"]
        content_id = item["content_id"]
        # Use the user_id embedded in the scheduled row as the tenant scope
        row_user_id = item.get("user_id") or user_id

        # Check if content can be published (duplicate check)
        can_publish, reason = can_publish_content(content_id, user_id=row_user_id)
        if not can_publish:
            logger.warning("⏭️ Skipping %s: %s", content_id[:8], reason)
            update_schedule_status(schedule_id, "failed", user_id=row_user_id)
            skipped += 1
            continue

        content = fetch_content(content_id, user_id=row_user_id)
        if not content:
            logger.error("Content not found: %s", content_id)
            update_schedule_status(schedule_id, "failed", user_id=row_user_id)
            continue

        normalized_post_type = _normalize_post_type(content.get("post_type"))
        if normalized_post_type in DRAFT_ONLY_FORMATS:
            logger.info("Content %s is draft-only (%s); marking draft_ready", content_id[:8], normalized_post_type)
            _mark_content_draft_ready(content_id, schedule_id, row_user_id)
            _notify_draft_ready(row_user_id, normalized_post_type)
            skipped += 1
            continue
        if normalized_post_type not in AUTO_PUBLISHABLE_FORMATS:
            logger.warning("Skipping %s: unknown post_type=%s", content_id[:8], content.get("post_type"))
            update_schedule_status(schedule_id, "failed", user_id=row_user_id)
            skipped += 1
            continue

        # v2.1.1: Anti Double-Publish - skip API if already posted
        existing_fb_post_id = content.get("fb_post_id")
        if existing_fb_post_id:
            logger.warning("⏭️ Skipping %s: already posted as %s (anti double-publish)", content_id[:8], existing_fb_post_id)
            update_schedule_status(schedule_id, "published", user_id=row_user_id)
            published += 1
            continue

        # v2.1.1: CAS transition to 'publishing' (thread-safe)
        # "approved" = post that has already passed Telegram approval and is
        # ready to publish without re-gating (distinct from "scheduled" which
        # has not yet been approved when approval_mode is enabled).
        content_status = content.get("status") or "scheduled"
        _APPROVAL_BYPASS_STATUSES = {"approved"}
        _SCHEDULABLE_STATUSES = {
            "drafted",
            "scheduled",
            "media_ready",
            "retry_scheduled",
            "approved",
        }
        if content_status not in _SCHEDULABLE_STATUSES:
            logger.warning("⏭️ Skipping %s: status is '%s' (not schedulable)", content_id[:8], content_status)
            skipped += 1
            continue

        if not cas_update_content_status(content_id, content_status, "publishing", user_id=row_user_id):
            logger.warning("⏭️ Skipping %s: CAS failed (another process may have claimed it)", content_id[:8])
            skipped += 1
            continue

        # ── Approval-mode gate ─────────────────────────────────────────
        # Only gate content that has NOT already been through approval.
        # content_status=="approved" means the user (or auto-approve) already
        # reviewed this post — skip the gate and publish directly.
        _skip_approval_gate = content_status in _APPROVAL_BYPASS_STATUSES
        if row_user_id and not _skip_approval_gate:
            try:
                from app.utils import _get_supabase_client as _sb_fn
                _sb = _sb_fn()
                _settings_res = (
                    _sb.table("user_settings")
                    .select("approval_mode")
                    .eq("user_id", row_user_id)
                    .limit(1)
                    .execute()
                )
                _approval_mode = (
                    _settings_res.data[0].get("approval_mode", False)
                    if _settings_res.data
                    else False
                )
            except Exception:
                _approval_mode = False

            if _approval_mode:
                # Build preview text
                _preview_text = (
                    content.get("arabic_text")
                    or content.get("generated_text")
                    or ""
                )
                # Revert status to pending_approval and send approval request.
                # Set approval_requested_at to now so auto-approve fires 4h
                # from this moment (not from content creation time).
                try:
                    from datetime import datetime as _dt, timezone as _tz
                    _now_iso = _dt.now(_tz.utc).isoformat()
                    _sb.table("processed_content").update({
                        "status": "pending_approval",
                        "approval_requested_at": _now_iso,
                    }).eq("id", content_id).execute()
                    update_schedule_status(schedule_id, "pending_approval", user_id=row_user_id)
                except Exception as _revert_exc:
                    logger.warning("Could not set pending_approval status: %s", _revert_exc)
                try:
                    from tasks.telegram_bot import telegram_send_approval_request
                    telegram_send_approval_request(row_user_id, content_id, _preview_text)
                except Exception as _tg_exc:
                    logger.debug("Approval request send failed: %s", _tg_exc)
                logger.info("⏸️  %s held for Telegram approval (user=%s)", content_id[:8], row_user_id[:8])
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

        normalized_post_type = _normalize_post_type(content.get("post_type"))
        structured_payload = _parse_structured_payload(content)

        # ── Load per-user Facebook tokens (multi-tenant, fail-closed) ──
        # In tenant mode we NEVER fall back to global env credentials —
        # that would publish one user's content with another page's token.
        row_fb_token: str = ""
        row_fb_page_id: str = ""
        _token_load_failed: bool = False
        if row_user_id:
            try:
                from app.utils import load_tokens_for_user as _ltu
                _toks = _ltu(row_user_id) or {}
                row_fb_token = _toks.get("page_token", "")
                row_fb_page_id = _toks.get("page_id", "")
            except Exception as _tok_exc:
                logger.warning(
                    "Could not load per-user tokens (user=%s): %s — skipping post",
                    row_user_id[:8] if row_user_id else "?", _tok_exc,
                )
                _token_load_failed = True

        # If we are in tenant mode and token retrieval failed or returned empty,
        # mark the scheduled row as failed and skip — never use global env creds.
        if row_user_id and _token_load_failed:
            update_schedule_status(schedule_id, "failed", user_id=row_user_id)
            skipped += 1
            continue
        if row_user_id and not (row_fb_token and row_fb_page_id):
            logger.warning(
                "No Facebook credentials for user=%s — skipping post",
                row_user_id[:8],
            )
            update_schedule_status(schedule_id, "failed", user_id=row_user_id)
            skipped += 1
            continue

        # ── Per-platform results (tracked independently) ───────────────
        fb_post_id: str = ""
        fb_ok: bool = False
        ig_ok: bool = False
        ig_post_id: str = ""
        fb_error: str = ""
        ig_error: str = ""
        if publish_to_instagram and normalized_post_type == "carousel":
            ig_error = "Carousel auto-publish is not supported for Instagram."
            logger.info("Skipping Instagram publish for carousel %s", content_id[:8])
            publish_to_instagram = False

        # ── Facebook publish (isolated try — does NOT block IG) ────────
        if publish_to_facebook:
            try:
                if normalized_post_type == "carousel":
                    carousel_caption = str(structured_payload.get("caption") or "").strip()
                    carousel_hashtags = _coerce_hashtags(
                        structured_payload.get("hashtags") or content.get("hashtags")
                    )
                    if carousel_hashtags:
                        carousel_caption = f"{carousel_caption}\n\n{' '.join(carousel_hashtags)}".strip()
                    fb_post_id = publish_carousel_post(
                        carousel_caption,
                        structured_payload.get("slides") or [],
                        access_token=row_fb_token,
                        page_id=row_fb_page_id,
                        user_id=row_user_id,
                    )
                elif image_path and os.path.exists(image_path):
                    logger.info("📷 Publishing to Facebook with image: %s", image_path)
                    fb_post_id = publish_photo_post(
                        message, image_path,
                        access_token=row_fb_token,
                        page_id=row_fb_page_id,
                    )
                else:
                    logger.info("📝 Publishing text-only to Facebook")
                    fb_post_id = publish_text_post(
                        message,
                        access_token=row_fb_token,
                        page_id=row_fb_page_id,
                    )

                mark_published(content["id"], fb_post_id, user_id=row_user_id)
                record_publication(content["id"], fb_post_id, user_id=row_user_id)
                fb_ok = True
                logger.info("✅ Published %s -> FB: %s", content_id[:8], fb_post_id)
            except Exception as fb_exc:
                fb_error = str(fb_exc)
                logger.error("❌ Facebook publish failed for %s: %s", content_id[:8], fb_exc)
                action, error_code = error_handler.classify_error(fb_exc)
                retry_count = content.get("retry_count", 0)
                error_handler.execute_action(action, content_id, error_code, retry_count)

        # ── Instagram publish (isolated — does NOT depend on FB) ─────
        if publish_to_instagram:
            ig_result = _publish_to_instagram_if_configured(content, fb_post_id, user_id=row_user_id)
            ig_ok = ig_result["success"]
            ig_error = ig_result.get("error") or ""
            ig_post_id = ig_result.get("post_id") or ""
            if not ig_ok:
                logger.warning("⚠️ Instagram publish failed for %s: %s", content_id[:8], ig_error)

        # ── Persist outcome row for ALL selected platforms to Supabase ─
        # This is the single authoritative write — handles all combinations:
        # FB-only, IG-only, both succeed, partial fail, all fail.
        _persist_publish_outcome(
            content_id=content["id"],
            platforms_field=platforms_field,
            publish_to_facebook=publish_to_facebook,
            fb_ok=fb_ok,
            fb_post_id=fb_post_id,
            publish_to_instagram=publish_to_instagram,
            ig_ok=ig_ok,
            ig_post_id=ig_post_id,
            user_id=row_user_id,
        )

        # ── Update content status & schedule row based on outcomes ─────
        any_ok = fb_ok or ig_ok
        if any_ok:
            # At least one platform succeeded — mark processed_content as published
            if not publish_to_facebook or (publish_to_instagram and not fb_ok):
                # IG-only or FB failed but IG succeeded: processed_content was not updated by
                # mark_published(), so update it here.
                if not fb_ok:
                    try:
                        uq = config.get_database_client().table("processed_content").update(
                            {"status": "published"}
                        ).eq("id", content["id"])
                        if row_user_id:
                            uq = uq.eq("user_id", row_user_id)
                        uq.execute()
                    except Exception as state_err:
                        logger.warning("Could not update content status: %s", state_err)

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

            # ── Telegram publish notification ─────────────────────────────
            if row_user_id:
                try:
                    from tasks.telegram_bot import telegram_notify_published
                    platforms_published = []
                    if fb_ok:
                        platforms_published.append("facebook")
                    if ig_ok:
                        platforms_published.append("instagram")
                    platform_label = ", ".join(platforms_published)

                    # Prefer Facebook post URL (always resolvable).
                    # For IG-only posts, fetch the permalink via Graph API
                    # (returns a real instagram.com/p/<shortcode>/ URL).
                    post_url = ""
                    if fb_post_id:
                        post_url = f"https://www.facebook.com/{fb_post_id}"
                    elif ig_ok and ig_post_id and row_fb_token:
                        try:
                            from engine.instagram_publisher import get_ig_media_permalink
                            post_url = get_ig_media_permalink(ig_post_id, row_fb_token)
                        except Exception as _pl_exc:
                            logger.debug("IG permalink fetch skipped: %s", _pl_exc)

                    telegram_notify_published(
                        row_user_id,
                        platform_label,
                        message,
                        post_url,
                    )
                except Exception as _tg_exc:
                    logger.debug("Telegram notify skipped: %s", _tg_exc)
        else:
            # All selected platforms failed — mark as failed
            final_status = "failed"
            logger.error("❌ All platforms failed for %s", content_id[:8])

        update_schedule_status(schedule_id, final_status, user_id=row_user_id)

        # Rate limiting pause
        time.sleep(config.REQUEST_SLEEP_SECONDS)

    logger.info("📊 Publishing complete: %d published, %d skipped", published, skipped)
    return published


def publish_with_duplicate_check(content_id: str, user_id: Optional[str] = None) -> Optional[str]:
    """
    Publish a specific content item with duplicate checking.

    Args:
        content_id: Content ID to publish

    Returns:
        Facebook post ID if successful, None otherwise
    """
    # Check if can publish
    can_publish, reason = can_publish_content(content_id, user_id=user_id)
    if not can_publish:
        logger.warning("Cannot publish %s: %s", content_id[:8], reason)
        return None

    content = fetch_content(content_id)
    if not content:
        logger.error("Content not found: %s", content_id)
        return None

    try:
        normalized_post_type = _normalize_post_type(content.get("post_type"))
        if normalized_post_type in DRAFT_ONLY_FORMATS:
            logger.warning("Draft-only format cannot auto-publish: %s", normalized_post_type)
            return None
        if normalized_post_type == "carousel":
            payload = _parse_structured_payload(content)
            caption = str(payload.get("caption") or "").strip()
            hashtags = _coerce_hashtags(payload.get("hashtags") or content.get("hashtags"))
            if hashtags:
                caption = f"{caption}\n\n{' '.join(hashtags)}".strip()
            post_id = publish_carousel_post(caption, payload.get("slides") or [])
        elif normalized_post_type == "post":
            post_id = publish_text_post(_build_standard_message(content))
        else:
            logger.warning("Unsupported post type for auto-publish: %s", content.get("post_type"))
            return None

        # Record publication
        mark_published(content_id, post_id, user_id=user_id)
        record_publication(content_id, post_id, user_id=user_id)

        logger.info("✅ Published %s -> FB: %s", content_id[:8], post_id)
        return post_id

    except Exception as exc:
        logger.error("❌ Publish failed: %s", exc)
        return None


def publish_content_by_id(content_id: str, user_id: Optional[str] = None) -> Dict:
    """
    Publish a specific content by ID - for dashboard API.

    Args:
        content_id: UUID of content to publish
        user_id: Optional tenant ID to scope all DB operations (multi-tenant safety)

    Returns:
        Dict with success status and details
    """
    try:
        # Check rate limiter
        can_post, reason = can_post_now(user_id=user_id)
        if not can_post:
            return {"success": False, "error": f"Rate limited: {reason}"}

        # Check ban detector
        if should_pause_automation(user_id=user_id):
            return {"success": False, "error": "Automation paused due to potential shadowban"}

        # Fetch content (scoped to user_id if provided)
        content = fetch_content(content_id, user_id=user_id)
        if not content:
            return {"success": False, "error": "Content not found"}

        # v2.1.1: Anti Double-Publish - skip API if already posted
        existing_fb_post_id = content.get("fb_post_id")
        if existing_fb_post_id:
            logger.warning("⏭️ Skipping %s: already posted as %s (anti double-publish)", content_id[:8], existing_fb_post_id)
            return {"success": True, "post_id": existing_fb_post_id, "note": "Already published"}

        # Check status is valid for publishing
        if content.get("status") not in ["scheduled", "waiting_approval", "media_ready", "drafted", "failed", "retry_scheduled"]:
            return {"success": False, "error": f"Invalid status for publishing: {content.get('status')}"}

        # Transition to 'publishing'
        client = config.get_database_client()
        update_q = client.table("processed_content").update({"status": "publishing"}).eq("id", content_id)
        if user_id:
            update_q = update_q.eq("user_id", user_id)
        update_q.execute()

        normalized_post_type = _normalize_post_type(content.get("post_type"))
        if normalized_post_type in DRAFT_ONLY_FORMATS:
            return {
                "success": False,
                "error": f"{_draft_format_label(normalized_post_type).capitalize()} is draft-only. Open Studio to export it.",
            }
        if normalized_post_type not in AUTO_PUBLISHABLE_FORMATS:
            return {"success": False, "error": f"Unsupported post type: {content.get('post_type')}"}

        structured_payload = _parse_structured_payload(content)
        message = _build_standard_message(content)

        # Resolve per-user Facebook credentials — fail-closed in tenant mode
        _fb_token: str = ""
        _fb_page: str = ""
        if user_id:
            try:
                from app.utils import load_tokens_for_user as _ltu2
                _toks2 = _ltu2(user_id) or {}
                _fb_token = _toks2.get("page_token", "")
                _fb_page = _toks2.get("page_id", "")
            except Exception as _tok2_exc:
                return {
                    "success": False,
                    "error": f"Could not load per-user tokens: {_tok2_exc}",
                }
            if not _fb_token or not _fb_page:
                return {"success": False, "error": "No Facebook credentials for this user"}
        # Non-tenant (single-user) mode: low-level methods fall back to env vars

        image_path = content.get("image_path")
        if normalized_post_type == "carousel":
            caption = str(structured_payload.get("caption") or "").strip()
            hashtags = _coerce_hashtags(structured_payload.get("hashtags") or content.get("hashtags"))
            if hashtags:
                caption = f"{caption}\n\n{' '.join(hashtags)}".strip()
            post_id = publish_carousel_post(
                caption,
                structured_payload.get("slides") or [],
                access_token=_fb_token,
                page_id=_fb_page,
                user_id=user_id,
            )
        elif image_path and os.path.exists(image_path):
            post_id = publish_photo_post(
                message, image_path,
                access_token=_fb_token,
                page_id=_fb_page,
            )
        else:
            post_id = publish_text_post(
                message,
                access_token=_fb_token,
                page_id=_fb_page,
            )

        if post_id:
            mark_published(content_id, post_id, user_id=user_id)
            record_publication(content_id, post_id, user_id=user_id)
            error_handler.update_success_status(content_id)
            logger.info("✅ Published content %s -> FB: %s", content_id[:8], post_id)
            return {"success": True, "post_id": post_id, "facebook_url": f"https://facebook.com/{post_id}"}
        else:
            revert_q = client.table("processed_content").update({"status": "failed"}).eq("id", content_id)
            if user_id:
                revert_q = revert_q.eq("user_id", user_id)
            revert_q.execute()
            return {"success": False, "error": "Facebook API returned no post ID"}

    except Exception as e:
        logger.error("❌ Publish error: %s", e)
        try:
            revert_q = config.get_database_client().table("processed_content").update({"status": "failed", "last_error": str(e)}).eq("id", content_id)
            if user_id:
                revert_q = revert_q.eq("user_id", user_id)
            revert_q.execute()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def get_publication_status(user_id: Optional[str] = None) -> Dict:
    """Get current publication status and stats."""
    tracker = get_tracker(user_id=user_id)
    return tracker.get_publication_stats()


def _persist_publish_outcome(
    *,
    content_id: str,
    platforms_field: str,
    publish_to_facebook: bool,
    fb_ok: bool,
    fb_post_id: str,
    publish_to_instagram: bool,
    ig_ok: bool,
    ig_post_id: str,
    user_id: Optional[str] = None,
) -> None:
    """
    Write a single, authoritative published_posts row to Supabase for this attempt.

    user_id is ALWAYS propagated to every DB write so published_posts rows are
    correctly scoped to the owning tenant.

    Design:
    - If Facebook succeeded, mark_published() already inserted the FB row.
      Update that row with IG outcome (if IG was selected).
    - If Facebook failed but Instagram succeeded, _publish_to_instagram_if_configured
      already inserted an IG-only row. Update that row with fb_status='failed'.
    - If both failed, insert a failure-only row (no post IDs) so the outcome is visible.
    - If Facebook failed and Instagram was also selected but failed, insert a combined
      failure row showing both attempts.

    All writes go to Supabase (the DB layer the dashboard API reads from).
    """
    try:
        client = config.get_database_client()

        if fb_ok and not publish_to_instagram:
            # FB-only success — already inserted by mark_published() with user_id; nothing to do.
            return

        if fb_ok and publish_to_instagram:
            # FB succeeded; IG was attempted. _publish_to_instagram_if_configured already
            # updated the row on IG success. If IG failed, stamp instagram_status='failed'.
            if not ig_ok:
                q = client.table("published_posts").update(
                    {"instagram_status": "failed"}
                ).eq("content_id", content_id).eq("facebook_post_id", fb_post_id)
                if user_id:
                    q = q.eq("user_id", user_id)
                q.execute()
            # IG succeeded → already updated inside _publish_to_instagram_if_configured.
            return

        if not fb_ok and ig_ok and not publish_to_facebook:
            # Pure IG-only success. Row already inserted inside _publish_to_instagram_if_configured.
            return

        if not fb_ok and ig_ok and publish_to_facebook:
            # FB failed, IG succeeded. IG helper inserted an IG-only row.
            # Stamp facebook_status='failed' on that row for the full picture.
            q = (
                client.table("published_posts")
                .select("id")
                .eq("content_id", content_id)
                .eq("instagram_post_id", ig_post_id)
            )
            if user_id:
                q = q.eq("user_id", user_id)
            result = q.limit(1).execute()
            if result.data:
                client.table("published_posts").update({
                    "facebook_status": "failed",
                    "platforms": platforms_field,
                }).eq("id", result.data[0]["id"]).execute()
            return

        # All selected platforms failed — insert a diagnostic failure row.
        import uuid as _uuid
        platforms_attempted = []
        if publish_to_facebook:
            platforms_attempted.append("facebook")
        if publish_to_instagram:
            platforms_attempted.append("instagram")
        row: Dict = {
            "id": str(_uuid.uuid4()),
            "content_id": content_id,
            "platforms": ",".join(platforms_attempted),
        }
        # Always write user_id so the row is tenant-scoped
        if user_id:
            row["user_id"] = user_id
        if publish_to_facebook:
            row["facebook_status"] = "failed"
        if publish_to_instagram:
            row["instagram_status"] = "failed"
        client.table("published_posts").insert(row).execute()

    except Exception as err:
        logger.warning("_persist_publish_outcome: DB write failed: %s", err)


def _publish_to_instagram_if_configured(
    content: Dict, fb_post_id: str, user_id: Optional[str] = None
) -> Dict:
    """
    Attempt to publish content to Instagram.
    Always returns a structured result dict — never raises.

    Args:
        content:    Processed-content row dict.
        fb_post_id: Corresponding Facebook post ID (may be empty).
        user_id:    Tenant ID — loads tokens from managed_pages when provided.

    Returns:
        {"success": bool, "post_id": str|None, "error": str|None}
    """
    from facebook_oauth import get_instagram_account_for_page
    from instagram_publisher import publish_photo_to_instagram, get_public_image_url, get_app_base_url

    def _fail(reason: str) -> Dict:
        logger.warning("Instagram publish skipped/failed: %s", reason)
        return {"success": False, "post_id": None, "error": reason}

    if user_id:
        try:
            from app.utils import load_tokens_for_user
            tokens = load_tokens_for_user(user_id)
        except Exception as exc:
            # Fail-closed in tenant mode — never fall back to global tokens
            return _fail(f"load_tokens_for_user failed: {exc}")
    else:
        from facebook_oauth import load_tokens
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
        client = config.get_database_client()
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
            # IG-only: insert new row — always include user_id for tenant isolation
            import uuid as _uuid
            ig_row: Dict = {
                "id": str(_uuid.uuid4()),
                "content_id": content["id"],
                "instagram_post_id": ig_post_id,
                "instagram_status": "published",
                "platforms": "instagram",
            }
            if user_id:
                ig_row["user_id"] = user_id
            client.table("published_posts").insert(ig_row).execute()
    except Exception as db_err:
        logger.warning("Could not update published_posts with Instagram post ID: %s", db_err)

    return {"success": True, "post_id": ig_post_id, "error": None}


def publish_for_user(user_config: "UserConfig") -> int:  # type: ignore[name-defined]
    """
    Publish due scheduled posts for a single tenant using a UserConfig object.

    This is the preferred entry point for the multi-tenant pipeline runner.
    Credentials come directly from ``user_config``; returns 0 without touching
    global environment credentials if the tenant has no credentials configured.

    Parameters
    ----------
    user_config : UserConfig
        Fully-populated tenant configuration object with facebook_access_token
        and facebook_page_id already loaded from managed_pages.

    Returns
    -------
    int
        Number of posts published.
    """
    # Guard: do not enter the publish loop if the tenant has no FB credentials.
    # This prevents global env credential fallback entirely.
    if not user_config.facebook_access_token or not user_config.facebook_page_id:
        logger.info(
            "publish_for_user: no FB credentials for user=%s — skipping",
            user_config.user_id[:8],
        )
        return 0
    return publish_due_posts(limit=5, user_id=user_config.user_id)


if __name__ == "__main__":
    from process_lock import acquire_global_lock, release_global_lock

    if acquire_global_lock():
        try:
            publish_due_posts()
        finally:
            release_global_lock()
    else:
        logger.warning("🚫 Automation already running (lock held). Exiting.")
