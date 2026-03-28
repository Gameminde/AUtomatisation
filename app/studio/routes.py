"""Content Studio API routes - thin compatibility layer over focused modules."""

from __future__ import annotations

from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request
from flask_login import current_user

import config
from app.utils import api_login_required
from . import content as content_impl
from . import helpers as helpers_impl
from . import payloads as payloads_impl
from . import publishing as publishing_impl
from . import workflow as workflow_impl

logger = config.get_logger("studio")

studio_bp = Blueprint("studio", __name__)

AUTO_PUBLISHABLE_FORMATS = helpers_impl.AUTO_PUBLISHABLE_FORMATS
DRAFT_ONLY_FORMATS = helpers_impl.DRAFT_ONLY_FORMATS

_client = helpers_impl._client
_normalize_platforms = helpers_impl._normalize_platforms
_normalize_ui_language = helpers_impl._normalize_ui_language
_build_studio_article = helpers_impl._build_studio_article
_extract_language_from_content = helpers_impl._extract_language_from_content
_load_active_page_context = helpers_impl._load_active_page_context
_build_content_preview = helpers_impl._build_content_preview
_load_runtime_profile = helpers_impl._load_runtime_profile
_normalize_generated_content = helpers_impl._normalize_generated_content
_parse_structured_generated_text = helpers_impl._parse_structured_generated_text
_normalize_draft_row = helpers_impl._normalize_draft_row
_build_record_payload = helpers_impl._build_record_payload
_save_draft_record = helpers_impl._save_draft_record
_load_owned_content_row = helpers_impl._load_owned_content_row
_create_schedule_record = helpers_impl._create_schedule_record
_clear_schedule_records = helpers_impl._clear_schedule_records
_generate_studio_content = helpers_impl._generate_studio_content
_regenerate_existing_content = helpers_impl._regenerate_existing_content

_load_pending_content_payload = payloads_impl._load_pending_content_payload
_load_draft_content_payload = payloads_impl._load_draft_content_payload
_load_scheduled_content_payload = payloads_impl._load_scheduled_content_payload
_load_published_content_payload = payloads_impl._load_published_content_payload
_load_dashboard_summary_payload = payloads_impl._load_dashboard_summary_payload
_load_studio_bootstrap_payload = payloads_impl._load_studio_bootstrap_payload

_publish_to_instagram = publishing_impl._publish_to_instagram


def _resolve_request_data() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def _resolve_studio_user_id(data: Dict[str, Any]) -> str:
    requested_user_id = str(data.get("user_id") or current_user.id).strip()
    if requested_user_id != current_user.id:
        raise PermissionError("You can only generate content for your own account.")
    return requested_user_id


def _api_success(**payload):
    data = {"success": True}
    data.update(payload)
    return jsonify(data)


def _api_error(message: str, status: int = 400, **payload):
    data = {"success": False, "error": message}
    data.update(payload)
    return jsonify(data), status


def _wire_module_dependencies() -> None:
    helpers_impl._client = lambda: _client()
    helpers_impl._current_user_id = lambda: current_user.id

    payloads_impl._client = lambda: _client()
    payloads_impl._build_content_preview = lambda row: _build_content_preview(row)
    payloads_impl._extract_language_from_content = lambda row: _extract_language_from_content(row)
    payloads_impl._load_active_page_context = lambda user_id: _load_active_page_context(user_id)
    payloads_impl._normalize_draft_row = lambda row: _normalize_draft_row(row)

    workflow_impl._client = lambda: _client()
    workflow_impl._create_schedule_record = lambda *args, **kwargs: _create_schedule_record(*args, **kwargs)
    workflow_impl._current_user_id = lambda: current_user.id
    workflow_impl._generate_studio_content = lambda *args, **kwargs: _generate_studio_content(*args, **kwargs)
    workflow_impl._load_draft_content_payload = lambda *args, **kwargs: _load_draft_content_payload(*args, **kwargs)
    workflow_impl._load_owned_content_row = lambda *args, **kwargs: _load_owned_content_row(*args, **kwargs)
    workflow_impl._load_pending_content_payload = lambda *args, **kwargs: _load_pending_content_payload(*args, **kwargs)
    workflow_impl._load_runtime_profile = lambda *args, **kwargs: _load_runtime_profile(*args, **kwargs)
    workflow_impl._normalize_platforms = lambda raw_value: _normalize_platforms(raw_value)
    workflow_impl._normalize_ui_language = lambda language, fallback="en": _normalize_ui_language(language, fallback=fallback)
    workflow_impl._regenerate_existing_content = lambda *args, **kwargs: _regenerate_existing_content(*args, **kwargs)
    workflow_impl._resolve_request_data = lambda: _resolve_request_data()
    workflow_impl._resolve_studio_user_id = lambda data: _resolve_studio_user_id(data)
    workflow_impl._save_draft_record = lambda *args, **kwargs: _save_draft_record(*args, **kwargs)

    content_impl._client = lambda: _client()
    content_impl._clear_schedule_records = lambda *args, **kwargs: _clear_schedule_records(*args, **kwargs)
    content_impl._create_schedule_record = lambda *args, **kwargs: _create_schedule_record(*args, **kwargs)
    content_impl._current_user_id = lambda: current_user.id
    content_impl._load_dashboard_summary_payload = lambda *args, **kwargs: _load_dashboard_summary_payload(*args, **kwargs)
    content_impl._load_owned_content_row = lambda *args, **kwargs: _load_owned_content_row(*args, **kwargs)
    content_impl._load_published_content_payload = lambda *args, **kwargs: _load_published_content_payload(*args, **kwargs)
    content_impl._load_runtime_profile = lambda *args, **kwargs: _load_runtime_profile(*args, **kwargs)
    content_impl._load_scheduled_content_payload = lambda *args, **kwargs: _load_scheduled_content_payload(*args, **kwargs)
    content_impl._normalize_draft_row = lambda row: _normalize_draft_row(row)
    content_impl._normalize_platforms = lambda raw_value: _normalize_platforms(raw_value)
    content_impl._regenerate_existing_content = lambda *args, **kwargs: _regenerate_existing_content(*args, **kwargs)
    content_impl._resolve_request_data = lambda: _resolve_request_data()

    publishing_impl._client = lambda: _client()
    publishing_impl._current_user_id = lambda: current_user.id
    publishing_impl._load_owned_content_row = lambda *args, **kwargs: _load_owned_content_row(*args, **kwargs)


