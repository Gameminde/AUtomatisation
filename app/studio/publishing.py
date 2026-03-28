"""Studio publish and scheduler actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from flask import jsonify

import config
from . import helpers as studio_helpers

logger = config.get_logger("studio")

DRAFT_ONLY_FORMATS = studio_helpers.DRAFT_ONLY_FORMATS
_client = studio_helpers._client
_current_user_id = studio_helpers._current_user_id
_load_owned_content_row = studio_helpers._load_owned_content_row


def _api_error(message: str, status: int = 400, **payload):
    data = {"success": False, "error": message}
    data.update(payload)
    return jsonify(data), status


def _publish_to_instagram(content_id: str) -> Dict:
    """Internal: publish content to Instagram, scoped to current user."""
    try:
        from app.utils import load_tokens_for_user
        from facebook_oauth import get_instagram_account_for_page
        from instagram_publisher import get_app_base_url, get_public_image_url, publish_photo_to_instagram

        user_id = _current_user_id()
        tokens = load_tokens_for_user(user_id)
        if not tokens:
            return {"success": False, "error": "No Facebook/Instagram tokens configured"}
        page_id = tokens.get("page_id")
        page_token = tokens.get("page_token")
        stored_ig_id = tokens.get("instagram_account_id", "")
        if stored_ig_id:
            ig_user_id = stored_ig_id
        else:
            ig_info = get_instagram_account_for_page(page_id, page_token)
            if not ig_info:
                return {"success": False, "error": "No Instagram Business Account linked"}
            ig_user_id = ig_info["instagram_account_id"]

        client = _client()
        result = (
            client.table("processed_content")
            .select("*")
            .eq("id", content_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not result.data:
            return {"success": False, "error": "Content not found"}
        content = result.data

        arabic_text = content.get("arabic_text", "")
        hook = content.get("hook", "")
        body = content.get("generated_text", "")
        cta = content.get("call_to_action", "")
        hashtags = " ".join(content.get("hashtags") or [])
        caption = (arabic_text or f"{hook}\n\n{body}\n\n{cta}").strip()
        if hashtags:
            caption = f"{caption}\n\n{hashtags}"

        image_path = content.get("image_path", "")
        if not image_path:
            return {"success": False, "error": "No image available"}

        base_url = get_app_base_url()
        image_url = get_public_image_url(image_path, base_url)
        if not image_url:
            return {"success": False, "error": f"Image file not found: {image_path}"}

        ig_post_id = publish_photo_to_instagram(ig_user_id, page_token, image_url, caption)

        try:
            pub_rows = (
                client.table("published_posts")
                .select("id")
                .eq("content_id", content_id)
                .eq("user_id", user_id)
                .order("published_at", desc=True)
                .limit(1)
                .execute()
            )
            if pub_rows.data:
                (
                    client.table("published_posts")
                    .update(
                        {
                            "instagram_post_id": ig_post_id,
                            "instagram_status": "published",
                            "platforms": "facebook,instagram",
                        }
                    )
                    .eq("id", pub_rows.data[0]["id"])
                    .eq("user_id", user_id)
                    .execute()
                )
            else:
                import uuid as _uuid

                (
                    client.table("published_posts")
                    .insert(
                        {
                            "id": str(_uuid.uuid4()),
                            "user_id": user_id,
                            "content_id": content_id,
                            "instagram_post_id": ig_post_id,
                            "instagram_status": "published",
                            "platforms": "instagram",
                        }
                    )
                    .execute()
                )
                (
                    client.table("processed_content")
                    .update({"status": "published"})
                    .eq("id", content_id)
                    .eq("user_id", user_id)
                    .execute()
                )
        except Exception as db_err:
            logger.warning("Could not save Instagram post ID to DB: %s", db_err)

        return {"success": True, "post_id": ig_post_id}
    except Exception as exc:
        logger.error("Instagram publish failed: %s", exc)
        return {"success": False, "error": str(exc)}


def publish_specific_content(data: dict):
    try:
        from publisher import publish_content_by_id

        content_id = data.get("content_id")
        if not content_id:
            return _api_error("content_id required", 400)
        owned_content = _load_owned_content_row(str(content_id).strip(), "id, post_type, status")
        if not owned_content:
            return _api_error("Content not found", 404)
        post_type = str(owned_content.get("post_type") or "post").strip().lower()
        if post_type in DRAFT_ONLY_FORMATS:
            return _api_error("This format cannot be auto-published. Use Save Draft instead.", 400)
        platforms = data.get("platforms", ["facebook"])
        if isinstance(platforms, str):
            platforms = [platforms]

        user_id = _current_user_id()
        per_platform: Dict = {}
        if "facebook" in platforms:
            per_platform["facebook"] = publish_content_by_id(content_id, user_id=user_id)
        if "instagram" in platforms:
            per_platform["instagram"] = _publish_to_instagram(content_id)

        any_success = any(result.get("success") for result in per_platform.values())
        results: Dict = {
            "content_id": content_id,
            "platforms": per_platform,
            "results": per_platform,
            "success": any_success,
        }
        if per_platform.get("facebook", {}).get("success"):
            results["post_id"] = per_platform["facebook"].get("post_id")
        if per_platform.get("instagram", {}).get("success"):
            results["instagram_post_id"] = per_platform["instagram"].get("post_id")
        if not any_success:
            results["error"] = "; ".join(
                f"{platform}: {value.get('error', 'failed')}"
                for platform, value in per_platform.items()
                if not value.get("success")
            )
        return jsonify(results), (200 if any_success else 400)
    except Exception as exc:
        logger.error("Error publishing content: %s", exc)
        return _api_error(str(exc), 500)


def publish_next():
    try:
        client = _client()
        next_post = (
            client.table("scheduled_posts")
            .select("*")
            .eq("status", "scheduled")
            .eq("user_id", _current_user_id())
            .order("scheduled_time")
            .limit(1)
            .execute()
        )
        if not next_post.data:
            return jsonify({"success": False, "error": "No scheduled posts found"})
        now = datetime.now(timezone.utc).isoformat()
        (
            client.table("scheduled_posts")
            .update({"scheduled_time": now})
            .eq("id", next_post.data[0]["id"])
            .eq("user_id", _current_user_id())
            .execute()
        )
        return jsonify({"success": True, "message": "Scheduled for immediate publishing"})
    except Exception as exc:
        logger.error("Error publishing next: %s", exc)
        return jsonify({"error": str(exc)}), 500


def publish_now(data: dict):
    try:
        from publisher import publish_due_posts

        limit = int(data.get("limit", 1))
        published = publish_due_posts(limit=limit, user_id=_current_user_id())
        return jsonify({"success": True, "published_count": published})
    except Exception as exc:
        logger.error("Error publishing: %s", exc)
        return jsonify({"error": str(exc)}), 500


def run_scheduler(data: dict):
    try:
        from scheduler import schedule_posts

        days = int(data.get("days", 7))
        platforms_raw = data.get("platforms", "facebook")
        if isinstance(platforms_raw, list):
            platforms_str = ",".join(item.strip() for item in platforms_raw)
        else:
            platforms_str = str(platforms_raw).strip() or "facebook"
        scheduled = schedule_posts(days=days, platforms=platforms_str, user_id=_current_user_id())
        return jsonify({"success": True, "scheduled_count": scheduled, "platforms": platforms_str})
    except Exception as exc:
        logger.error("Error scheduling: %s", exc)
        return jsonify({"error": str(exc)}), 500


def sync_analytics():
    try:
        from analytics_tracker import sync_all_posts

        synced = sync_all_posts()
        return jsonify({"success": True, "synced_count": synced})
    except Exception as exc:
        logger.error("Error syncing analytics: %s", exc)
        return jsonify({"error": str(exc)}), 500
