"""
Image Pipeline Integration - Génère des images Instagram pour chaque article.

Fonctionnalités:
- Téléchargement image d'article (Pexels ou URL originale)
- Traduction/génération du texte arabe
- Génération image Instagram avec template
"""

from __future__ import annotations

import os
import re
import requests
from pathlib import Path
from typing import Optional, Tuple

import config
from image_generator import generate_post_image, OUTPUT_DIR
from gemini_client import get_ai_client, GeminiClient

logger = config.get_logger("image_pipeline")

# Dossiers
DOWNLOADS_DIR = Path(__file__).parent / "downloaded_images"
DOWNLOADS_DIR.mkdir(exist_ok=True)


# Prompt pour générer le texte arabe (HOOK) pour l'image
# Based on: "First line = everything" - la première ligne fait TOUTE la différence
ARABIC_TEXT_PROMPT = """Tu es un expert en copywriting viral pour les réseaux sociaux arabophones.

🎯 OBJECTIF: Créer une ACCROCHE (HOOK) ultra-percutante pour une image Instagram/Facebook.

TITRE DE L'ARTICLE: {title}

═══════════════════════════════════════════════════════════
📝 RÈGLES STRICTES:
═══════════════════════════════════════════════════════════

1. 🔥 LONGUEUR: Maximum 10 mots (très court!)

2. 💥 STYLE: Choisis UN de ces formats d'accroche:
   • Question choc: "هل تصدق...؟"
   • Statistique: "90% لا يعرفون هذا!"
   • Affirmation audacieuse: "هذا غيّر كل شيء!"
   • Teaser: "السر الذي لا يريدونك أن تعرفه..."
   • Émotion: "صدمة!" ou "مفاجأة!"

3. 🌟 TON: Provocant, curieux, excitant

4. ⚠️ MARQUES EN LATIN OBLIGATOIRE:
   ✓ ChatGPT, OpenAI, Tesla, ASUS, Apple, Samsung, iPhone
   ✗ شات جي بي تي, أوبن إي آي, تسلا (INTERDIT)

5. ❌ INTERDIT:
   - Hashtags
   - Ponctuation multiple
   - Plus de 10 mots

═══════════════════════════════════════════════════════════
✅ EXEMPLES CORRECTS:
═══════════════════════════════════════════════════════════
• "صدمة! ChatGPT يفعل هذا الآن"
• "هل تصدق ما فعلته Tesla؟"
• "السر وراء نجاح OpenAI"
• "90% يستخدمون iPhone بشكل خاطئ!"
• "اكتشاف جديد سيغير كل شيء!"

Réponds UNIQUEMENT avec le texte arabe (10 mots max), sans guillemets ni explication.
"""


