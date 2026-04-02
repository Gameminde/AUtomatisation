"""Studio workflow and generation handlers."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import jsonify

import config
from . import helpers as studio_helpers
from . import payloads as studio_payloads

logger = config.get_logger("studio")

DRAFT_ONLY_FORMATS = studio_helpers.DRAFT_ONLY_FORMATS
_client = studio_helpers._client
_load_owned_content_row = studio_helpers._load_owned_content_row
_load_runtime_profile = studio_helpers._load_runtime_profile
_normalize_platforms = studio_helpers._normalize_platforms
_normalize_ui_language = studio_helpers._normalize_ui_language
_resolve_request_data = lambda: {}
_resolve_studio_user_id = lambda data: ""
_save_draft_record = studio_helpers._save_draft_record
_canonical_post_type = studio_helpers._canonical_post_type
_create_schedule_record = studio_helpers._create_schedule_record
_generate_studio_content = studio_helpers._generate_studio_content
_regenerate_existing_content = studio_helpers._regenerate_existing_content
_build_record_payload = studio_helpers._build_record_payload
_current_user_id = studio_helpers._current_user_id
_load_pending_content_payload = studio_payloads._load_pending_content_payload
_load_draft_content_payload = studio_payloads._load_draft_content_payload


def _api_success(**payload):
    data = {"success": True}
    data.update(payload)
    return jsonify(data)


def _api_error(message: str, status: int = 400, **payload):
    data = {"success": False, "error": message}
    data.update(payload)
    return jsonify(data), status


def approve_content(content_id: str):
    try:
        result = (
            _client()
            .table("processed_content")
            .update({"status": "scheduled"})
            .eq("id", content_id)
            .eq("user_id", _current_user_id())
            .eq("status", "waiting_approval")
            .execute()
        )
        if not result.data:
            return _api_error("Content not found or not in waiting_approval status", 404)
        return _api_success(content_id=content_id, new_status="scheduled")
    except Exception as exc:
        logger.error("Error approving content: %s", exc)
        return _api_error(str(exc), 500)


def reject_content(content_id: str):
    try:
        data = _resolve_request_data()
        action = data.get("action", "reject")
        reason = data.get("reason", "Rejected by user")
        new_status = "drafted" if action == "regenerate" else "rejected"
        result = (
            _client()
            .table("processed_content")
            .update({"status": new_status, "rejected_reason": reason if new_status == "rejected" else None})
            .eq("id", content_id)
            .eq("user_id", _current_user_id())
            .execute()
        )
        if not result.data:
            return _api_error("Content not found", 404)
        return _api_success(content_id=content_id, new_status=new_status)
    except Exception as exc:
        logger.error("Error rejecting content: %s", exc)
        return _api_error(str(exc), 500)


def get_pending_content(limit: int = 20):
    try:
        return _api_success(**_load_pending_content_payload(_current_user_id(), limit=limit))
    except Exception as exc:
        logger.error("Error fetching pending content: %s", exc)
        return _api_error(str(exc), 500)


def get_draft_content(limit: int = 50):
    try:
        return _api_success(**_load_draft_content_payload(_current_user_id(), limit=limit))
    except Exception as exc:
        logger.error("Error fetching drafts: %s", exc)
        return _api_error(str(exc), 500)


def send_content_to_review(content_id: str):
    try:
        content_row = _load_owned_content_row(content_id, "id, post_type, status")
        if not content_row:
            return _api_error("Content not found", 404)

        post_type = str(content_row.get("post_type") or "post").strip().lower()
        if post_type in DRAFT_ONLY_FORMATS:
            return _api_error("This format is saved for manual posting only.", 400)

        current_status = str(content_row.get("status") or "").strip().lower()
        if current_status not in {"draft_only", "draft_ready", "drafted", "pending"}:
            return _api_error("Content must be in a draft state before review.", 400)

        approval_requested_at = datetime.now(timezone.utc).isoformat()
        result = (
            _client()
            .table("processed_content")
            .update(
                {
                    "status": "waiting_approval",
                    "approval_requested_at": approval_requested_at,
                }
            )
            .eq("id", content_id)
            .eq("user_id", _current_user_id())
            .execute()
        )
        if not result.data:
            return _api_error("Content not found", 404)

        return _api_success(
            content_id=content_id,
            new_status="waiting_approval",
            approval_requested_at=approval_requested_at,
        )
    except Exception as exc:
        logger.error("Error sending content to review: %s", exc)
        return _api_error(str(exc), 500)


def studio_generate():
    try:
        data = _resolve_request_data()
        user_id = _resolve_studio_user_id(data)
        content_format = str(data.get("format") or "post").strip().lower()
        if content_format not in {"post", "carousel", "story_sequence", "reel_script"}:
            return _api_error("format must be one of: post, carousel, story_sequence, reel_script", 400)

        language = _normalize_ui_language(data.get("language"), fallback="en")
        tone = str(data.get("tone") or "").strip().lower() or None
        topic = str(data.get("topic") or "").strip()
        generated = _generate_studio_content(
            content_format=content_format,
            language=language,
            topic=topic,
            user_id=user_id,
            tone=tone,
        )
        return _api_success(format=content_format, content=generated)
    except PermissionError as exc:
        return _api_error(str(exc), 403)
    except Exception as exc:
        logger.error("Error generating studio content: %s", exc)
        return _api_error(str(exc), 500)


def studio_regenerate():
    try:
        data = _resolve_request_data()
        _resolve_studio_user_id(data)
        content_id = str(data.get("content_id") or "").strip()
        instruction = str(data.get("instruction") or "").strip()
        tone = str(data.get("tone") or "").strip().lower() or None
        content = data.get("content") if isinstance(data.get("content"), dict) else None
        requested_format = str(data.get("format") or (content or {}).get("format") or "").strip().lower()
        if not content_id and not content:
            return _api_error("content_id or content required", 400)

        row = None
        if content_id:
            row = _load_owned_content_row(content_id)
            if not row:
                return _api_error("Content not found", 404)

        if row and content:
            content_format = _canonical_post_type(row.get("post_type") or requested_format or "post")
            hydrated = _build_record_payload(
                content_format=content_format,
                content=content,
                status=str(row.get("status") or "draft_only"),
                article_id=str(row.get("article_id") or ""),
                user_id=str(row.get("user_id") or _current_user_id()),
            )
            row = {
                **row,
                **hydrated,
                "id": row.get("id"),
            }
        elif not row and content:
            content_format = requested_format or "post"
            row = _build_record_payload(
                content_format=content_format,
                content=content,
                status="draft_only",
                article_id="",
                user_id=_current_user_id(),
            )

        regenerated = _regenerate_existing_content(
            row,
            instruction=instruction,
            tone=tone,
        )
        return _api_success(content_id=content_id, content=regenerated)
    except PermissionError as exc:
        return _api_error(str(exc), 403)
    except Exception as exc:
        logger.error("Error regenerating studio content: %s", exc)
        return _api_error(str(exc), 500)


def studio_save_draft():
    try:
        data = _resolve_request_data()
        user_id = _resolve_studio_user_id(data)
        content = data.get("content")
        if not isinstance(content, dict):
            return _api_error("content object required", 400)

        content_format = str(data.get("format") or content.get("format") or "post").strip().lower()
        if content_format not in {"post", "carousel", "story_sequence", "reel_script"}:
            return _api_error("Unsupported content format", 400)

        language = _normalize_ui_language(data.get("language") or content.get("language"), fallback="en")
        normalized_content = dict(content)
        normalized_content["language"] = language
        saved = _save_draft_record(
            content_format=content_format,
            content=normalized_content,
            user_id=user_id,
            article_id=str(data.get("article_id") or "").strip(),
            status="draft_only",
        )
        return _api_success(
            content_id=saved.get("id"),
            status="draft_only",
            content=normalized_content,
        )
    except PermissionError as exc:
        return _api_error(str(exc), 403)
    except Exception as exc:
        logger.error("Error saving studio draft: %s", exc)
        return _api_error(str(exc), 500)


def studio_approve():
    try:
        data = _resolve_request_data()
        _resolve_studio_user_id(data)
        content_id = str(data.get("content_id") or "").strip()
        scheduled_time = str(data.get("scheduled_time") or "").strip()
        if not content_id:
            return _api_error("content_id required", 400)
        if not scheduled_time:
            return _api_error("scheduled_time required", 400)

        content_row = _load_owned_content_row(content_id, "id, post_type, status, user_id")
        if not content_row:
            return _api_error("Content not found", 404)
        if content_row.get("status") not in {"draft_only", "draft_ready", "drafted", "pending", "waiting_approval"}:
            return _api_error("Content must be in a draft or review state before approval", 400)
        post_type = str(content_row.get("post_type") or "post").strip().lower()
        if post_type in DRAFT_ONLY_FORMATS:
            return _api_error("This format cannot be auto-published. Use Save Draft instead.", 400)

        runtime_profile = _load_runtime_profile(_current_user_id())
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
            timezone_name=runtime_profile.timezone or "UTC",
            platforms=_normalize_platforms(data.get("platforms")),
        )
        return _api_success(content_id=content_id, new_status="scheduled", scheduled=scheduled)
    except PermissionError as exc:
        return _api_error(str(exc), 403)
    except Exception as exc:
        logger.error("Error approving studio draft: %s", exc)
        return _api_error(str(exc), 500)
