"""
Unified Content Creator - Pipeline Intelligent Unifié v2

Ce module gère TOUT le processus de manière cohérente:
1. Trouve les tendances (Google Trends + NewsData + HackerNews)
2. Crée l'article complet avec description image
3. Trouve l'image qui CORRESPOND (Pexels avec mots-clés précis de l'AI)
4. Compose le canvas final
5. Sauvegarde en base de données (traçabilité)
6. Publie sur Facebook

Usage:
    from unified_content_creator import create_and_publish
    result = create_and_publish()
"""

from __future__ import annotations

import json
import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

import config
from gemini_client import get_ai_client, GeminiClient

# v3.0: Import new modules
from language_picker import pick_language, get_cta, get_glossary_string, KEEP_ENGLISH_GLOSSARY
from template_manager import pick_text_template, pick_image_template, get_template_config
from quality_gate import validate_content, full_quality_check, extract_hook

logger = config.get_logger("unified_creator")

# Paths
BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "generated_images"
DOWNLOADED_DIR = BASE_DIR / "downloaded_images"
IMAGE_CONFIG_PATH = BASE_DIR / "image_config.json"

# Create directories
IMAGES_DIR.mkdir(exist_ok=True)
DOWNLOADED_DIR.mkdir(exist_ok=True)

# API Keys
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")


# ============================================
# v3.0: MULTI-LANGUAGE PROMPTS
# ============================================

def get_prompt_for_language(lang: str, template: dict, topic: dict) -> str:
    """
    Generate the LLM prompt for the given language and template.
    
    Args:
        lang: Language code (AR/FR/EN)
        template: Text template with structure
        topic: Topic dict with title/content
    
    Returns:
        Formatted prompt string
    """
    title = topic.get("title", "")
    content = topic.get("content", "")[:500]
    structure = template.get("structure", "")
    example = template.get("example", "")
    
    if lang == "AR":
        return f"""أنت خبير محتوى عربي فيروسي. اتبع هذا النمط بدقة:

📋 النمط المرجعي:
{structure}

📝 مثال:
{example}

🎯 الموضوع:
العنوان: {title}
المحتوى: {content}

📝 أنشئ بصيغة JSON فقط:
{{
  "caption": "النص الكامل (hook + body + CTA) - اتبع النمط أعلاه",
  "image_title": "3-6 كلمات بالإنجليزية للصورة",
  "keywords": ["كلمة1", "كلمة2", "كلمة3"],
  "hashtags": ["#هاشتاق1", "#هاشتاق2", "..."]
}}

⚠️ قواعد صارمة:
- المصطلحات التقنية بالإنجليزية: {', '.join(KEEP_ENGLISH_GLOSSARY[:15])}
- CTA = 🔗 الرابط: [LINK] (بدون طلب تعليقات)
- 8-12 هاشتاق مزيج عربي/إنجليزي
- image_title بالإنجليزية فقط، 3-6 كلمات
- JSON فقط بدون أي نص إضافي!"""

    elif lang == "FR":
        return f"""Tu es expert en contenu viral francophone. Suis ce pattern exactement:

📋 Pattern de référence:
{structure}

📝 Exemple:
{example}

🎯 Sujet:
Titre: {title}
Contenu: {content}

📝 Génère en JSON strict:
{{
  "caption": "Texte complet (hook + body + CTA) - suis le pattern ci-dessus",
  "image_title": "3-6 mots en anglais pour l'image",
  "keywords": ["mot1", "mot2", "mot3"],
  "hashtags": ["#hashtag1", "#hashtag2", "..."]
}}

⚠️ Règles strictes:
- CTA = 🔗 Lien : [LINK] (pas de demande de commentaires)
- 8-12 hashtags français/anglais
- image_title en anglais uniquement, 3-6 mots
- JSON uniquement, aucun texte autour!"""

    else:  # EN
        return f"""You are a viral content expert. Follow this pattern exactly:

📋 Reference pattern:
{structure}

📝 Example:
{example}

🎯 Topic:
Title: {title}
Content: {content}

📝 Generate JSON only:
{{
  "caption": "Full text (hook + body + CTA) - follow the pattern above",
  "image_title": "3-6 words for image",
  "keywords": ["word1", "word2", "word3"],
  "hashtags": ["#hashtag1", "#hashtag2", "..."]
}}

⚠️ Strict rules:
- CTA = 🔗 Link: [LINK] (no comment requests)
- 8-12 hashtags
- image_title in English, 3-6 words
- JSON only, no surrounding text!"""