def download_article_image(
    image_url: Optional[str] = None,
    search_query: Optional[str] = None,
    output_name: str = "article",
) -> Optional[str]:
    """
    Télécharge une image pour l'article avec multi-fallback.

    Priorité:
    1. URL de l'image originale de l'article
    2. Pexels API
    3. Unsplash Source (gratuit, sans clé)
    4. Pixabay API
    5. Lorem Picsum (fallback ultime)

    Returns:
        Chemin vers l'image téléchargée ou None
    """
    output_path = DOWNLOADS_DIR / f"{output_name}.jpg"

    # 1. Essayer l'URL de l'article si fournie
    if image_url:
        try:
            logger.info("Source 1/5: Image article URL")
            resp = requests.get(
                image_url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "image" in content_type:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                logger.info("✅ Image article téléchargée")
                return str(output_path)
        except Exception as e:
            logger.debug("Source 1 échec: %s", e)

    # 2. Utiliser SmartImageSearch (recherche intelligente basée sur le titre)
    if search_query:
        try:
            logger.info("Source 2/5: Smart Image Search (AI)")
            from smart_image_search import get_smart_image_url

            smart_url = get_smart_image_url(search_query)

            if smart_url:
                img_resp = requests.get(smart_url, timeout=15)
                img_resp.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(img_resp.content)
                logger.info("✅ Image intelligente téléchargée")
                return str(output_path)
        except Exception as e:
            logger.debug("Source 2 (Smart) échec: %s", e)

    # 3. Fallback Pexels direct (si Smart échoue)
    pexels_key = os.getenv("PEXELS_API_KEY", "")
    if pexels_key and search_query:
        try:
            logger.info("Source 3/5: Pexels direct fallback")
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": pexels_key},
                params={"query": search_query, "per_page": 1, "orientation": "square"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("photos"):
                photo_url = data["photos"][0]["src"]["large"]
                img_resp = requests.get(photo_url, timeout=15)
                img_resp.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(img_resp.content)
                logger.info("✅ Image Pexels fallback téléchargée")
                return str(output_path)
        except Exception as e:
            logger.debug("Source 3 échec: %s", e)

    # 3. Essayer Unsplash Source (gratuit, sans clé API)
    if search_query:
        try:
            logger.info("Source 3/5: Unsplash Source")
            # Unsplash Source - images gratuites par recherche
            query_clean = search_query.replace(" ", ",")[:50]
            url = f"https://source.unsplash.com/1024x1024/?{query_clean}"
            resp = requests.get(url, timeout=20, allow_redirects=True)
            resp.raise_for_status()

            if len(resp.content) > 10000:  # Minimum 10KB pour être valide
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                logger.info("✅ Image Unsplash téléchargée")
                return str(output_path)
        except Exception as e:
            logger.debug("Source 3 échec: %s", e)

    # 4. Essayer Pixabay si clé API configurée
    pixabay_key = os.getenv("PIXABAY_API_KEY", "")
    if pixabay_key and search_query:
        try:
            logger.info("Source 4/5: Pixabay API")
            resp = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": pixabay_key,
                    "q": search_query[:100],
                    "image_type": "photo",
                    "per_page": 3,
                    "safesearch": "true",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("hits"):
                photo_url = data["hits"][0]["largeImageURL"]
                img_resp = requests.get(photo_url, timeout=15)
                img_resp.raise_for_status()

                with open(output_path, "wb") as f:
                    f.write(img_resp.content)
                logger.info("✅ Image Pixabay téléchargée")
                return str(output_path)
        except Exception as e:
            logger.debug("Source 4 échec: %s", e)

    # 5. Fallback ultime: Lorem Picsum
    try:
        logger.info("Source 5/5: Lorem Picsum (fallback)")
        resp = requests.get(
            "https://picsum.photos/1024/1024",
            timeout=30,
            allow_redirects=True,
        )
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            f.write(resp.content)
        logger.info("✅ Image Lorem Picsum téléchargée")
        return str(output_path)
    except Exception as e:
        logger.error("❌ Toutes les sources ont échoué: %s", e)
        return None


def generate_arabic_text(
    title: str,
    client: Optional[GeminiClient] = None,
) -> str:
    """
    Génère un texte arabe accrocheur à partir du titre de l'article.

    Args:
        title: Titre de l'article
        client: Client AI (optionnel)

    Returns:
        Texte arabe généré
    """
    if client is None:
        client = get_ai_client()

    prompt = ARABIC_TEXT_PROMPT.format(title=title)

    try:
        response = client.generate(prompt, max_tokens=100, temperature=0.7)

        # Nettoyer la réponse
        arabic_text = response.strip()
        # Retirer les guillemets si présents
        arabic_text = arabic_text.strip("\"'")
        # Retirer les explications potentielles
        if "\n" in arabic_text:
            arabic_text = arabic_text.split("\n")[0]

        logger.info("Texte arabe généré: %s", arabic_text[:50])
        return arabic_text

    except Exception as e:
        logger.error("Échec génération texte arabe: %s", e)
        # Fallback: texte par défaut
        return "الذكاء الاصطناعي يغير مستقبل التكنولوجيا"


def generate_social_post(
    article_id: str,
    title: str,
    image_url: Optional[str] = None,
    client: Optional[GeminiClient] = None,
) -> Tuple[str, str]:
    """
    Génère une image Instagram complète pour un article.

    Args:
        article_id: ID unique de l'article
        title: Titre de l'article
        image_url: URL de l'image de l'article (optionnel)
        client: Client AI (optionnel)

    Returns:
        Tuple (chemin_image, texte_arabe)
    """
    logger.info("Génération post social pour: %s", title[:50])

    # 1. Générer le texte arabe
    arabic_text = generate_arabic_text(title, client)

    # 2. Télécharger l'image
    # Extraire mots-clés du titre pour recherche Pexels
    search_query = " ".join(title.split()[:5])  # 5 premiers mots
    image_path = download_article_image(
        image_url=image_url,
        search_query=search_query,
        output_name=f"article_{article_id[:8]}",
    )

    # 3. Générer l'image finale
    output_filename = f"post_{article_id[:8]}.png"
    output_path = str(OUTPUT_DIR / output_filename)

    try:
        result = generate_post_image(
            article_image_path=image_path,
            text=arabic_text,
            output_path=output_path,
        )
        logger.info("Post social généré: %s", result)
        return result, arabic_text

    except Exception as e:
        logger.error("Échec génération image: %s", e)
        return "", arabic_text


def process_article_with_image(
    article: dict,
    client: Optional[GeminiClient] = None,
) -> dict:
    """
    Traite un article et génère l'image associée.

    Args:
        article: Dict avec 'id', 'title', et optionnellement 'image_url'
        client: Client AI (optionnel)

    Returns:
        Dict avec les informations de l'image générée
    """
    article_id = article.get("id", "unknown")
    title = article.get("title", "")
    image_url = article.get("image_url")

    image_path, arabic_text = generate_social_post(
        article_id=article_id,
        title=title,
        image_url=image_url,
        client=client,
    )

    return {
        "article_id": article_id,
        "image_path": image_path,
        "arabic_text": arabic_text,
        "success": bool(image_path),
    }


# Test
if __name__ == "__main__":
    print("=" * 50)
    print("TEST: Image Pipeline Integration")
    print("=" * 50)

    # Test avec un article exemple
    test_article = {
        "id": "test123456",
        "title": "OpenAI releases new GPT-5 model with revolutionary capabilities",
        "image_url": None,  # Utilisera fallback
    }

    print(f"\nArticle: {test_article['title']}")

    result = process_article_with_image(test_article)

    print(f"\nRésultat:")
    print(f"  - Image: {result['image_path']}")
    print(f"  - Texte arabe: {result['arabic_text']}")
    print(f"  - Succès: {result['success']}")

    print("\n" + "=" * 50)
