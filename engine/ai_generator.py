"""Generate viral content using OpenRouter with batching support."""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

import config
from openrouter_client import OpenRouterClient, AllKeysExhaustedError

logger = config.get_logger("ai_generator")


# Batch prompt template - generates content for multiple articles in one call
# Based on: "Écrire des posts courts et engageants sur la tech et le gaming"
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


def get_ai_client_instance() -> GeminiClient:
    """Get configured AI client (Gemini default, OpenRouter fallback)."""
    return get_ai_client()


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


def generate_batch(articles: List[dict], client: Optional[GeminiClient] = None) -> List[Dict]:
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
        client = get_ai_client_instance()

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
        response = client.generate(prompt, max_tokens=2000, temperature=0.7)
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

    except AllKeysExhaustedError:
        logger.error("All API keys exhausted - wait for rate limit reset")
        raise
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse JSON response: %s", exc)
        raise
    except Exception as exc:
        logger.error("Batch generation failed: %s", exc)
        raise


def generate_single(
    article: dict, client: Optional[GeminiClient] = None
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
        client = get_ai_client_instance()

    prompt = SINGLE_PROMPT_TEMPLATE.format(
        title=article.get("title", ""),
        summary=(article.get("content") or "")[:500],
    )

    response = client.generate(prompt, max_tokens=1024, temperature=0.7)
    return parse_json_response(response)


def save_processed_content(
    article_id: str, post_type: str, payload: Dict, article_title: str = ""
) -> None:
    """Save generated content to Supabase and generate social image."""
    db_client = config.get_supabase_client()

    # Generate social media image
    image_path = ""
    arabic_text = ""
    try:
        from image_pipeline import generate_social_post

        ai_client = get_ai_client_instance()
        image_path, arabic_text = generate_social_post(
            article_id=article_id,
            title=article_title or payload.get("hook", ""),
            client=ai_client,
        )
        logger.info("Generated social image: %s", image_path)
    except Exception as e:
        logger.warning("Image generation failed (continuing): %s", e)

    record = {
        "article_id": article_id,
        "post_type": post_type,
        "generated_text": payload.get("body", ""),
        "hashtags": payload.get("hashtags", []),
        "hook": payload.get("hook"),
        "call_to_action": payload.get("cta"),
        "target_audience": "AR",  # v2.0: Target Arabic audience
        "image_path": image_path,
        "arabic_text": arabic_text,
    }

    db_client.table("processed_content").insert(record).execute()
    logger.debug("Saved processed content for article %s", article_id)


def mark_article_processed(article_id: str) -> None:
    """Mark article as processed in database."""
    client = config.get_supabase_client()
    client.table("raw_articles").update({"status": "processed"}).eq("id", article_id).execute()


def process_pending_articles(limit: int = 10, batch_size: int = 5) -> int:
    """
    Process pending articles with batching for efficiency.

    Args:
        limit: Maximum number of articles to process
        batch_size: Number of articles per batch (default 5)

    Returns:
        Number of articles processed
    """
    db_client = config.get_supabase_client()

    # Fetch pending articles
    response = (
        db_client.table("raw_articles")
        .select("id,title,content")
        .eq("status", "pending")
        .limit(limit)
        .execute()
    )

    rows = response.data or []
    if not rows:
        logger.info("No pending articles to process")
        return 0

    logger.info("Processing %d pending articles in batches of %d", len(rows), batch_size)

    ai_client = get_ai_client_instance()
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
                            article_id, "text", text_data, article_title=article.get("title", "")
                        )

                    mark_article_processed(article_id)
                    processed += 1
                except Exception as item_exc:
                    logger.error("Failed to save content for article %s: %s", article_id, item_exc)
                    continue

            # Rate limiting pause between batches
            if i + batch_size < len(rows):
                time.sleep(config.REQUEST_SLEEP_SECONDS)

        except AllKeysExhaustedError:
            logger.error("All API keys exhausted, stopping batch processing")
            break
        except Exception as exc:
            logger.error("Batch processing failed: %s", exc)
            # Continue with next batch
            continue

    logger.info("Processed %d articles total", processed)
    return processed


if __name__ == "__main__":
    process_pending_articles()
