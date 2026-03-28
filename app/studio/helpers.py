"""Shared helper functions for the Studio blueprint."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import config

logger = config.get_logger("studio")

AUTO_PUBLISHABLE_FORMATS = {"post", "carousel"}
DRAFT_ONLY_FORMATS = {"story_sequence", "reel_script"}


def _client():
    return config.get_database_client()


def _current_user_id() -> str:
    from flask_login import current_user

    return current_user.id


def _resolve_request_data(request) -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def _resolve_studio_user_id(requested_user_id: str) -> str:
    requested = str(requested_user_id or _current_user_id()).strip()
    if requested != _current_user_id():
        raise PermissionError("You can only generate content for your own account.")
    return requested


def _normalize_ui_language(language: Optional[str], fallback: str = "en") -> str:
    value = str(language or fallback).strip().lower()
    return value if value in {"ar", "fr", "en"} else fallback


def _normalize_platforms(raw_value: Any) -> str:
    if isinstance(raw_value, (list, tuple, set)):
        tokens = [str(item or "").strip().lower() for item in raw_value]
    else:
        cleaned = str(raw_value or "").replace("[", "").replace("]", "")
        cleaned = cleaned.replace('"', "").replace("'", "")
        tokens = [token.strip().lower() for token in cleaned.split(",")]

    allowed: list[str] = []
    for token in tokens:
        if token in {"facebook", "instagram"} and token not in allowed:
            allowed.append(token)
    return ",".join(allowed or ["facebook"])


def _build_studio_article(topic: str, content_format: str) -> Dict[str, str]:
    cleaned_topic = str(topic or "").strip()
    title = cleaned_topic or f"{content_format.replace('_', ' ').title()} idea"
    summary = cleaned_topic or "Create a clear, valuable draft that is ready for review and scheduling."
    return {"title": title, "content": summary}


def _extract_language_from_content(row: Dict[str, Any]) -> str:
    target = str(row.get("target_audience") or "").strip().lower()
    if target in {"ar", "fr", "en"}:
        return target

    raw_generated = row.get("generated_text")
    if isinstance(raw_generated, str) and raw_generated.strip().startswith(("{", "[")):
        try:
            payload = json.loads(raw_generated)
            if isinstance(payload, dict):
                return _normalize_ui_language(payload.get("language"), fallback="en")
        except (TypeError, ValueError) as exc:
            logger.debug("Could not parse generated content language: %s", exc)

    return "en"


def _load_active_page_context(user_id: str) -> Dict[str, Any]:
    try:
        result = (
            _client()
            .table("managed_pages")
            .select("page_id, page_name, instagram_account_id, language")
            .eq("user_id", user_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not result.data:
            return {
                "page_id": "",
                "page_name": "Connected page",
                "platforms": "facebook",
                "platform_label": "Facebook",
                "language": "",
            }

        row = result.data[0]
        has_instagram = bool(row.get("instagram_account_id"))
        return {
            "page_id": row.get("page_id") or "",
            "page_name": row.get("page_name") or "Connected page",
            "platforms": "facebook,instagram" if has_instagram else "facebook",
            "platform_label": "Facebook + Instagram" if has_instagram else "Facebook",
            "language": _normalize_ui_language(row.get("language"), fallback="en"),
        }
    except Exception as exc:
        logger.warning("Could not load active page context for %s: %s", user_id[:8], exc)
        return {
            "page_id": "",
            "page_name": "Connected page",
            "platforms": "facebook",
            "platform_label": "Facebook",
            "language": "",
        }


def _build_content_preview(row: Dict[str, Any]) -> str:
    hook = str(row.get("hook") or "").strip()
    if hook:
        return hook

    post_type = str(row.get("post_type") or "post").strip().lower()
    parsed_payload = _parse_structured_generated_text(row.get("generated_text"))
    if post_type == "carousel":
        slides = parsed_payload.get("slides") or []
        first_slide = slides[0] if isinstance(slides, list) and slides else {}
        return (
            str(first_slide.get("headline") or "").strip()
            or str(first_slide.get("body") or "").strip()
            or str(parsed_payload.get("caption") or "").strip()
        )
    if post_type == "story_sequence":
        frames = parsed_payload.get("frames") or []
        first_frame = frames[0] if isinstance(frames, list) and frames else {}
        return str(first_frame.get("text") or "").strip()
    if post_type == "reel_script":
        return str(parsed_payload.get("hook") or "").strip() or str(parsed_payload.get("cta") or "").strip()
    return str(row.get("generated_text") or "").strip()


def _load_runtime_profile(
    user_id: str,
    language: Optional[str] = None,
    tone: Optional[str] = None,
):
    from user_config import get_user_config

    runtime_profile = get_user_config(user_id)
    resolved_language = _normalize_ui_language(language, fallback=runtime_profile.content_language or "en")
    runtime_profile.content_language = resolved_language
    resolved_tone = str(tone or runtime_profile.content_tone or "").strip().lower()
    if resolved_tone in config.SUPPORTED_CONTENT_TONES:
        runtime_profile.content_tone = resolved_tone

    content_languages = list(getattr(runtime_profile, "content_languages", []) or [])
    content_languages = [lang for lang in content_languages if lang != resolved_language]
    runtime_profile.content_languages = [resolved_language] + content_languages
    return runtime_profile


def _normalize_generated_content(content_format: str, raw_response: str, language: str) -> Dict[str, Any]:
    from ai_generator import normalize_generated_payload, parse_json_response

    parsed = parse_json_response(raw_response)
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}
    return normalize_generated_payload(content_format, parsed, language)


def _parse_structured_generated_text(raw_value: Any) -> Dict[str, Any]:
    if isinstance(raw_value, dict):
        return dict(raw_value)
    if not isinstance(raw_value, str):
        return {}
    stripped = raw_value.strip()
    if not stripped.startswith(("{", "[")):
        return {}
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_draft_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    post_type = str(row.get("post_type") or "post").strip().lower()
    language = _extract_language_from_content(row)
    hashtags = row.get("hashtags") or []
    hook = row.get("hook")
    image_path = row.get("image_path") or ""
    raw_generated = row.get("generated_text") or ""
    parsed_payload = _parse_structured_generated_text(raw_generated)

    if post_type == "carousel":
        normalized["content_normalized"] = {
            "format": "carousel",
            "language": _normalize_ui_language(parsed_payload.get("language"), fallback=language),
            "slides": parsed_payload.get("slides") or [],
            "caption": str(parsed_payload.get("caption") or "").strip(),
            "hashtags": parsed_payload.get("hashtags") or hashtags,
        }
    elif post_type == "story_sequence":
        normalized["content_normalized"] = {
            "format": "story_sequence",
            "language": _normalize_ui_language(parsed_payload.get("language"), fallback=language),
            "frames": parsed_payload.get("frames") or [],
            "hashtags": parsed_payload.get("hashtags") or hashtags,
        }
    elif post_type == "reel_script":
        normalized["content_normalized"] = {
            "format": "reel_script",
            "language": _normalize_ui_language(parsed_payload.get("language"), fallback=language),
            "hook": str(parsed_payload.get("hook") or hook or "").strip(),
            "points": parsed_payload.get("points") or [],
            "cta": str(parsed_payload.get("cta") or "").strip(),
            "hashtags": parsed_payload.get("hashtags") or hashtags,
        }
    else:
        normalized["content_normalized"] = {
            "format": "post",
            "language": language,
            "hook": str(hook or "").strip(),
            "body": str(raw_generated or "").strip(),
            "cta": str(row.get("call_to_action") or "").strip(),
            "hashtags": hashtags,
            "image_path": image_path,
        }

    return normalized


def _build_record_payload(
    content_format: str,
    content: Dict[str, Any],
    status: str = "draft_only",
    article_id: str = "",
    user_id: str = "",
) -> Dict[str, Any]:
    normalized_format = str(content_format or "post").strip().lower()
    language = _normalize_ui_language(content.get("language"), fallback="en").upper()
    record = {
        "article_id": article_id or None,
        "post_type": normalized_format,
        "generated_text": "",
        "hashtags": content.get("hashtags") or [],
        "hook": None,
        "call_to_action": None,
        "target_audience": language,
        "image_path": "",
        "arabic_text": "",
        "status": status,
        "user_id": user_id or _current_user_id(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if normalized_format == "post":
        record["generated_text"] = str(content.get("body") or "").strip()
        record["hook"] = str(content.get("hook") or "").strip() or None
        record["call_to_action"] = str(content.get("cta") or "").strip() or None
        if language == "AR":
            record["arabic_text"] = str(content.get("hook") or content.get("body") or "").strip()
        return record

    record["generated_text"] = json.dumps(content, ensure_ascii=False)
    if normalized_format == "carousel":
        slides = content.get("slides") or []
        first_slide = slides[0] if isinstance(slides, list) and slides else {}
        record["hook"] = str(first_slide.get("headline") or "").strip() or None
        record["call_to_action"] = str(content.get("caption") or "").strip() or None
        if language == "AR":
            record["arabic_text"] = str(first_slide.get("headline") or "").strip()
    elif normalized_format == "story_sequence":
        frames = content.get("frames") or []
        first_frame = frames[0] if isinstance(frames, list) and frames else {}
        record["hook"] = str(first_frame.get("text") or "").strip() or None
    elif normalized_format == "reel_script":
        record["hook"] = str(content.get("hook") or "").strip() or None
        record["call_to_action"] = str(content.get("cta") or "").strip() or None
    return record


def _save_draft_record(
    content_format: str,
    content: Dict[str, Any],
    user_id: str,
    article_id: str = "",
    status: str = "draft_only",
) -> Dict[str, Any]:
    record = _build_record_payload(content_format=content_format, content=content, status=status, article_id=article_id, user_id=user_id)
    result = _client().table("processed_content").insert(record).execute()
    return (result.data or [record])[0]


def _load_owned_content_row(content_id: str, fields: str = "*") -> Optional[Dict[str, Any]]:
    result = (
        _client()
        .table("processed_content")
        .select(fields)
        .eq("id", content_id)
        .eq("user_id", _current_user_id())
        .single()
        .execute()
    )
    return result.data or None


def _create_schedule_record(content_id: str, scheduled_time: str, timezone_name: str, platforms: str = "facebook") -> Optional[Dict[str, Any]]:
    result = (
        _client()
        .table("scheduled_posts")
        .insert(
            {
                "user_id": _current_user_id(),
                "content_id": content_id,
                "scheduled_time": scheduled_time,
                "timezone": timezone_name,
                "status": "scheduled",
                "platforms": platforms,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .execute()
    )
    return result.data[0] if result.data else None


def _clear_schedule_records(content_id: str) -> None:
    (
        _client()
        .table("scheduled_posts")
        .update({"status": "cancelled"})
        .eq("content_id", content_id)
        .eq("user_id", _current_user_id())
        .eq("status", "scheduled")
        .execute()
    )


def _generate_studio_content(
    content_format: str,
    language: str,
    topic: str,
    user_id: str,
    instruction: str = "",
    tone: Optional[str] = None,
) -> Dict[str, Any]:
    from ai_generator import build_generation_prompt, build_regeneration_prompt
    from ai_provider import generate as run_ai_generation

    runtime_profile = _load_runtime_profile(user_id=user_id, language=language, tone=tone)
    article = _build_studio_article(topic=topic, content_format=content_format)
    if instruction:
        prompt = build_regeneration_prompt(
            existing_content=article,
            content_format=content_format,
            language=runtime_profile.content_language,
            tone=runtime_profile.content_tone,
            instruction=instruction,
        )
    else:
        prompt = build_generation_prompt(
            article=article,
            content_format=content_format,
            language=runtime_profile.content_language,
            tone=runtime_profile.content_tone,
        )
    raw_response = run_ai_generation(prompt, runtime_profile, max_tokens=1536 if content_format == "carousel" else 1024, temperature=0.7)
    return _normalize_generated_content(content_format=content_format, raw_response=raw_response, language=runtime_profile.content_language)


def _regenerate_existing_content(content_row: Dict[str, Any], instruction: str, tone: Optional[str] = None) -> Dict[str, Any]:
    from ai_generator import build_regeneration_prompt
    from ai_provider import generate as run_ai_generation

    user_id = str(content_row.get("user_id") or _current_user_id())
    content_format = str(content_row.get("post_type") or "post").strip().lower()
    language = _extract_language_from_content(content_row)
    runtime_profile = _load_runtime_profile(user_id=user_id, language=language, tone=tone)
    prompt = build_regeneration_prompt(
        existing_content=content_row,
        content_format=content_format,
        language=runtime_profile.content_language,
        tone=runtime_profile.content_tone,
        instruction=instruction,
    )
    raw_response = run_ai_generation(prompt, runtime_profile, max_tokens=1536 if content_format == "carousel" else 1024, temperature=0.7)
    regenerated = _normalize_generated_content(content_format=content_format, raw_response=raw_response, language=runtime_profile.content_language)
    update_payload = _build_record_payload(content_format=content_format, content=regenerated, status="draft_only", article_id=str(content_row.get("article_id") or ""), user_id=user_id)
    _client().table("processed_content").update(update_payload).eq("id", content_row["id"]).eq("user_id", user_id).execute()
    return regenerated
