"""
Quality Gate - Content validation for Content Factory v3.0.

Features:
- Validate hook quality (not robotic, not generic)
- Validate image_title length (3-6 words)
- Validate hashtag count (8-12)
- Anti-repeat check for similar hooks
- Auto-regenerate on failure (1 retry)
"""

from __future__ import annotations

import os
import re
from typing import Dict, Tuple, List, Optional
from datetime import datetime, timedelta, timezone

import config

logger = config.get_logger("quality_gate")

# Configurable quality threshold (0-100)
MIN_QUALITY_SCORE = int(os.environ.get("MIN_QUALITY_SCORE", "40"))

# Generic hooks that should be rejected
GENERIC_HOOKS = {
    "AR": ["خبر عاجل", "هام جداً", "لن تصدق", "صادم", "خبر عاجل في عالم التقنية"],
    "FR": ["Breaking news", "Actualité", "Incroyable", "À ne pas rater", "C'est officiel"],
    "EN": ["Breaking news", "You won't believe", "This is huge", "Amazing news", "Just in"]
}

# Minimum hook lengths by language
MIN_HOOK_LENGTH = {
    "AR": 15,
    "FR": 20,
    "EN": 20
}


def validate_content(content: dict, lang: str) -> Tuple[bool, str]:
    """
    Validate generated content against quality standards.
    
    Args:
        content: Dict with caption, image_title, keywords, hashtags
        lang: Language code (AR/FR/EN)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    errors = []
    
    # Extract fields
    caption = content.get("caption", "")
    image_title = content.get("image_title", "")
    hashtags = content.get("hashtags", [])
    keywords = content.get("keywords", [])
    
    # === Check 1: Caption exists and has hook ===
    if not caption or len(caption) < 20:
        errors.append("Caption trop court ou vide")
    
    # === Check 2: Hook quality ===
    hook = extract_hook(caption, lang)
    hook_valid, hook_error = validate_hook(hook, lang)
    if not hook_valid:
        errors.append(hook_error)
    
    # === Check 3: image_title length (3-6 words) ===
    title_valid, title_error = validate_image_title(image_title)
    if not title_valid:
        errors.append(title_error)
    
    # === Check 4: Hashtag count (8-12) ===
    hashtag_valid, hashtag_error = validate_hashtags(hashtags)
    if not hashtag_valid:
        errors.append(hashtag_error)
    
    # === Check 5: Keywords exist ===
    if len(keywords) < 2:
        errors.append("Pas assez de keywords (min 2)")
    
    # Return result
    if errors:
        error_msg = "; ".join(errors)
        logger.warning("❌ Quality Gate FAILED: %s", error_msg)
        return False, error_msg
    
    logger.info("✅ Quality Gate PASSED")
    return True, "OK"


def extract_hook(caption: str, lang: str) -> str:
    """Extract the hook (first line) from caption."""
    if not caption:
        return ""
    
    # Split by newlines and get first non-empty line
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    return lines[0] if lines else ""


def validate_hook(hook: str, lang: str) -> Tuple[bool, str]:
    """
    Validate hook quality.
    
    Checks:
    - Minimum length
    - Not in generic hooks list
    - Contains emoji (engagement indicator)
    """
    if not hook:
        return False, "Hook vide"
    
    # Check minimum length
    min_len = MIN_HOOK_LENGTH.get(lang, 20)
    if len(hook) < min_len:
        return False, f"Hook trop court ({len(hook)} < {min_len} caractères)"
    
    # Check not generic
    generic_list = GENERIC_HOOKS.get(lang, [])
    hook_lower = hook.lower()
    for generic in generic_list:
        if generic.lower() in hook_lower:
            return False, f"Hook trop générique (contient '{generic}')"
    
    # Check for emoji (good engagement signal)
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\U00002702-\U000027B0"
        u"\U0001F900-\U0001F9FF"
        "]+", flags=re.UNICODE)
    
    if not emoji_pattern.search(hook):
        return False, "Hook sans emoji (recommandé pour engagement)"
    
    return True, "OK"


def validate_image_title(image_title: str) -> Tuple[bool, str]:
    """
    Validate image_title is 3-6 words.
    """
    if not image_title:
        return False, "image_title vide"
    
    # Count words (simple split)
    words = image_title.split()
    word_count = len(words)
    
    if word_count < 3:
        return False, f"image_title trop court ({word_count} mots, min 3)"
    
    if word_count > 6:
        return False, f"image_title trop long ({word_count} mots, max 6)"
    
    return True, "OK"


def validate_hashtags(hashtags: list) -> Tuple[bool, str]:
    """
    Validate hashtag count is 8-12.
    """
    if not hashtags:
        return False, "Aucun hashtag"
    
    count = len(hashtags)
    
    if count < 8:
        return False, f"Pas assez de hashtags ({count}, min 8)"
    
    if count > 12:
        return False, f"Trop de hashtags ({count}, max 12)"
    
    # Check hashtags start with #
    for tag in hashtags:
        if not tag.startswith("#"):
            return False, f"Hashtag invalide: '{tag}' (doit commencer par #)"
    
    return True, "OK"


def check_anti_repeat(new_hook: str, recent_hooks: List[str], threshold: float = 0.7) -> Tuple[bool, str]:
    """
    Check if the new hook is too similar to recent hooks.
    
    Args:
        new_hook: The new hook to check
        recent_hooks: List of recent hooks to compare against
        threshold: Similarity threshold (0.0-1.0)
    
    Returns:
        Tuple of (is_unique, message)
    """
    if not recent_hooks:
        return True, "OK"
    
    try:
        from duplicate_detector import simple_text_similarity
        
        for old_hook in recent_hooks:
            similarity = simple_text_similarity(new_hook, old_hook)
            if similarity > threshold:
                return False, f"Hook trop similaire à un récent ({similarity:.0%})"
        
        return True, "OK"
        
    except ImportError:
        logger.warning("duplicate_detector not available, skipping anti-repeat check")
        return True, "OK (skip)"


def get_recent_hooks(hours: int = 48, limit: int = 20) -> List[str]:
    """
    Get recent hooks from database for anti-repeat check.
    """
    try:
        client = config.get_supabase_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        result = client.table("processed_content").select(
            "hook"
        ).gte("generated_at", cutoff).order(
            "generated_at", desc=True
        ).limit(limit).execute()
        
        return [r["hook"] for r in result.data if r.get("hook")]
        
    except Exception as e:
        logger.warning("Could not fetch recent hooks: %s", e)
        return []


def score_content(content: dict, lang: str) -> Dict:
    """
    Score generated content on a 0-100 scale with per-dimension breakdown.

    Dimensions:
        hook (30 pts)   – length, emoji, originality
        body (25 pts)   – caption length and paragraph structure
        emoji (15 pts)  – presence and density
        hashtags (15 pts) – count within 5-12 range
        uniqueness (15 pts) – anti-repeat vs recent hooks

    Returns:
        Dict with 'total', per-dimension scores, and 'grade' (A-F).
    """
    scores: Dict[str, float] = {}
    caption = content.get("caption", "")
    hook = extract_hook(caption, lang)
    hashtags = content.get("hashtags", [])

    # ── Hook (0-30) ───────────────────────────────────
    hook_score = 0.0
    if hook:
        min_len = MIN_HOOK_LENGTH.get(lang, 20)
        # Length score (up to 15)
        hook_score += min(len(hook) / (min_len * 2) * 15, 15)
        # Emoji bonus (up to 5)
        emoji_pat = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F900-\U0001F9FF"
            u"\U00002702-\U000027B0"
            "]+", flags=re.UNICODE)
        if emoji_pat.search(hook):
            hook_score += 5
        # Originality (up to 10): penalize generic hooks
        generic_list = GENERIC_HOOKS.get(lang, [])
        is_generic = any(g.lower() in hook.lower() for g in generic_list)
        hook_score += 0 if is_generic else 10
    scores["hook"] = round(min(hook_score, 30), 1)

    # ── Body (0-25) ───────────────────────────────────
    body_score = 0.0
    if caption:
        # Length score (up to 15): ideal 100-300 chars
        clen = len(caption)
        if clen >= 100:
            body_score += min(clen / 300 * 15, 15)
        # Paragraph structure (up to 10): reward line breaks
        paragraphs = [p for p in caption.split("\n") if p.strip()]
        body_score += min(len(paragraphs) * 2.5, 10)
    scores["body"] = round(min(body_score, 25), 1)

    # ── Emoji density (0-15) ──────────────────────────
    emoji_all = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F900-\U0001F9FF"
        u"\U00002702-\U000027B0"
        "]+", flags=re.UNICODE)
    emoji_count = len(emoji_all.findall(caption))
    # Ideal: 2-5 emojis
    if emoji_count == 0:
        scores["emoji"] = 0.0
    elif emoji_count <= 5:
        scores["emoji"] = round(emoji_count / 5 * 15, 1)
    else:
        scores["emoji"] = round(max(15 - (emoji_count - 5) * 2, 5), 1)

    # ── Hashtags (0-15) ───────────────────────────────
    tag_count = len(hashtags)
    if tag_count == 0:
        scores["hashtags"] = 0.0
    elif 5 <= tag_count <= 12:
        scores["hashtags"] = 15.0
    elif tag_count < 5:
        scores["hashtags"] = round(tag_count / 5 * 15, 1)
    else:
        scores["hashtags"] = round(max(15 - (tag_count - 12) * 3, 0), 1)

    # ── Uniqueness (0-15) ─────────────────────────────
    try:
        recent = get_recent_hooks(hours=48, limit=20)
        if recent and hook:
            unique, _ = check_anti_repeat(hook, recent, threshold=0.7)
            scores["uniqueness"] = 15.0 if unique else 3.0
        else:
            scores["uniqueness"] = 15.0  # No history → assume unique
    except Exception:
        scores["uniqueness"] = 15.0  # Fail-open

    total = round(sum(scores.values()), 1)
    # Grade
    if total >= 80:
        grade = "A"
    elif total >= 65:
        grade = "B"
    elif total >= 50:
        grade = "C"
    elif total >= 35:
        grade = "D"
    else:
        grade = "F"

    return {"total": total, "grade": grade, **scores}


def full_quality_check(content: dict, lang: str) -> Tuple[bool, str]:
    """
    Complete quality check including anti-repeat and quality scoring.

    Args:
        content: Generated content dict
        lang: Language code

    Returns:
        Tuple of (passed, error_message)
    """
    # Basic validation
    valid, error = validate_content(content, lang)
    if not valid:
        return False, error

    # Anti-repeat check
    hook = extract_hook(content.get("caption", ""), lang)
    recent_hooks = get_recent_hooks()
    unique, unique_error = check_anti_repeat(hook, recent_hooks)
    if not unique:
        return False, unique_error

    # Quality scoring
    result = score_content(content, lang)
    if result["total"] < MIN_QUALITY_SCORE:
        msg = "Quality score too low: %d/100 (min %d) — %s" % (
            result["total"], MIN_QUALITY_SCORE, result["grade"]
        )
        logger.warning("⚠️ %s", msg)
        return False, msg

    logger.info("✅ Quality Gate PASSED — score %d/100 (%s)", result["total"], result["grade"])
    return True, "OK"


if __name__ == "__main__":
    # Test validation
    test_content = {
        "caption": "🔥 OpenAI vient de changer les règles du jeu!\n\nVoici ce que ça signifie pour vous...\n\n🔗 Lien : example.com",
        "image_title": "OpenAI Game Changer",
        "keywords": ["openai", "ai", "tech"],
        "hashtags": ["#OpenAI", "#AI", "#Tech", "#Innovation", "#Future", "#ChatGPT", "#GPT", "#Productivity"]
    }
    
    valid, msg = validate_content(test_content, "FR")
    print(f"Validation result: {valid} - {msg}")
