"""Studio content CRUD and scheduling handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from flask import jsonify, send_file

import config
from . import helpers as studio_helpers
from . import payloads as studio_payloads

logger = config.get_logger("studio")

DRAFT_ONLY_FORMATS = studio_helpers.DRAFT_ONLY_FORMATS
_client = studio_helpers._client
_clear_schedule_records = studio_helpers._clear_schedule_records
_create_schedule_record = studio_helpers._create_schedule_record
_current_user_id = studio_helpers._current_user_id
_load_owned_content_row = studio_helpers._load_owned_content_row
_load_runtime_profile = studio_helpers._load_runtime_profile
_normalize_draft_row = studio_helpers._normalize_draft_row
_normalize_platforms = studio_helpers._normalize_platforms
_regenerate_existing_content = studio_helpers._regenerate_existing_content
_resolve_request_data = lambda: {}
_load_dashboard_summary_payload = studio_payloads._load_dashboard_summary_payload
_load_published_content_payload = studio_payloads._load_published_content_payload
_load_scheduled_content_payload = studio_payloads._load_scheduled_content_payload


def _api_success(**payload):
    data = {"success": True}
    data.update(payload)
    return jsonify(data)


def _api_error(message: str, status: int = 400, **payload):
    data = {"success": False, "error": message}
    data.update(payload)
    return jsonify(data), status


def get_scheduled_content(limit: int = 20):
    try:
        return _api_success(**_load_scheduled_content_payload(_current_user_id(), limit=limit))
    except Exception as exc:
        logger.error("Error fetching scheduled: %s", exc)
        return _api_error(str(exc), 500)


def get_published_content(limit: int = 20):
    try:
        return _api_success(**_load_published_content_payload(_current_user_id(), limit=limit))
    except Exception as exc:
        logger.error("Error fetching published: %s", exc)
        return _api_error(str(exc), 500)


def get_content_by_id(content_id: str):
    try:
        row = _load_owned_content_row(content_id)
        if not row:
            return _api_error("Content not found", 404)
        return _api_success(content=_normalize_draft_row(row))
    except Exception as exc:
        logger.error("Error fetching content: %s", exc)
        return _api_error(str(exc), 500)


def get_content_image(content_id: str):
    try:
        result = (
            _client()
            .table("processed_content")
            .select("image_path")
            .eq("id", content_id)
            .eq("user_id", _current_user_id())
            .single()
            .execute()
        )
        if not result.data:
            return _api_error("Content not found", 404)
        image_path = result.data.get("image_path")
        if not image_path:
            return _api_error("No image available", 404)
        base_dir = Path(__file__).parent.parent.parent.resolve()
        normalized_path = str(image_path).strip()
        if normalized_path.startswith("~"):
            return _api_error("Invalid image path", 400)
        candidate_path = Path(normalized_path)
        if not candidate_path.is_absolute():
            candidate_path = base_dir / candidate_path
        img_path = candidate_path.resolve(strict=True)
        allowed_roots = [
            (base_dir / "generated_images").resolve(),
            (base_dir / "downloaded_images").resolve(),
            base_dir.resolve(),
        ]
        if not any(img_path == root or root in img_path.parents for root in allowed_roots):
            return _api_error("Invalid image path", 400)
        return send_file(str(img_path))
    except FileNotFoundError:
        return _api_error("Image not found", 404)
    except Exception as exc:
        logger.error("Error serving image: %s", exc)
        return _api_error(str(exc), 500)


def update_content(content_id: str):
    try:
        data = _resolve_request_data()
        update_data: Dict = {}
        for field in ["generated_text", "arabic_text", "hashtags", "hook", "call_to_action", "image_path"]:
            if field in data:
                update_data[field] = data[field]
        if not update_data:
            return _api_error("No fields to update", 400)
        result = (
            _client()
            .table("processed_content")
            .update(update_data)
            .eq("id", content_id)
            .eq("user_id", _current_user_id())
            .execute()
        )
        if result.data:
            return _api_success(content=_normalize_draft_row(result.data[0]))
        return _api_error("Content not found", 404)
    except Exception as exc:
        logger.error("Error updating content: %s", exc)
        return _api_error(str(exc), 500)


def get_dashboard_summary():
    try:
        return _api_success(**_load_dashboard_summary_payload(_current_user_id()))
    except Exception as exc:
        logger.error("Error fetching dashboard summary: %s", exc)
        return _api_error(str(exc), 500)


def list_content(limit: int = 50, q: str = "", status: str = ""):
    try:
        statuses = [item.strip() for item in str(status).split(",") if item.strip()]
        query = (
            _client()
            .table("processed_content")
            .select(
                "id, hook, generated_text, status, generated_at, image_path, "
                "post_type, last_error, last_error_at, next_retry_at, approval_requested_at"
            )
            .eq("user_id", _current_user_id())
            .order("generated_at", desc=True)
            .limit(limit)
        )
        if statuses:
            query = query.in_("status", statuses)
        rows = query.execute().data or []
        lowered = str(q or "").strip().lower()
        if lowered:
            rows = [
                row
                for row in rows
                if lowered in (row.get("hook") or "").lower()
                or lowered in (row.get("generated_text") or "").lower()
            ]
        return _api_success(content=rows)
    except Exception as exc:
        logger.error("Error listing content: %s", exc)
        return _api_error(str(exc), 500)


def get_all_content(limit: int = 50):
    try:
        result = (
            _client()
            .table("processed_content")
            .select("id, generated_text, hook, status, created_at, generated_at, target_audience")
            .eq("user_id", _current_user_id())
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return _api_success(content=result.data or [])
    except Exception as exc:
        logger.error("Error fetching all content: %s", exc)
        return _api_error(str(exc), 500)


def schedule_content(content_id: str):
    try:
        data = _resolve_request_data()
        scheduled_time = data.get("scheduled_time")
        if not scheduled_time:
            return _api_error("scheduled_time required", 400)
        content_row = _load_owned_content_row(content_id, "id, post_type, status")
        if not content_row:
            return _api_error("Content not found", 404)
        post_type = str(content_row.get("post_type") or "post").strip().lower()
        if post_type in DRAFT_ONLY_FORMATS:
            return _api_error("This format cannot be auto-published. Use Save Draft instead.", 400)
        timezone_name = str(data.get("timezone") or "").strip()
        if not timezone_name:
            try:
                timezone_name = _load_runtime_profile(_current_user_id()).timezone
            except Exception:
                timezone_name = "UTC"
        (
            _client()
            .table("processed_content")
            .update({"status": "scheduled"})
            .eq("id", content_id)
            .eq("user_id", _current_user_id())
            .execute()
        )
        scheduled = _create_schedule_record(
            content_id=content_id,
            scheduled_time=scheduled_time,
            timezone_name=timezone_name or "UTC",
            platforms=_normalize_platforms(data.get("platforms")),
        )
        return _api_success(content_id=content_id, new_status="scheduled", scheduled=scheduled)
    except Exception as exc:
        logger.error("Error scheduling content: %s", exc)
        return _api_error(str(exc), 500)


def unschedule_content(content_id: str):
    try:
        content_row = _load_owned_content_row(content_id, "id, post_type, status")
        if not content_row:
            return _api_error("Content not found", 404)

        if str(content_row.get("status") or "").strip().lower() != "scheduled":
            return _api_error("Content is not scheduled", 400)

        post_type = str(content_row.get("post_type") or "post").strip().lower()
        fallback_status = "draft_only" if post_type in DRAFT_ONLY_FORMATS else "drafted"
        (
            _client()
            .table("processed_content")
            .update({"status": fallback_status})
            .eq("id", content_id)
            .eq("user_id", _current_user_id())
            .execute()
        )
        _clear_schedule_records(content_id)
        return _api_success(content_id=content_id, new_status=fallback_status)
    except Exception as exc:
        logger.error("Error unscheduling content: %s", exc)
        return _api_error(str(exc), 500)


def regenerate_content_by_id(content_id: str):
    try:
        data = _resolve_request_data()
        content = _load_owned_content_row(content_id)
        if not content:
            return _api_error("Content not found", 404)
        regenerated = _regenerate_existing_content(
            content,
            instruction=str(data.get("instruction") or "").strip(),
            tone=str(data.get("tone") or "").strip().lower() or None,
        )
        return _api_success(content_id=content_id, content=regenerated)
    except Exception as exc:
        logger.error("Error regenerating content: %s", exc)
        return _api_error(str(exc), 500)


def regenerate_content_legacy():
    try:
        data = _resolve_request_data()
        content_id = data.get("content_id")
        if not content_id:
            return _api_error("Missing content_id", 400)
        result = (
            _client()
            .table("processed_content")
            .select("*")
            .eq("id", content_id)
            .eq("user_id", _current_user_id())
            .single()
            .execute()
        )
        if not result.data:
            return _api_error("Content not found", 404)
        regenerated = _regenerate_existing_content(
            result.data,
            instruction=str(data.get("instruction") or "").strip(),
            tone=str(data.get("tone") or "").strip().lower() or None,
        )
        return _api_success(content_id=content_id, content=regenerated)
    except Exception as exc:
        logger.error("Regenerate error: %s", exc)
        return _api_error(str(exc), 500)