_wire_module_dependencies()


@studio_bp.route("/api/content/<content_id>/approve", methods=["POST"])
@api_login_required
def approve_content(content_id: str):
    return workflow_impl.approve_content(content_id)


@studio_bp.route("/api/content/<content_id>/reject", methods=["POST"])
@api_login_required
def reject_content(content_id: str):
    return workflow_impl.reject_content(content_id)


@studio_bp.route("/api/content/pending", methods=["GET"])
@api_login_required
def get_pending_content():
    limit = int(request.args.get("limit", 20))
    return workflow_impl.get_pending_content(limit=limit)


@studio_bp.route("/api/content/drafts", methods=["GET"])
@api_login_required
def get_draft_content():
    limit = int(request.args.get("limit", 50))
    return workflow_impl.get_draft_content(limit=limit)


@studio_bp.route("/api/content/<content_id>/review", methods=["POST"])
@api_login_required
def send_content_to_review(content_id: str):
    return workflow_impl.send_content_to_review(content_id)


@studio_bp.route("/api/studio/generate", methods=["POST"])
@api_login_required
def studio_generate():
    return workflow_impl.studio_generate()


@studio_bp.route("/api/studio/regenerate", methods=["POST"])
@api_login_required
def studio_regenerate():
    return workflow_impl.studio_regenerate()


@studio_bp.route("/api/studio/save-draft", methods=["POST"])
@api_login_required
def studio_save_draft():
    return workflow_impl.studio_save_draft()


@studio_bp.route("/api/studio/approve", methods=["POST"])
@api_login_required
def studio_approve():
    return workflow_impl.studio_approve()


@studio_bp.route("/api/content/scheduled", methods=["GET"])
@api_login_required
def get_scheduled_content():
    limit = int(request.args.get("limit", 20))
    return content_impl.get_scheduled_content(limit=limit)


@studio_bp.route("/api/content/published", methods=["GET"])
@api_login_required
def get_published_content():
    limit = int(request.args.get("limit", 20))
    return content_impl.get_published_content(limit=limit)


@studio_bp.route("/api/content/<content_id>", methods=["GET"])
@api_login_required
def get_content_by_id(content_id: str):
    return content_impl.get_content_by_id(content_id)


@studio_bp.route("/api/content/<content_id>/image", methods=["GET"])
@api_login_required
def get_content_image(content_id: str):
    return content_impl.get_content_image(content_id)


@studio_bp.route("/api/content/<content_id>", methods=["PUT"])
@api_login_required
def update_content(content_id: str):
    return content_impl.update_content(content_id)


@studio_bp.route("/api/content/dashboard-summary", methods=["GET"])
@api_login_required
def get_dashboard_summary():
    return content_impl.get_dashboard_summary()


@studio_bp.route("/api/content/list", methods=["GET"])
@api_login_required
def list_content():
    limit = int(request.args.get("limit", 50))
    q = (request.args.get("q") or "").strip().lower()
    status = (request.args.get("status") or "").strip()
    return content_impl.list_content(limit=limit, q=q, status=status)


@studio_bp.route("/api/content/all", methods=["GET"])
@api_login_required
def get_all_content():
    limit = int(request.args.get("limit", 50))
    return content_impl.get_all_content(limit=limit)


@studio_bp.route("/api/content/<content_id>/schedule", methods=["POST"])
@api_login_required
def schedule_content(content_id: str):
    return content_impl.schedule_content(content_id)


@studio_bp.route("/api/content/<content_id>/unschedule", methods=["POST"])
@api_login_required
def unschedule_content(content_id: str):
    return content_impl.unschedule_content(content_id)


@studio_bp.route("/api/content/<content_id>/regenerate", methods=["POST"])
@api_login_required
def regenerate_content_by_id(content_id: str):
    return content_impl.regenerate_content_by_id(content_id)


@studio_bp.route("/api/content/regenerate", methods=["POST"])
@api_login_required
def regenerate_content_legacy():
    return content_impl.regenerate_content_legacy()


@studio_bp.route("/api/actions/publish-content", methods=["POST"])
@api_login_required
def publish_specific_content():
    return publishing_impl.publish_specific_content(_resolve_request_data())


@studio_bp.route("/api/actions/publish-next", methods=["POST"])
@api_login_required
def publish_next():
    return publishing_impl.publish_next()


@studio_bp.route("/api/actions/publish-now", methods=["POST"])
@api_login_required
def publish_now():
    return publishing_impl.publish_now(_resolve_request_data())


@studio_bp.route("/api/actions/schedule", methods=["POST"])
@api_login_required
def run_scheduler():
    return publishing_impl.run_scheduler(_resolve_request_data())


@studio_bp.route("/api/actions/sync-analytics", methods=["POST"])
@api_login_required
def sync_analytics():
    return publishing_impl.sync_analytics()
