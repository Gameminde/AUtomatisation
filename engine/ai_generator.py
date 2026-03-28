"""Generate viral content using the configured AI provider with batching support."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import config
from ai_provider import AIProviderError, generate as run_ai_generation

logger = config.get_logger("ai_generator")


# Batch prompt template - generates content for multiple articles in one call.
# The prompt was originally adapted from an internal local writing reference and
# is now maintained directly in code.
_DEFAULT_BATCH_PROMPT = """أنت منشئ محتوى فيروسي محترف لفيسبوك، متخصص في التكنولوجيا والألعاب للجمهور العربي.

🎯 المبدأ الأساسي: "السطر الأول = كل شيء" - يجب أن توقف القارئ عن التمرير فوراً!

📰 المقالات للمعالجة ({count} مقال):
{articles_json}

لكل مقال، أنشئ محتوى يتبع هذه القواعد الذهبية:

═══════════════════════════════════════════════════════════
🔥 1. الافتتاحية (HOOK) - أهم جزء!
═══════════════════════════════════════════════════════════
اختر نوعاً من هذه الاستراتيجيات:
• سؤال صادم: "هل تصدق أن...؟"
• إحصائية مفاجئة: "90% من المستخدمين لا يعرفون هذا!"
• تصريح جريء: "نسيت كل ما تعرفه عن..."
• إيموجي + تحذير: "🚨 خبر عاجل!"
• قصة شخصية: "اكتشفت للتو شيئاً غيّر كل شيء..."

⚠️ مهم: أسماء الماركات تبقى بالإنجليزية (ChatGPT, OpenAI, Tesla, ASUS, Apple...)

═══════════════════════════════════════════════════════════
💎 2. المحتوى (BODY) - قيمة حقيقية!
═══════════════════════════════════════════════════════════
• قدم معلومة جديدة أو نصيحة عملية
• "هل تعلم أن..." أو "نصيحة سريعة:..."
• استخدم أسلوب المحادثة (كأنك تتحدث مع صديق)
• جمل قصيرة ومؤثرة
• فقرات قصيرة (2-3 أسطر)
• 2-3 إيموجي مناسبة 🎮🤖💡

═══════════════════════════════════════════════════════════
📣 3. دعوة للتفاعل (CTA) - ضرورية!
═══════════════════════════════════════════════════════════
اختر سؤالاً يدعو للتعليق:
• "ما رأيكم؟ شاركونا في التعليقات! 💬"
• "هل جربتم هذا من قبل؟"
• "من معي في هذا الرأي؟ 🙋‍♂️"
• "تاغ شخص يحتاج يعرف هذا!"

═══════════════════════════════════════════════════════════
#️⃣ 4. الهاشتاقات
═══════════════════════════════════════════════════════════
5-7 هاشتاقات مزيج من:
- عربية: #تقنية #الذكاء_الاصطناعي #ألعاب
- إنجليزية للماركات: #ChatGPT #OpenAI #Tesla

أجب بـ JSON فقط (بدون أي نص إضافي):
[
  {{
    "article_index": 0,
    "text_post": {{
      "hook": "🚨 الخبر الذي سيغير كل شيء!...",
      "body": "هل تعلم أن... [محتوى قيم ومفيد]...",
      "cta": "ما رأيكم؟ شاركونا تجربتكم! 💬",
      "hashtags": ["#الذكاء_الاصطناعي", "#تقنية", "#ChatGPT"]
    }}
  }}
]
"""


# Single article prompt (fallback) - v2.0 simplified, no Reels
# Supports style parameter: emotional, news, casual, motivation
_DEFAULT_SINGLE_PROMPT = """أنت منشئ محتوى فيروسي محترف لفيسبوك متخصص في التكنولوجيا والألعاب.

🎯 القاعدة الذهبية: "السطر الأول يحدد كل شيء!" - اجعل القارئ يتوقف فوراً!

📰 المقال:
العنوان: {title}
الملخص: {summary}

📝 اكتب منشوراً يتبع هذه البنية:

1. 🔥 HOOK (افتتاحية صادمة - 10 كلمات كحد أقصى)
2. 💎 BODY (محتوى قيم - 50-80 كلمة)
3. 📣 CTA (دعوة للتفاعل)
4. #️⃣ HASHTAGS (5-7 مزيج عربي/إنجليزية)

⚠️ أسماء الماركات بالإنجليزية: ChatGPT, Tesla, Apple, OpenAI

