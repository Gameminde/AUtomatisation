"""
Smart Image Search - Recherche d'images contextuelles pertinentes
Extrait concepts clés de l'article et cherche images spécifiques
"""

import os
import requests
from typing import Dict, List, Optional

import config

logger = config.get_logger("smart_image_search")

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")


class SmartImageSearch:
    """Recherche d'images contextuelle et intelligente"""

    def __init__(self):
        from gemini_client import get_ai_client

        self.ai_client = get_ai_client()

    def extract_visual_concepts(self, article_title: str, article_content: str = "") -> Dict:
        """
        Extrait concepts visuels clés de l'article avec AI

        Args:
            article_title: Titre de l'article
            article_content: Contenu

        Returns:
            dict: primary_keywords, visual_theme, suggested_queries
        """
        try:
            logger.info("🎨 Extraction concepts visuels...")

            prompt = f"""Analyse cet article tech et extrais les concepts visuels pour trouver une image PERTINENTE.

ARTICLE:
Titre: {article_title}
Contenu: {article_content[:300] if article_content else 'Non disponible'}

Instructions:
1. Identifie 3 mots-clés VISUELS en anglais (pour recherche Pexels)
2. Les mots-clés doivent représenter des objets/scènes CONCRETS (pas abstraits)
3. Évite les noms de personnes, dates, ou textes

Exemples bons mots-clés:
- "AI" → "robot", "circuit board", "neural network visualization"
- "Tesla" → "electric car", "charging station", "EV battery"
- "Space" → "rocket launch", "satellite", "astronaut"

Réponds UNIQUEMENT avec 3 mots-clés séparés par des virgules:
keyword1, keyword2, keyword3"""

            response = self.ai_client.generate(prompt, max_tokens=50, temperature=0.3)

            if response:
                keywords = [k.strip() for k in response.split(",")[:3]]
                logger.info(f"✅ Concepts extraits: {keywords}")
                return {"primary_keywords": keywords, "suggested_queries": keywords}

            return self._extract_keywords_fallback(article_title)

        except Exception as e:
            logger.error(f"Erreur extract_visual_concepts: {e}")
            return self._extract_keywords_fallback(article_title)

    def _extract_keywords_fallback(self, title: str) -> Dict:
        """Extraction basique de mots-clés (fallback)"""
        tech_keywords = {
            "ai": ["artificial intelligence robot", "neural network", "machine learning"],
            "gpt": ["chatbot interface", "AI assistant", "digital brain"],
            "chatgpt": ["chatbot interface", "AI conversation", "language model"],
            "openai": ["AI technology", "machine learning", "futuristic tech"],
            "robot": ["humanoid robot", "robotics automation", "industrial robot"],
            "quantum": ["quantum computer", "physics laboratory", "technology future"],
            "space": ["rocket launch", "space satellite", "astronaut"],
            "tesla": ["electric car", "EV charging", "autonomous vehicle"],
            "apple": ["smartphone technology", "modern device", "tech gadget"],
            "google": ["search technology", "data center", "cloud computing"],
            "meta": ["virtual reality headset", "metaverse", "VR technology"],
            "blockchain": ["cryptocurrency", "digital currency", "blockchain network"],
            "healthcare": ["medical technology", "digital health", "hospital tech"],
            "startup": ["tech office", "entrepreneur", "modern workspace"],
        }

        title_lower = title.lower()

        for key, keywords in tech_keywords.items():
            if key in title_lower:
                logger.info(f"📝 Fallback keywords for '{key}': {keywords}")
                return {"primary_keywords": keywords, "suggested_queries": keywords}

        # Default tech keywords
        default = ["technology innovation", "digital future", "modern tech"]
        logger.info(f"📝 Using default keywords: {default}")
        return {"primary_keywords": default, "suggested_queries": default}

    def search_pexels(self, query: str, per_page: int = 3) -> List[Dict]:
        """
        Recherche images sur Pexels

        Args:
            query: Requête de recherche
            per_page: Nombre de résultats

        Returns:
            list: Images trouvées
        """
        try:
            if not PEXELS_API_KEY:
                logger.warning("PEXELS_API_KEY non configurée")
                return []

            headers = {"Authorization": PEXELS_API_KEY}
            url = "https://api.pexels.com/v1/search"

            params = {
                "query": query,
                "per_page": per_page,
                "orientation": "portrait",
                "size": "large",
            }

            response = requests.get(url, headers=headers, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()

                images = []
                for photo in data.get("photos", []):
                    images.append(
                        {
                            "url": photo["src"]["large2x"],
                            "medium_url": photo["src"]["medium"],
                            "photographer": photo["photographer"],
                            "alt": photo.get("alt", query),
                        }
                    )

                logger.info(f"✅ Pexels: {len(images)} images pour '{query}'")
                return images

            logger.warning(f"Pexels error {response.status_code}")
            return []

        except Exception as e:
            logger.error(f"Erreur search_pexels: {e}")
            return []

    def find_best_image(self, article_title: str, article_content: str = "") -> Optional[str]:
        """
        Trouve la meilleure image pour un article

        Args:
            article_title: Titre de l'article
            article_content: Contenu

        Returns:
            str: URL de la meilleure image ou None
        """
        try:
            # 1. Extraire concepts visuels avec AI
            concepts = self.extract_visual_concepts(article_title, article_content)

            # 2. Chercher avec chaque query
            all_images = []

            for query in concepts.get("suggested_queries", ["technology"])[:3]:
                images = self.search_pexels(query, per_page=2)
                all_images.extend(images)

                if all_images:
                    break  # Prendre la première query qui marche

            if not all_images:
                logger.warning("Aucune image trouvée")
                return None

            # 3. Retourner la première (plus pertinente)
            best = all_images[0]
            logger.info(f"✅ Image sélectionnée: {best['alt'][:30]}... by {best['photographer']}")

            return best["url"]

        except Exception as e:
            logger.error(f"Erreur find_best_image: {e}")
            return None


def get_smart_image_url(title: str, content: str = "") -> Optional[str]:
    """
    Fonction simple pour obtenir une image pertinente

    Args:
        title: Titre de l'article
        content: Contenu optionnel

    Returns:
        str: URL de l'image ou None
    """
    searcher = SmartImageSearch()
    return searcher.find_best_image(title, content)


if __name__ == "__main__":
    print("🔍 Test Smart Image Search...")

    # Test avec différents articles
    test_cases = [
        "OpenAI Releases Revolutionary GPT-5 Model",
        "Tesla Unveils New Electric Truck",
        "NASA Launches Mars Mission 2026",
        "Apple Announces iPhone 17 with AI Features",
        "MIT Researchers Develop Quantum Computer Breakthrough",
    ]

    searcher = SmartImageSearch()

    for title in test_cases:
        print(f"\n{'='*60}")
        print(f"📰 Article: {title}")

        url = searcher.find_best_image(title)

        if url:
            print(f"✅ Image: {url[:60]}...")
        else:
            print("❌ Aucune image")