# Legacy prompt (kept for fallback compatibility)
UNIFIED_PROMPT = """أنت خبير في إنشاء محتوى فيروسي للشبكات الاجتماعية العربية.

🎯 المهمة: إنشاء منشور كامل عن موضوع تقني/ألعاب رائج.

📰 الموضوع:
العنوان: {title}
المحتوى: {content}

📝 أنشئ المحتوى التالي بصيغة JSON:

{{
  "caption": "النص الكامل للمنشور",
  "image_title": "3-6 كلمات بالإنجليزية",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "hashtags": ["#تقنية", "#ذكاء_اصطناعي", "..."]
}}

⚠️ مهم جداً:
- أسماء الماركات بالإنجليزية (OpenAI, Tesla, ChatGPT)
- CTA = 🔗 الرابط: [LINK]
- 8-12 هاشتاق
- أجب بـ JSON فقط!"""


# ============================================
# ÉTAPE 1: TROUVER LES TENDANCES
# ============================================

def get_google_trends() -> List[Dict]:
    """
    Get trending topics from Google Trends (free).
    Uses pytrends library.
    """
    trends = []
    try:
        from pytrends.request import TrendReq
        
        pytrends = TrendReq(hl='en-US', tz=360)
        
        # Get trending searches
        trending = pytrends.trending_searches(pn='united_states')
        
        for topic in trending[0].head(10).tolist():
            # Filter for tech/gaming topics
            topic_lower = topic.lower()
            if any(kw in topic_lower for kw in ['ai', 'gpt', 'game', 'tech', 'nvidia', 'apple', 'google', 'microsoft', 'meta', 'openai', 'chatgpt']):
                trends.append({
                    "title": topic,
                    "content": f"Trending topic: {topic}",
                    "source": "google_trends"
                })
        
        logger.info(f"📈 Google Trends: {len(trends)} sujets tech trouvés")
        
    except ImportError:
        logger.warning("pytrends not installed. Install with: pip install pytrends")
    except Exception as e:
        logger.warning(f"Google Trends error: {e}")
    
    return trends