أجب بـ JSON فقط:
{{
  "hook": "🚨 [افتتاحية صادمة]...",
  "body": "[محتوى قيم]...",
  "cta": "ما رأيكم؟ 💬",
  "hashtags": ["#تقنية", "#ChatGPT"]
}}
"""


def get_prompts() -> Dict[str, str]:
    """Return current prompt templates (custom env override or defaults)."""
    return {
        "batch": os.environ.get("CUSTOM_BATCH_PROMPT", "").strip() or _DEFAULT_BATCH_PROMPT,
        "single": os.environ.get("CUSTOM_SINGLE_PROMPT", "").strip() or _DEFAULT_SINGLE_PROMPT,
    }


def set_prompts(batch: Optional[str] = None, single: Optional[str] = None) -> None:
    """Update prompt env vars at runtime."""
    if batch is not None:
        os.environ["CUSTOM_BATCH_PROMPT"] = batch
    if single is not None:
        os.environ["CUSTOM_SINGLE_PROMPT"] = single


# Module-level aliases (for backward compat + runtime override)
BATCH_PROMPT_TEMPLATE = get_prompts()["batch"]
SINGLE_PROMPT_TEMPLATE = get_prompts()["single"]

LEGACY_POST_TYPE_MAP = {
    "text": "post",
    "photo": "post",
    "story": "story_sequence",
    "reel": "reel_script",
}

SUPPORTED_CONTENT_FORMATS = {"post", "carousel", "story_sequence", "reel_script"}
DRAFT_ONLY_FORMATS = {"story_sequence", "reel_script"}


def normalize_content_format(post_type: Optional[str]) -> str:
    candidate = str(post_type or "post").strip().lower()
    candidate = LEGACY_POST_TYPE_MAP.get(candidate, candidate)
    if candidate in SUPPORTED_CONTENT_FORMATS:
        return candidate
    return "post"


def _resolve_generation_preferences(
    runtime_profile: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> tuple[str, str]:
    profile = runtime_profile
    if profile is None and user_id:
        try:
            from user_config import get_user_config

            profile = get_user_config(user_id)
        except Exception as exc:
            logger.debug("Could not resolve generation preferences for %s: %s", user_id[:8], exc)
            profile = None

    language = "en"
    tone = "professional"
    if profile is not None:
        language = (
            getattr(profile, "content_language", "")
            or (getattr(profile, "content_languages", []) or ["en"])[0]
            or "en"
        )
        tone = getattr(profile, "content_tone", "") or "professional"
    return str(language).lower(), str(tone).lower()


def _truncate_words(text: str, max_words: int) -> str:
    words = [word for word in str(text or "").strip().split() if word]
    return " ".join(words[:max_words]).strip()


def _coerce_hashtags(raw_value: Any) -> List[str]:
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()][:8]
    if isinstance(raw_value, str):
        return [token.strip() for token in raw_value.split() if token.strip().startswith("#")][:8]
    return []


def _sanitize_post_payload(payload: Dict[str, Any], language: str) -> Dict[str, Any]:
    return {
        "format": "post",
        "language": str(payload.get("language") or language or "en").lower(),
        "hook": str(payload.get("hook") or "").strip(),
        "body": str(payload.get("body") or "").strip(),
        "cta": str(payload.get("cta") or payload.get("call_to_action") or "").strip(),
        "hashtags": _coerce_hashtags(payload.get("hashtags")),
    }


def _sanitize_carousel_payload(payload: Dict[str, Any], language: str) -> Dict[str, Any]:
    raw_slides = payload.get("slides") or []
    slides: List[Dict[str, Any]] = []
    if isinstance(raw_slides, list):
        for index, slide in enumerate(raw_slides[:5], start=1):
            if not isinstance(slide, dict):
                continue
            slides.append(
                {
                    "slide_number": int(slide.get("slide_number") or index),
                    "headline": _truncate_words(str(slide.get("headline") or ""), 8),
                    "body": _truncate_words(str(slide.get("body") or ""), 20),
                    "visual_suggestion": str(slide.get("visual_suggestion") or "").strip(),
                }
            )
    return {
        "format": "carousel",
        "language": str(payload.get("language") or language or "en").lower(),
        "slides": slides,
        "caption": str(payload.get("caption") or "").strip(),
        "hashtags": _coerce_hashtags(payload.get("hashtags")),
    }


def _sanitize_story_payload(payload: Dict[str, Any], language: str) -> Dict[str, Any]:
    frames: List[Dict[str, Any]] = []
    raw_frames = payload.get("frames") or payload.get("story_frames") or []
    if isinstance(raw_frames, list):
        for index, frame in enumerate(raw_frames[:3], start=1):
            if not isinstance(frame, dict):
                continue
            frames.append(
                {
                    "frame_number": int(frame.get("frame_number") or index),
                    "text": str(frame.get("text") or "").strip(),
                    "visual_suggestion": str(frame.get("visual_suggestion") or "").strip(),
                }
            )
    return {
        "format": "story_sequence",
        "language": str(payload.get("language") or language or "en").lower(),
        "frames": frames,
    }


def _sanitize_reel_script_payload(payload: Dict[str, Any], language: str) -> Dict[str, Any]:
    raw_points = payload.get("points") or payload.get("three_points") or []
    points = [str(point).strip() for point in raw_points if str(point).strip()][:3] if isinstance(raw_points, list) else []
    return {
        "format": "reel_script",
        "language": str(payload.get("language") or language or "en").lower(),
        "hook": str(payload.get("hook") or "").strip(),
        "points": points,
        "cta": str(payload.get("cta") or payload.get("call_to_action") or "").strip(),
    }


def normalize_generated_payload(
    post_type: Optional[str],
    payload: Any,
    language: str,
) -> Dict[str, Any]:
    content_format = normalize_content_format(post_type)
    payload_dict = payload if isinstance(payload, dict) else {}
    if content_format == "carousel":
        return _sanitize_carousel_payload(payload_dict, language)
    if content_format == "story_sequence":
        return _sanitize_story_payload(payload_dict, language)
    if content_format == "reel_script":
        return _sanitize_reel_script_payload(payload_dict, language)
    return _sanitize_post_payload(payload_dict, language)


def build_generation_prompt(
    article: dict,
    content_format: Optional[str],
    language: str,
    tone: str,
) -> str:
    return _build_single_prompt(
        article,
        normalize_content_format(content_format),
        language,
        tone,
    )


def build_regeneration_prompt(
    existing_content: dict,
    content_format: Optional[str],
    language: str,
    tone: str,
    instruction: str = "",
) -> str:
    format_name = normalize_content_format(content_format)
    hook = existing_content.get("hook", "")
    body = existing_content.get("generated_text", "")
    prompt = build_generation_prompt(
        {
            "title": hook or existing_content.get("title", "") or "Existing draft",
            "content": (
                f"Current content:\n{body}\n\n"
                f"Existing metadata:\n{json.dumps(existing_content, ensure_ascii=False)}"
            ),
        },
        format_name,
        language,
        tone,
    )
    if instruction:
        prompt += f"\nAdditional instruction: {instruction.strip()}\n"
    return prompt


def _build_single_prompt(article: dict, content_format: str, language: str, tone: str) -> str:
    title = article.get("title", "")
    summary = (article.get("content") or "")[:1200]
    if content_format == "carousel":
        return f"""You create publishable Facebook carousel content.

