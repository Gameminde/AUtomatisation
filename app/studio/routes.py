"""Content Studio API routes - thin compatibility layer over focused modules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from flask import Blueprint, jsonify, request
from flask_login import current_user
from werkzeug.utils import secure_filename

import config
from app.utils import api_login_required, get_user_settings, require_user_settings_update
from . import content as content_impl
from . import helpers as helpers_impl
from . import payloads as payloads_impl
from . import publishing as publishing_impl
from . import workflow as workflow_impl

logger = config.get_logger("studio")

studio_bp = Blueprint("studio", __name__)

AUTO_PUBLISHABLE_FORMATS = helpers_impl.AUTO_PUBLISHABLE_FORMATS
DRAFT_ONLY_FORMATS = helpers_impl.DRAFT_ONLY_FORMATS
_STUDIO_UPLOAD_DIR = (config.BASE_DIR / "downloaded_images").resolve()
_STUDIO_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_STUDIO_UPLOAD_FALLBACK_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_STUDIO_UPLOAD_MAX_BYTES = 12 * 1024 * 1024

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


def _normalize_template_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}

    def _bounded_number(key: str, minimum: int, maximum: int) -> None:
        if key not in data:
            return
        try:
            value = int(float(data.get(key)))
        except (TypeError, ValueError):
            return
        normalized[key] = max(minimum, min(maximum, value))

    for key in ("brandName", "socialHandle", "backgroundImagePath"):
        if key in data:
            normalized[key] = str(data.get(key) or "").strip()[:512]

    _bounded_number("backgroundDensity", 0, 100)
    _bounded_number("backgroundZoom", 40, 180)
    _bounded_number("backgroundOffsetX", -40, 40)
    _bounded_number("backgroundOffsetY", -40, 40)
    _bounded_number("mediaWidth", 30, 100)
    _bounded_number("mediaHeight", 110, 260)
    _bounded_number("mediaZoom", 40, 220)
    _bounded_number("mediaClarity", 80, 140)
    _bounded_number("mediaOffsetX", -60, 60)
    _bounded_number("mediaOffsetY", -60, 60)
    _bounded_number("titleScale", 80, 140)
    _bounded_number("titleOffsetY", -24, 24)
    _bounded_number("titleWidth", 68, 100)

    media_fit = str(data.get("mediaFit") or "").strip()
    if media_fit in {"contain", "cover"}:
        normalized["mediaFit"] = media_fit

    title_font_family = str(data.get("titleFontFamily") or "").strip()
    if title_font_family in {"display", "body", "mono"}:
        normalized["titleFontFamily"] = title_font_family

    title_color = str(data.get("titleColor") or "").strip()
    if len(title_color) == 7 and title_color.startswith("#"):
        try:
            int(title_color[1:], 16)
            normalized["titleColor"] = title_color.lower()
        except ValueError:
            pass

    for key in ("showSocialStrip", "showBrandBadge"):
        if key in data:
            normalized[key] = bool(data.get(key))

    return normalized


def _load_template_defaults_for_user(user_id: str) -> Dict[str, Any]:
    raw = str((get_user_settings(user_id) or {}).get("studio_template_defaults") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return _normalize_template_defaults(parsed if isinstance(parsed, dict) else {})


def _save_uploaded_studio_image(file_storage, prefix: str) -> tuple[Path, str]:
    filename = secure_filename(str(getattr(file_storage, "filename", "") or ""))
    extension = Path(filename).suffix.lower()
    if extension not in _STUDIO_UPLOAD_EXTENSIONS:
        extension = _STUDIO_UPLOAD_FALLBACK_EXTENSIONS.get(str(getattr(file_storage, "mimetype", "") or "").lower(), "")
    if extension not in _STUDIO_UPLOAD_EXTENSIONS:
        raise ValueError("Upload a JPG, PNG, WEBP, or GIF image.")

    payload = file_storage.read()
    if not payload:
        raise ValueError("Upload an image file first.")
    if len(payload) > _STUDIO_UPLOAD_MAX_BYTES:
        raise ValueError("Image upload is too large. Max size is 12 MB.")

    _STUDIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_name = f"studio-{prefix}-{uuid4().hex}{extension}"
    saved_path = (_STUDIO_UPLOAD_DIR / saved_name).resolve()
    if saved_path.parent != _STUDIO_UPLOAD_DIR:
        raise ValueError("Invalid upload destination.")
    saved_path.write_bytes(payload)
    return saved_path, f"/media/public/{saved_name}"


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


@studio_bp.route("/api/studio/template-settings", methods=["GET", "POST"])
@api_login_required
def studio_template_settings():
    if request.method == "GET":
        return _api_success(template_defaults=_load_template_defaults_for_user(current_user.id))

    normalized = _normalize_template_defaults(_resolve_request_data())
    try:
        require_user_settings_update(
            current_user.id,
            {"studio_template_defaults": json.dumps(normalized, ensure_ascii=False)},
        )
    except RuntimeError as exc:
        return _api_error(str(exc), 500)
    return _api_success(template_defaults=normalized)


@studio_bp.route("/api/studio/assets/upload", methods=["POST"])
@api_login_required
def studio_upload_asset():
    try:
        kind = str(request.form.get("kind") or "").strip().lower()
        file_storage = request.files.get("file")
        if not file_storage:
            return _api_error("Upload an image file first.", 400)

        if kind == "main-image":
            content_id = str(request.form.get("content_id") or "").strip()
            if not content_id:
                return _api_error("content_id required for main image uploads", 400)
            owned_content = _load_owned_content_row(content_id, "id")
            if not owned_content:
                return _api_error("Content not found", 404)
            saved_path, public_url = _save_uploaded_studio_image(file_storage, "content")
            relative_path = f"downloaded_images/{saved_path.name}"
            result = (
                _client()
                .table("processed_content")
                .update({"image_path": relative_path})
                .eq("id", content_id)
                .eq("user_id", current_user.id)
                .execute()
            )
            if not result.data:
                return _api_error("Content not found", 404)
            return _api_success(
                kind=kind,
                content_id=content_id,
                image_path=public_url,
                image_url=f"/api/content/{content_id}/image",
                public_url=public_url,
            )

        if kind == "background":
            _saved_path, public_url = _save_uploaded_studio_image(file_storage, "background")
            return _api_success(
                kind=kind,
                backgroundImagePath=public_url,
                public_url=public_url,
            )

        return _api_error("Unsupported upload target", 400)
    except ValueError as exc:
        return _api_error(str(exc), 400)
    except Exception as exc:
        logger.error("Error uploading studio asset: %s", exc)
        return _api_error(str(exc), 500)


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