def get_newsdata_topics() -> List[Dict]:
    """Get trending topics from NewsData API."""
    topics = []
    
    if not config.NEWSDATA_API_KEY:
        return topics
    
    try:
        url = "https://newsdata.io/api/1/latest"
        params = {
            "apikey": config.NEWSDATA_API_KEY,
            "category": "technology",
            "language": "en",
            "q": "AI OR gaming OR ChatGPT OR OpenAI OR tech"
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        for article in data.get("results", [])[:5]:
            topics.append({
                "title": article.get("title", ""),
                "content": article.get("description") or article.get("content", ""),
                "source": article.get("source_id", "newsdata"),
                "url": article.get("link", ""),
                "image_url": article.get("image_url")
            })
        
        logger.info(f"📰 NewsData: {len(topics)} articles trouvés")
        
    except Exception as e:
        logger.warning(f"NewsData error: {e}")
    
    return topics


def get_hackernews_topics() -> List[Dict]:
    """Get trending topics from Hacker News."""
    topics = []
    
    try:
        base_url = "https://hacker-news.firebaseio.com/v0"
        resp = requests.get(f"{base_url}/topstories.json", timeout=10)
        ids = resp.json()[:10]
        
        for story_id in ids:
            story_resp = requests.get(f"{base_url}/item/{story_id}.json", timeout=10)
            story = story_resp.json()
            if story and story.get("type") == "story":
                title = story.get("title", "")
                # Filter for tech/AI topics
                if any(kw in title.lower() for kw in ["ai", "gpt", "openai", "tech", "game", "nvidia", "llm", "chatgpt"]):
                    topics.append({
                        "title": title,
                        "content": story.get("text", title),
                        "source": "hackernews",
                        "url": story.get("url", "")
                    })
        
        logger.info(f"🔥 HackerNews: {len(topics)} articles tech trouvés")
        
    except Exception as e:
        logger.warning(f"HackerNews error: {e}")
    
    return topics


def find_trending_topic() -> Dict:
    """
    Trouve un sujet tendance en combinant plusieurs sources.
    
    Priority: Google Trends > NewsData > HackerNews
    
    Returns:
        Dict avec title, content, source
    """
    logger.info("🔍 Recherche des tendances...")
    
    all_topics = []
    
    # 1. Google Trends (free, real-time)
    all_topics.extend(get_google_trends())
    
    # 2. NewsData API
    all_topics.extend(get_newsdata_topics())
    
    # 3. HackerNews (always free)
    all_topics.extend(get_hackernews_topics())
    
    if all_topics:
        # Pick the first one (priority order)
        topic = all_topics[0]
        logger.info(f"✅ Tendance choisie: {topic['title'][:50]}... (source: {topic.get('source')})")
        return topic
    
    # Ultimate fallback
    logger.warning("⚠️ Aucune tendance trouvée, utilisation du fallback")
    return {
        "title": "OpenAI Announces New AI Breakthrough",
        "content": "OpenAI has announced a major breakthrough in artificial intelligence capabilities.",
        "source": "fallback"
    }


def find_all_trending_topics(limit: int = 10) -> List[Dict]:
    """Get all trending topics for selection."""
    all_topics = []
    all_topics.extend(get_google_trends())
    all_topics.extend(get_newsdata_topics())
    all_topics.extend(get_hackernews_topics())
    return all_topics[:limit]


# ============================================
# ÉTAPE 2: GÉNÉRER LE CONTENU COMPLET
# ============================================

def generate_complete_content(
    topic: Dict, 
    client: Optional[GeminiClient] = None,
    lang: Optional[str] = None,
    max_retries: int = 1
) -> Dict:
    """
    v3.0: Génère contenu avec multi-langue, templates et quality gate.
    
    Args:
        topic: Dict avec title/content du sujet
        client: Client AI (optionnel)
        lang: Force une langue (sinon tirage pondéré)
        max_retries: Nombre de regenerate si quality gate fail
    
    Returns:
        Dict avec caption, image_title, keywords, hashtags, + metadata
    """
    # v3.0: Pick language if not specified (weighted random)
    if lang is None:
        lang = pick_language()
    
    logger.info(f"📝 Génération contenu v3.0 [{lang}]...")
    
    # v3.0: Pick text template for this language
    text_template = pick_text_template(lang)
    logger.info(f"📋 Template: {text_template['name']}")
    
    if client is None:
        client = get_ai_client()
    
    # v3.0: Build prompt using template
    prompt = get_prompt_for_language(lang, text_template, topic)
    
    for attempt in range(max_retries + 1):
        try:
            response = client.generate(prompt, max_tokens=1500, temperature=0.7)
            
            # Parse JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            content = json.loads(json_match.group())
            
            # v3.0: Quality Gate validation
            is_valid, error_msg = validate_content(content, lang)
            
            if is_valid:
                # Add metadata for database
                content["_metadata"] = {
                    "language": lang,
                    "text_template_id": text_template["id"],
                    "text_template_name": text_template["name"]
                }
                logger.info(f"✅ Contenu v3.0 généré [{lang}] - Quality Gate PASSED")
                return content
            else:
                logger.warning(f"⚠️ Quality Gate FAILED (attempt {attempt+1}): {error_msg}")
                if attempt < max_retries:
                    logger.info("🔄 Regenerating...")
                    continue
                else:
                    logger.error("❌ Max retries reached, using fallback")
                    return _get_fallback_content_v3(topic, lang)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            if attempt == max_retries:
                return _get_fallback_content_v3(topic, lang)
        except Exception as e:
            logger.error(f"Content generation error: {e}")
            if attempt == max_retries:
                return _get_fallback_content_v3(topic, lang)
    
    return _get_fallback_content_v3(topic, lang)


def _get_fallback_content_v3(topic: Dict, lang: str = "AR") -> Dict:
    """v3.0: Fallback content with proper structure."""
    title = topic.get("title", "AI Technology")
    
    # CTA by language (no comment requests)
    cta_map = {
        "AR": "🔗 الرابط: [LINK]",
        "FR": "🔗 Lien : [LINK]",
        "EN": "🔗 Link: [LINK]"
    }
    cta = cta_map.get(lang, cta_map["EN"])
    
    # Fallback captions by language
    if lang == "AR":
        caption = f"🔥 {title}\n\nموضوع مهم يستحق المتابعة!\n\n{cta}"
        hashtags = ["#تقنية", "#AI", "#ذكاء_اصطناعي", "#Tech", "#Innovation", "#Future", "#Digital", "#Trending"]
    elif lang == "FR":
        caption = f"🔥 {title}\n\nUn sujet à suivre de près!\n\n{cta}"
        hashtags = ["#Tech", "#IA", "#Innovation", "#Actualité", "#Digital", "#Future", "#Tendance", "#Technologie"]
    else:
        caption = f"🔥 {title}\n\nA topic worth following!\n\n{cta}"
        hashtags = ["#Tech", "#AI", "#Innovation", "#Trending", "#Digital", "#Future", "#News", "#Technology"]
    
    return {
        "caption": caption,
        "image_title": f"{title[:30]} Tech",
        "keywords": ["technology", "innovation", "digital"],
        "hashtags": hashtags,
        "_metadata": {
            "language": lang,
            "text_template_id": "fallback",
            "text_template_name": "Fallback"
        }
    }


# Legacy fallback (kept for compatibility)
def _get_fallback_content(topic: Dict) -> Dict:
    """Return fallback content structure (legacy)."""
    return _get_fallback_content_v3(topic, "AR")


# ============================================
# ÉTAPE 3: TROUVER L'IMAGE (Pexels avec mots-clés AI)
# ============================================

def find_matching_image(image_info: Dict, article_title: str = "") -> Optional[str]:
    """
    Trouve une image sur Pexels avec les mots-clés PRÉCIS de l'AI.
    """
    logger.info("🎨 Recherche d'image avec mots-clés AI...")
    
    keywords = image_info.get("keywords_en", ["technology"])
    description = image_info.get("description_en", "technology")
    
    # Build search query from AI keywords
    query = " ".join(keywords[:3])
    logger.info(f"🔍 Recherche: '{query}'")
    
    # Try Pexels first
    if PEXELS_API_KEY:
        image_path = search_pexels(query)
        if image_path:
            return image_path
        
        # Try with first keyword only
        if len(keywords) > 1:
            image_path = search_pexels(keywords[0])
            if image_path:
                return image_path
    
    # Fallback to Unsplash
    for kw in keywords:
        image_path = search_unsplash(kw)
        if image_path:
            return image_path
    
    # Ultimate fallback
    return search_unsplash("technology")


def search_pexels(query: str) -> Optional[str]:
    """Search Pexels for an image."""
    if not PEXELS_API_KEY:
        return None
    
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 5, "orientation": "square"}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        photos = data.get("photos", [])
        if photos:
            photo = photos[0]
            image_url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
            
            if image_url:
                img_resp = requests.get(image_url, timeout=15)
                img_resp.raise_for_status()
                
                output_path = DOWNLOADED_DIR / f"pexels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                with open(output_path, 'wb') as f:
                    f.write(img_resp.content)
                
                logger.info(f"✅ Image Pexels: {output_path}")
                return str(output_path)
                
    except Exception as e:
        logger.warning(f"Pexels error: {e}")
    
    return None