Target language: {language}
Target tone: {tone}
Article title: {title}
Article summary: {summary}

Return JSON only using this exact structure:
{{
  "format": "carousel",
  "language": "{language}",
  "slides": [
    {{
      "slide_number": 1,
      "headline": "headline here",
      "body": "main slide text here",
      "visual_suggestion": "description of what image should show"
    }}
  ],
  "caption": "Main post caption for Facebook",
  "hashtags": ["tag1", "tag2"]
}}

Rules:
- Maximum 5 slides.
- Each headline must be maximum 8 words.
- Each body must be maximum 20 words.
- Keep slides concise, clear, and publishable.
"""
    if content_format == "story_sequence":
        return f"""You create Instagram and Facebook story sequences.

Target language: {language}
Target tone: {tone}
Article title: {title}
Article summary: {summary}

Return JSON only:
{{
  "format": "story_sequence",
  "language": "{language}",
  "frames": [
    {{
      "frame_number": 1,
      "text": "Story frame text",
      "visual_suggestion": "What the frame should show"
    }}
  ]
}}

Rules:
- Return exactly 3 frames.
- Keep each frame short and visual.
"""
    if content_format == "reel_script":
        return f"""You create short-form reel scripts.

Target language: {language}
Target tone: {tone}
Article title: {title}
Article summary: {summary}

