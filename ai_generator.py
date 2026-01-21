"""Generate viral content using OpenRouter with batching support."""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

import config
from openrouter_client import OpenRouterClient, AllKeysExhaustedError

logger = config.get_logger("ai_generator")


# Batch prompt template - generates content for multiple articles in one call
BATCH_PROMPT_TEMPLATE = """Tu es un créateur de contenu viral pour Facebook ciblant une audience tech US/UK/Canada.

OBJECTIF: Transformer ces {count} actualités tech en posts Facebook viraux.

ARTICLES À TRAITER:
{articles_json}

POUR CHAQUE ARTICLE, génère:

1. **POST TEXTE** (150-250 mots):
   - Hook CHOQUANT ou INTRIGANT (1-2 phrases)
   - Corps conversationnel et excitant
   - Utilise des retours à la ligne pour lisibilité
   - 1-2 emojis pertinents (pas excessif)
   - CTA fort: "What do you think? Comment below!"
   - 5-7 hashtags trending

2. **SCRIPT REEL** (30-45 secondes):
   - Format: [CUE VISUEL] + Narration
   - Commence par "DID YOU KNOW...?" ou "THIS JUST CHANGED EVERYTHING:"
   - Phrases courtes et percutantes

IMPORTANT: Réponds UNIQUEMENT en JSON valide, sans texte avant ou après:

[
  {{
    "article_index": 0,
    "text_post": {{
      "hook": "...",
      "body": "...",
      "cta": "What do you think? Comment below!",
      "hashtags": ["#AI", "#Tech", "#Innovation", ...]
    }},
    "reel_script": "[VISUAL: ...] Narration..."
  }},
  ...
]
"""

# Single article prompt (fallback)
SINGLE_PROMPT_TEMPLATE = """Tu es un créateur de contenu viral pour Facebook ciblant une audience tech US/UK.

Transforme cette actualité tech en post Facebook viral:

TITRE: {title}
RÉSUMÉ: {summary}
TYPE DE POST: {post_type}

EXIGENCES:
- Hook CHOQUANT ou INTRIGANT (1-2 phrases)
- Ton conversationnel et excitant
- Retours à la ligne pour lisibilité
- 1-2 emojis pertinents
- CTA: "What do you think? Comment below!"
- 5-7 hashtags trending
- Longueur: 150-250 mots
- Style HUMAIN, pas robotique

Si post_type = reel:
- Script vidéo 30-45 secondes
- Format: [CUE VISUEL] + Narration
- Commence par "DID YOU KNOW...?"

Réponds en JSON:
{{
  "hook": "...",
  "body": "...",
  "cta": "...",
  "hashtags": ["#AI", "#Tech", ...],
  "reel_script": "..." (si applicable)
}}
"""


def get_openrouter_client() -> OpenRouterClient:
    """Get configured OpenRouter client."""
    return OpenRouterClient()


def fix_json_string(text: str) -> str:
    """Attempt to fix common JSON issues from LLM output."""
    import re
    
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    
    # Fix unescaped newlines in strings
    # This is a simplified fix - handles common cases
    lines = text.split('\n')
    fixed_lines = []
    in_string = False
    for line in lines:
        # Count unescaped quotes to track if we're in a string
        quote_count = len(re.findall(r'(?<!\\)"', line))
        if in_string:
            # If we're continuing a string from previous line, escape this line
            fixed_lines.append(line.replace('\n', '\\n'))
        else:
            fixed_lines.append(line)
        # Toggle in_string if odd number of quotes
        if quote_count % 2 == 1:
            in_string = not in_string
    
    return '\n'.join(fixed_lines)


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
            json_text = stripped[start_array:end + 1]
    elif start_obj != -1:
        # It's an object
        end = stripped.rfind("}")
        if end != -1:
            json_text = stripped[start_obj:end + 1]
    
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
            objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_text)
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


def generate_batch(articles: List[dict], client: Optional[OpenRouterClient] = None) -> List[Dict]:
    """
    Generate content for multiple articles in a single API call.
    
    Args:
        articles: List of article dicts with 'title' and 'content' keys
        client: Optional OpenRouter client (creates new one if not provided)
        
    Returns:
        List of generated content dicts
    """
    if not articles:
        return []
    
    if client is None:
        client = get_openrouter_client()
    
    # Format articles for prompt
    articles_for_prompt = []
    for i, article in enumerate(articles):
        articles_for_prompt.append({
            "index": i,
            "title": article.get("title", ""),
            "summary": (article.get("content") or "")[:500],  # Limit summary length
        })
    
    prompt = BATCH_PROMPT_TEMPLATE.format(
        count=len(articles),
        articles_json=json.dumps(articles_for_prompt, ensure_ascii=False, indent=2),
    )
    
    try:
        response = client.call(prompt, max_tokens=4096, temperature=0.7)
        results = parse_json_response(response)
        
        if not isinstance(results, list):
            results = [results]
        
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


def generate_single(article: dict, post_type: str, client: Optional[OpenRouterClient] = None) -> Dict:
    """
    Generate content for a single article (fallback method).
    
    Args:
        article: Article dict with 'title' and 'content'
        post_type: 'text' or 'reel'
        client: Optional OpenRouter client
        
    Returns:
        Generated content dict
    """
    if client is None:
        client = get_openrouter_client()
    
    prompt = SINGLE_PROMPT_TEMPLATE.format(
        title=article.get("title", ""),
        summary=(article.get("content") or "")[:500],
        post_type=post_type,
    )
    
    response = client.call(prompt, max_tokens=1024, temperature=0.7)
    return parse_json_response(response)


def save_processed_content(article_id: str, post_type: str, payload: Dict, article_title: str = "") -> None:
    """Save generated content to Supabase and generate social image."""
    client = config.get_supabase_client()
    
    # Generate social media image
    image_path = ""
    arabic_text = ""
    try:
        from image_pipeline import generate_social_post
        from openrouter_client import OpenRouterClient
        
        or_client = OpenRouterClient()
        image_path, arabic_text = generate_social_post(
            article_id=article_id,
            title=article_title or payload.get("hook", ""),
            client=or_client,
        )
        logger.info("Generated social image: %s", image_path)
    except Exception as e:
        logger.warning("Image generation failed (continuing): %s", e)
    
    record = {
        "article_id": article_id,
        "post_type": post_type,
        "generated_text": payload.get("body", ""),
        "script_for_reel": payload.get("reel_script"),
        "hashtags": payload.get("hashtags", []),
        "hook": payload.get("hook"),
        "call_to_action": payload.get("cta"),
        "target_audience": "US",
        "image_path": image_path,
        "arabic_text": arabic_text,
    }
    
    client.table("processed_content").insert(record).execute()
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
    
    openrouter = get_openrouter_client()
    processed = 0
    
    # Process in batches
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        
        try:
            # Generate content for batch
            results = generate_batch(batch, client=openrouter)
            
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
                    # Save text post - handle different response structures
                    text_data = result.get("text_post") or result
                    if isinstance(text_data, dict) and (text_data.get("hook") or text_data.get("body")):
                        save_processed_content(article_id, "text", text_data, article_title=article.get("title", ""))
                    
                    # Save reel script
                    reel_script = result.get("reel_script") or text_data.get("reel_script")
                    if reel_script:
                        reel_data = {
                            "hook": text_data.get("hook", "") if isinstance(text_data, dict) else "",
                            "body": "",
                            "cta": "",
                            "hashtags": text_data.get("hashtags", []) if isinstance(text_data, dict) else [],
                            "reel_script": reel_script,
                        }
                        save_processed_content(article_id, "reel", reel_data, article_title=article.get("title", ""))
                    
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