def search_unsplash(query: str) -> Optional[str]:
    """Search Unsplash for an image (free, no API key needed)."""
    try:
        url = f"https://source.unsplash.com/1080x1080/?{query}"
        resp = requests.get(url, timeout=15, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 1000:
            output_path = DOWNLOADED_DIR / f"unsplash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            with open(output_path, 'wb') as f:
                f.write(resp.content)
            logger.info(f"✅ Image Unsplash: {output_path}")
            return str(output_path)
    except Exception as e:
        logger.warning(f"Unsplash error: {e}")
    
    return None


# ============================================
# ÉTAPE 4: COMPOSER LE CANVAS
# ============================================

def compose_canvas(image_path: str, hook_text: str) -> str:
    """Compose le canvas final avec l'image et le titre arabe."""
    logger.info("🖼️ Composition du canvas...")
    
    from image_generator import generate_post_image, load_config
    
    img_config = load_config()
    output_path = str(IMAGES_DIR / f"post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    
    result = generate_post_image(
        article_image_path=image_path,
        text=hook_text,
        output_path=output_path,
        config_overrides=img_config
    )
    
    logger.info(f"✅ Canvas créé: {result}")
    return result


# ============================================
# ÉTAPE 5: BASE DE DONNÉES (Traçabilité)
# ============================================

def save_to_database(topic: Dict, content: Dict, image_path: str, canvas_path: str) -> Optional[str]:
    """
    Sauvegarde le contenu dans Supabase pour traçabilité.
    
    v3.0: Supports new content structure with caption, image_title, metadata.
    v2.1: Includes state machine (APPROVAL_MODE) and content_hash for idempotence.
    
    Sauvegarde dans:
    - raw_articles: l'article source
    - processed_content: le contenu généré
    
    Returns:
        content_id
    """
    logger.info("💾 Sauvegarde en base de données...")
    
    try:
        client = config.get_supabase_client()
        
        # 1. Sauvegarder l'article source
        article_data = {
            "source_name": topic.get("source", "unified_creator"),
            "title": topic.get("title", ""),
            "url": topic.get("url", f"unified_{datetime.now().isoformat()}"),
            "content": topic.get("content", ""),
            "status": "processed",
            "virality_score": 10
        }
        
        article_result = client.table("raw_articles").insert(article_data).execute()
        article_id = article_result.data[0]["id"] if article_result.data else None
        
        # 2. Sauvegarder le contenu généré
        # v3.0: Handle both old (article.hook/body/cta) and new (caption) structures
        if "caption" in content:
            # v3.0 format
            full_text = content.get("caption", "")
            hook = extract_hook(full_text, content.get("_metadata", {}).get("language", "AR"))
            hashtags = content.get("hashtags", [])
            image_title = content.get("image_title", "")
            metadata = content.get("_metadata", {})
            lang = metadata.get("language", "AR")
            text_template_id = metadata.get("text_template_id", "")
        else:
            # Legacy v2.x format
            article_content = content.get("article", {})
            full_text = f"{article_content.get('hook', '')}\n\n{article_content.get('body', '')}\n\n{article_content.get('cta', '')}"
            hook = article_content.get("hook", "")
            hashtags = article_content.get("hashtags", [])
            image_title = ""
            lang = "AR"
            text_template_id = ""
        
        # v2.1: Generate content_hash for idempotence
        content_hash = hashlib.sha256(full_text.encode()).hexdigest()[:16]
        
        # v2.1: Determine initial status based on APPROVAL_MODE
        if config.APPROVAL_MODE:
            initial_status = "waiting_approval"
            logger.info("📋 Content set to WAITING_APPROVAL (approval mode enabled)")
        else:
            initial_status = "scheduled"
            logger.info("📅 Content set to SCHEDULED (auto-publish mode)")
        
        content_data = {
            "article_id": article_id,
            "post_type": "text",
            "generated_text": full_text,
            "hook": hook,
            "call_to_action": get_cta(lang),  # v3.0: Use CTA from language_picker
            "hashtags": hashtags,
            "target_audience": lang,  # v3.0: Use actual language
            "image_path": canvas_path,  # Use canvas path (the final composed image)
            "arabic_text": image_title if image_title else hook,  # v3.0: Use image_title for display
            # v2.1: State machine and idempotence
            "status": initial_status,
            "content_hash": content_hash,
            "retry_count": 0
        }
        
        content_result = client.table("processed_content").insert(content_data).execute()
        content_id = content_result.data[0]["id"] if content_result.data else None
        
        logger.info(f"✅ Sauvegardé: article_id={article_id}, content_id={content_id}, status={initial_status}")
        return content_id
        
    except Exception as e:
        # v2.1: Check for duplicate hash error
        if "idx_unique_content_hash" in str(e) or "UNIQUE constraint" in str(e):
            logger.warning(f"⚠️ Contenu dupliqué détecté (hash collision) - ignoré")
            return None
        logger.error(f"❌ Erreur sauvegarde DB: {e}")
        return None


def check_duplicate(topic: Dict) -> bool:
    """Check if similar content was already published."""
    try:
        from duplicate_detector import simple_text_similarity, get_recent_posts
        
        new_text = topic.get("title", "") + " " + topic.get("content", "")
        recent_posts = get_recent_posts(hours=24)
        
        for post in recent_posts:
            similarity = simple_text_similarity(new_text, post.get("text", ""))
            if similarity > 0.7:
                logger.warning(f"⚠️ Contenu similaire trouvé (similarité: {similarity:.0%})")
                return True
        
        return False
    except Exception as e:
        logger.warning(f"Duplicate check failed: {e}")
        return False


def record_publication(content_id: str, facebook_post_id: str) -> None:
    """Record publication in database."""
    try:
        client = config.get_supabase_client()
        
        data = {
            "content_id": content_id,
            "facebook_post_id": facebook_post_id,
            "published_at": datetime.now(timezone.utc).isoformat()
        }
        
        client.table("published_posts").insert(data).execute()
        logger.info(f"✅ Publication enregistrée: {facebook_post_id}")
        
    except Exception as e:
        logger.error(f"❌ Erreur enregistrement publication: {e}")


# ============================================
# ÉTAPE 6: PUBLIER SUR FACEBOOK
# ============================================

def publish_to_facebook(article: Dict, image_path: str) -> Optional[str]:
    """Publie le post sur Facebook."""
    logger.info("📤 Publication sur Facebook...")
    
    hook = article.get("hook", "")
    body = article.get("body", "")
    cta = article.get("cta", "")
    hashtags = article.get("hashtags", [])
    
    message = f"{hook}\n\n{body}\n\n{cta}\n\n{' '.join(hashtags)}"
    
    access_token = config.FACEBOOK_ACCESS_TOKEN
    page_id = config.FACEBOOK_PAGE_ID
    
    if not access_token or not page_id:
        logger.warning("❌ Facebook credentials not configured")
        return None
    
    try:
        url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
        
        with open(image_path, 'rb') as f:
            files = {'source': f}
            data = {
                'message': message,
                'access_token': access_token
            }
            resp = requests.post(url, files=files, data=data, timeout=60)
        
        resp.raise_for_status()
        result = resp.json()
        post_id = result.get("post_id") or result.get("id")
        
        logger.info(f"✅ Publié sur Facebook: {post_id}")
        return post_id
        
    except Exception as e:
        logger.error(f"❌ Erreur publication Facebook: {e}")
        return None


# ============================================
# PIPELINE PRINCIPAL
# ============================================

def create_and_publish(
    topic: Optional[Dict] = None, 
    publish: bool = True,
    save_to_db: bool = True,
    check_duplicates: bool = True,
    style: str = "emotional",
    niche: str = "tech"
) -> Dict:
    """
    Pipeline complet unifié.
    
    Args:
        topic: Custom topic (if None, finds trending)
        publish: Whether to publish to Facebook
        save_to_db: Whether to save to database
        check_duplicates: Whether to check for duplicates
        style: Content style (emotional, factual, casual, motivational)
        niche: Topic niche (tech, ai, business, sports, news, health, or custom)
    
    Returns:
        Dict with all results
    """
    result = {
        "success": False,
        "topic": None,
        "content": None,
        "image_path": None,
        "canvas_path": None,
        "content_id": None,
        "facebook_post_id": None,
        "error": None,
        "style": style,
        "niche": niche
    }
    
    try:
        # 1. Find trending topic
        if topic is None:
            topic = find_trending_topic()
        result["topic"] = topic
        logger.info(f"📰 Sujet: {topic.get('title', '')[:50]}...")
        
        # 2. Check for duplicates
        if check_duplicates and check_duplicate(topic):
            raise ValueError("Similar content already published in last 24h")
        
        # 3. Generate complete content
        client = get_ai_client()
        content = generate_complete_content(topic, client)
        result["content"] = content
        
        # 4. Find matching image
        image_info = content.get("image", {})
        image_path = find_matching_image(image_info, topic.get("title", ""))
        result["image_path"] = image_path
        
        if not image_path:
            raise ValueError("Could not find matching image")
        
        # 5. Compose canvas
        article = content.get("article", {})
        hook_text = article.get("hook", "🔥 خبر عاجل!")
        canvas_path = compose_canvas(image_path, hook_text)
        result["canvas_path"] = canvas_path
        
        # 6. Save to database
        content_id = None
        if save_to_db:
            content_id = save_to_database(topic, content, image_path, canvas_path)
            result["content_id"] = content_id
        
        # 7. Publish to Facebook
        if publish:
            post_id = publish_to_facebook(article, canvas_path)
            result["facebook_post_id"] = post_id
            
            # Record publication
            if content_id and post_id:
                record_publication(content_id, post_id)
        
        result["success"] = True
        logger.info("🎉 Pipeline terminé avec succès!")
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"❌ Erreur pipeline: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return result


def create_preview(topic: Optional[Dict] = None) -> Dict:
    """Create content without publishing (for preview)."""
    return create_and_publish(topic, publish=False, save_to_db=False, check_duplicates=False)


# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("🚀 Pipeline Intelligent Unifié v2")
    print("=" * 60)
    
    publish = "--publish" in sys.argv
    
    print(f"Mode: {'PUBLICATION' if publish else 'TEST'}")
    print()
    
    result = create_and_publish(publish=publish)
    
    print("\n" + "=" * 60)
    print("📊 Résultats:")
    print("=" * 60)
    
    if result["success"]:
        print(f"✅ Succès!")
        print(f"📰 Sujet: {result['topic'].get('title', '')[:50]}...")
        print(f"🖼️ Image: {result['image_path']}")
        print(f"📐 Canvas: {result['canvas_path']}")
        if result["content_id"]:
            print(f"💾 DB ID: {result['content_id']}")
        if result["facebook_post_id"]:
            print(f"📤 Facebook: {result['facebook_post_id']}")
    else:
        print(f"❌ Erreur: {result['error']}")