Return JSON only:
{{
  "format": "reel_script",
  "language": "{language}",
  "hook": "Opening hook",
  "points": ["Point 1", "Point 2", "Point 3"],
  "cta": "Call to action"
}}

Rules:
- Give exactly 3 points.
- Make it clear enough for a creator to record manually.
"""
    return f"""You create concise social media posts for Facebook and Instagram.

Target language: {language}
Target tone: {tone}
Article title: {title}
Article summary: {summary}

Return JSON only:
{{
  "format": "post",
  "language": "{language}",
  "hook": "Opening hook",
  "body": "Main post body",
  "cta": "Call to action",
  "hashtags": ["tag1", "tag2"]
}}
"""


class ProviderTextClient:
    """Adapter that exposes a `.generate()` method backed by engine.ai_provider."""

    def __init__(self, runtime_profile: Any):
        self.runtime_profile = runtime_profile

    def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
        return run_ai_generation(
            prompt,
            self.runtime_profile,
            max_tokens=max_tokens,
            temperature=temperature,
        )


def _build_runtime_ai_profile(
    user_id: Optional[str] = None,
    ai_key: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    provider_fallback: Optional[str] = None,
) -> Any:
    """Resolve the runtime AI profile for the current generation request."""
    if user_id:
        from user_config import get_user_config

        resolved = get_user_config(user_id)
        if ai_key:
            resolved.ai_api_key = ai_key
        if provider:
            resolved.ai_provider = provider
        if model:
            resolved.ai_model = model
        if provider_fallback is not None:
            resolved.provider_fallback = provider_fallback
        return resolved

    default_provider = "openrouter" if any(config.OPENROUTER_API_KEYS) else config.SUPPORTED_AI_PROVIDERS[0]
    return SimpleNamespace(
        user_id="",
        ai_provider=provider or default_provider,
        provider_fallback=provider_fallback or "",
        ai_model=model or "",
        ai_api_key=ai_key or "",
    )


def get_ai_client_instance(
    user_id: Optional[str] = None,
    ai_key: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    provider_fallback: Optional[str] = None,
) -> ProviderTextClient:
    """Return a text-generation client wrapper for the configured provider."""
    return ProviderTextClient(
        _build_runtime_ai_profile(
            user_id=user_id,
            ai_key=ai_key,
            provider=provider,
            model=model,
            provider_fallback=provider_fallback,
        )
    )


def _generate_text(client, prompt: str, max_tokens: int, temperature: float) -> str:
    """Support both the newer `.generate()` API and older `.call()` clients."""
    if hasattr(client, "call"):
        return client.call(prompt, max_tokens=max_tokens, temperature=temperature)
    if hasattr(client, "generate"):
        return client.generate(prompt, max_tokens=max_tokens, temperature=temperature)
    raise TypeError(f"Unsupported AI client: {type(client)!r}")


def fix_json_string(text: str) -> str:
    """Attempt to fix common JSON issues from LLM output."""
    import re

    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # Fix unescaped newlines in strings
    # This is a simplified fix - handles common cases
    lines = text.split("\n")
    fixed_lines = []
    in_string = False
    for line in lines:
        # Count unescaped quotes to track if we're in a string
        quote_count = len(re.findall(r'(?<!\\)"', line))
        if in_string:
            # If we're continuing a string from previous line, escape this line
            fixed_lines.append(line.replace("\n", "\\n"))
        else:
            fixed_lines.append(line)
        # Toggle in_string if odd number of quotes
        if quote_count % 2 == 1:
            in_string = not in_string

    return "\n".join(fixed_lines)


def parse_json_response(text: str) -> any:
    """Extract and parse JSON from model response with error recovery."""
    stripped = text.strip()

    # Remove markdown code blocks if present
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        # Find start and end of code block
        start_idx = 1 if lines[0].startswith("```") else 0
        end_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break
        stripped = "\n".join(lines[start_idx:end_idx])

    # Find JSON array or object
    start_array = stripped.find("[")
    start_obj = stripped.find("{")

    json_text = None

    if start_array != -1 and (start_obj == -1 or start_array < start_obj):
        # It's an array
        end = stripped.rfind("]")
        if end != -1:
            json_text = stripped[start_array : end + 1]
    elif start_obj != -1:
        # It's an object
        end = stripped.rfind("}")
        if end != -1:
            json_text = stripped[start_obj : end + 1]

    if json_text is None:
        raise ValueError(f"No valid JSON found in response: {stripped[:200]}...")

    # Try parsing directly first
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        pass

    # Try fixing common issues
    try:
        fixed = fix_json_string(json_text)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Last resort: try to extract individual objects if array fails
    if json_text.startswith("["):
        try:
            # Try to find complete objects
            import re

            objects = re.findall(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", json_text)
            if objects:
                results = []
                for obj in objects:
                    try:
                        results.append(json.loads(obj))
                    except json.JSONDecodeError:
                        continue
                if results:
                    logger.warning("Recovered %d objects from malformed JSON array", len(results))
                    return results
        except Exception:
            pass

    raise ValueError(f"Failed to parse JSON after recovery attempts: {json_text[:300]}...")


def generate_batch(
    articles: List[dict],
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
    runtime_profile: Optional[Any] = None,
) -> List[Dict]:
    """
    Generate content for multiple articles in a single API call.

    Args:
        articles: List of article dicts with 'title' and 'content' keys
        client: Optional AI client (creates new one if not provided)

    Returns:
        List of generated content dicts
    """
    if not articles:
        return []

    if client is None:
        client = (
            ProviderTextClient(runtime_profile)
            if runtime_profile is not None
            else get_ai_client_instance(user_id=user_id)
        )

    # Format articles for prompt
    articles_for_prompt = []
    for i, article in enumerate(articles):
        articles_for_prompt.append(
            {
                "index": i,
                "title": article.get("title", ""),
                "summary": (article.get("content") or "")[:500],  # Limit summary length
            }
        )

    # A/B testing: select variant if enabled
    variant_id = None
    active_template = BATCH_PROMPT_TEMPLATE
    try:
        from ab_testing import pick_variant
        variant = pick_variant()
        if variant:
            active_template = variant["template"]
            variant_id = variant["id"]
            logger.info("A/B: using variant '%s'", variant["name"])
    except ImportError:
        pass

    prompt = active_template.format(
        count=len(articles),
        articles_json=json.dumps(articles_for_prompt, ensure_ascii=False, indent=2),
    )

    try:
        response = _generate_text(client, prompt, max_tokens=2000, temperature=0.7)
        results = parse_json_response(response)

        if not isinstance(results, list):
            results = [results]

        # Tag results with variant_id for A/B tracking
        if variant_id:
            for r in results:
                if isinstance(r, dict):
                    r["variant_id"] = variant_id

        logger.info("Batch generation successful: %d articles processed", len(results))
        return results

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse JSON response: %s", exc)
        raise
    except AIProviderError:
        raise
    except Exception as exc:
        logger.error("Batch generation failed: %s", exc)
        raise


def generate_single(
    article: dict,
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
    post_type: Optional[str] = None,
    runtime_profile: Optional[Any] = None,
) -> Dict:
    """
    Generate content for a single article (fallback method).

    Args:
        article: Article dict with 'title' and 'content'
        client: Optional AI client

    Returns:
        Generated content dict
    """
    if client is None:
        client = (
            ProviderTextClient(runtime_profile)
            if runtime_profile is not None
            else get_ai_client_instance(user_id=user_id)
        )

    content_format = normalize_content_format(post_type)
    language, tone = _resolve_generation_preferences(runtime_profile=runtime_profile, user_id=user_id)
    prompt = _build_single_prompt(article, content_format, language, tone)
    response = _generate_text(client, prompt, max_tokens=1024, temperature=0.7)
    parsed = parse_json_response(response)
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}
    return normalize_generated_payload(content_format, parsed, language)


def save_processed_content(
    article_id: str, post_type: str, payload: Dict,
    article_title: str = "", user_id: Optional[str] = None,
    runtime_profile: Optional[Any] = None,
) -> None:
    """Save generated content to Supabase and generate social image.

    Args:
        article_id:    Source raw_article id.
        post_type:     e.g. "text", "photo".
        payload:       AI-generated content dict.
        article_title: Used for image caption generation.
        user_id:       Tenant ID — tags the row so only this user sees it.
                       Required for multi-tenant operation.
    """
    db_client = config.get_database_client()

    canonical_post_type = normalize_content_format(post_type)
    target_language = str(payload.get("language") or "multi").upper()
    generated_text = ""
    hook = None
    call_to_action = None
    status = "drafted"
    hashtags = _coerce_hashtags(payload.get("hashtags"))

    # Generate social media image
    image_path = ""
    arabic_text = ""
    if canonical_post_type == "post":
        generated_text = str(payload.get("body") or "")
        hook = payload.get("hook")
        call_to_action = payload.get("cta")
        try:
            from image_pipeline import generate_social_post

            ai_client = (
                ProviderTextClient(runtime_profile)
                if runtime_profile is not None
                else get_ai_client_instance(user_id=user_id)
            )
            image_path, arabic_text = generate_social_post(
                article_id=article_id,
                title=article_title or payload.get("hook", ""),
                client=ai_client,
            )
            logger.info("Generated social image: %s", image_path)
        except Exception as e:
            logger.warning("Image generation failed (continuing): %s", e)
    else:
        generated_text = json.dumps(payload, ensure_ascii=False)
        if canonical_post_type == "carousel":
            slides = payload.get("slides") or []
            first_slide = slides[0] if isinstance(slides, list) and slides else {}
            hook = str(first_slide.get("headline") or "") or None
            call_to_action = payload.get("caption")
            arabic_text = str(first_slide.get("headline") or "")
        elif canonical_post_type == "story_sequence":
            frames = payload.get("frames") or []
            first_frame = frames[0] if isinstance(frames, list) and frames else {}
            hook = str(first_frame.get("text") or "") or None
            status = "draft_only"
        elif canonical_post_type == "reel_script":
            hook = payload.get("hook")
            call_to_action = payload.get("cta")
            status = "draft_only"

    record = {
        "article_id": article_id,
        "post_type": canonical_post_type,
        "generated_text": generated_text,
        "hashtags": hashtags,
        "hook": hook,
        "call_to_action": call_to_action,
        "target_audience": target_language,
        "image_path": image_path,
        "arabic_text": arabic_text,
        "status": status,
    }
    if user_id:
        record["user_id"] = user_id

    db_client.table("processed_content").insert(record).execute()
    logger.debug("Saved processed content for article %s (user_id=%s)", article_id, user_id)


def mark_article_processed(article_id: str, user_id: Optional[str] = None) -> None:
    """Mark article as processed in database.

    Args:
        article_id: Row id in raw_articles.
        user_id:    Tenant scope — restricts the UPDATE to this user's rows.
    """
    client = config.get_database_client()
    query = client.table("raw_articles").update({"status": "processed"}).eq("id", article_id)
    if user_id:
        query = query.eq("user_id", user_id)
    query.execute()


def mark_article_failed(article_id: str, error_message: str, user_id: Optional[str] = None) -> None:
    """Mark the source article as failed so it does not remain stuck in pending."""
    client = config.get_database_client()
    update_payload = {"status": "failed"}
    query = client.table("raw_articles").update(update_payload).eq("id", article_id)
    if user_id:
        query = query.eq("user_id", user_id)
    query.execute()
    logger.debug("Marked raw article %s as failed (user_id=%s)", article_id, user_id)


def save_failed_content(
    article_id: str,
    article_title: str,
    error_message: str,
    user_id: Optional[str] = None,
) -> None:
    """Persist a generation failure row so health and support tooling can see it."""
    db_client = config.get_database_client()
    record = {
        "article_id": article_id,
        "post_type": "text",
        "generated_text": "",
        "hashtags": [],
        "hook": article_title[:120] if article_title else None,
        "call_to_action": None,
        "target_audience": "MULTI",
        "status": "failed",
        "last_error": error_message,
        "last_error_at": datetime.now(timezone.utc).isoformat(),
    }
    if user_id:
        record["user_id"] = user_id
    db_client.table("processed_content").insert(record).execute()


def notify_provider_failure(
    user_id: Optional[str],
    provider_name: str,
    error_message: str,
) -> None:
    """Notify the user via Telegram when AI generation fails completely."""
    if not user_id:
        return
    try:
        from tasks.telegram_bot import telegram_notify_ai_provider_failure

        telegram_notify_ai_provider_failure(
            user_id=user_id,
            provider_name=provider_name,
            error_message=error_message,
        )
    except Exception as exc:
        logger.debug("AI provider failure notification skipped: %s", exc)


def process_pending_articles(
    limit: int = 10,
    batch_size: int = 5,
    user_id: Optional[str] = None,
    ai_api_key: Optional[str] = None,
    ai_provider: Optional[str] = None,
    ai_model: Optional[str] = None,
    provider_fallback: Optional[str] = None,
) -> int:
    """Process pending articles with batching for efficiency.

    Args:
        limit:           Maximum number of articles to process.
        batch_size:      Number of articles per batch (default 5).
        user_id:         Tenant ID — only process this user's pending articles and
                         tag all generated content rows with their ID.
                         Required for multi-tenant operation.
        ai_api_key:      Explicit provider key for this run.
        ai_provider:     Explicit provider override for this run.
        ai_model:        Explicit model override for this run.
        provider_fallback:
                         Optional backup provider to try after the primary provider
                         fails three times.

    Returns:
        Number of articles processed.
    """
    db_client = config.get_database_client()

    # Fetch pending articles — scoped to tenant if user_id provided
    query = (
        db_client.table("raw_articles")
        .select("id,title,content")
        .eq("status", "pending")
        .limit(limit)
    )
    if user_id:
        query.eq("user_id", user_id)

    response = query.execute()
    rows = response.data or []
    if not rows:
        logger.info("No pending articles to process (user_id=%s)", user_id)
        return 0

    logger.info(
        "Processing %d pending articles in batches of %d (user_id=%s)",
        len(rows), batch_size, user_id
    )

    runtime_profile = _build_runtime_ai_profile(
        user_id=user_id,
        ai_key=ai_api_key,
        provider=ai_provider,
        model=ai_model,
        provider_fallback=provider_fallback,
    )
    ai_client = ProviderTextClient(runtime_profile)
    processed = 0

    # Process in batches
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]

        try:
            # Generate content for batch
            results = generate_batch(batch, client=ai_client)

            # Ensure results is a list
            if not isinstance(results, list):
                results = [results]

            # Save results
            for j, result in enumerate(results):
                if j >= len(batch):
                    break

                # Handle case where result might be a string or unexpected type
                if not isinstance(result, dict):
                    logger.warning("Skipping non-dict result: %s", type(result))
                    continue

                article = batch[j]
                article_id = article["id"]

                try:
                    # Save text/photo post - v2.0 simplified (no Reels)
                    text_data = result.get("text_post") or result
                    if isinstance(text_data, dict) and (
                        text_data.get("hook") or text_data.get("body")
                    ):
                        save_processed_content(
                            article_id, "post", text_data,
                            article_title=article.get("title", ""),
                            user_id=user_id,
                            runtime_profile=runtime_profile,
                        )

                    mark_article_processed(article_id, user_id=user_id)
                    processed += 1
                except Exception as item_exc:
                    logger.error("Failed to save content for article %s: %s", article_id, item_exc)
                    continue

            # Rate limiting pause between batches
            if i + batch_size < len(rows):
                time.sleep(config.REQUEST_SLEEP_SECONDS)

        except AIProviderError as exc:
            logger.error("Batch processing failed with provider error: %s", exc.user_message)
            for article in batch:
                article_id = article["id"]
                article_title = article.get("title", "")
                try:
                    save_failed_content(
                        article_id=article_id,
                        article_title=article_title,
                        error_message=exc.user_message,
                        user_id=user_id,
                    )
                    mark_article_failed(article_id, exc.user_message, user_id=user_id)
                except Exception as item_exc:
                    logger.error("Failed to persist generation failure for article %s: %s", article_id, item_exc)
            notify_provider_failure(user_id, exc.provider, exc.user_message)
            continue
        except Exception as exc:
            logger.error("Batch processing failed: %s", exc)
            # Continue with next batch
            continue

    logger.info("Processed %d articles total (user_id=%s)", processed, user_id)
    return processed


def generate_for_user(user_config: "UserConfig") -> int:  # type: ignore[name-defined]
    """
    Process pending articles for a single tenant using a UserConfig object.

    This is the preferred entry point for the multi-tenant pipeline runner.
    The resolved provider profile is used explicitly rather than relying on
    ambient globals, satisfying the per-user credential contract.

    Parameters
    ----------
    user_config : UserConfig
        Fully-populated tenant configuration object.

    Returns
    -------
    int
        Number of articles processed.
    """
    return process_pending_articles(
        limit=10,
        batch_size=5,
        user_id=user_config.user_id,
        ai_api_key=user_config.ai_api_key or None,
        ai_provider=user_config.ai_provider,
        ai_model=user_config.ai_model or None,
        provider_fallback=user_config.provider_fallback or None,
    )


if __name__ == "__main__":
    process_pending_articles()

