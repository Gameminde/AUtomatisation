"""
Duplicate Content Detector - Évite les posts similaires
Utilise TF-IDF + cosine similarity (sans ML lourd)
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import config

logger = config.get_logger("duplicate_detector")

# Seuil de similarité par défaut (75% = duplicate)
SIMILARITY_THRESHOLD = 0.75


def get_recent_posts(hours: int = 24) -> List[Dict]:
    """
    Récupère les posts publiés dans les dernières X heures
    
    Args:
        hours: Fenêtre temporelle (défaut 24h)
        
    Returns:
        list: Posts avec leur contenu texte
    """
    try:
        client = config.get_supabase_client()
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        # Posts publiés récemment
        result = client.table("published_posts") \
            .select("id, content_id, published_at") \
            .gte("published_at", cutoff) \
            .execute()
        
        posts = []
        for post in result.data or []:
            # Récupérer le contenu généré
            content = client.table("processed_content") \
                .select("generated_text") \
                .eq("id", post.get("content_id")) \
                .execute()
            
            if content.data:
                text = content.data[0].get("generated_text", "")
                if text:
                    posts.append({
                        "id": post["id"],
                        "text": text
                    })
        
        logger.info(f"📥 {len(posts)} posts récents chargés (dernières {hours}h)")
        return posts
        
    except Exception as e:
        logger.error(f"Erreur get_recent_posts: {e}")
        return []


def calculate_similarity(new_text: str, existing_posts: List[Dict]) -> Tuple[float, Optional[str]]:
    """
    Calcule la similarité entre le nouveau texte et les posts existants
    
    Args:
        new_text: Texte du nouveau post à vérifier
        existing_posts: Liste des posts récents
        
    Returns:
        tuple: (max_similarity, most_similar_post_id)
    """
    try:
        if not existing_posts or not new_text:
            return 0.0, None
        
        # Import sklearn pour TF-IDF
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            logger.warning("scikit-learn non installé - détection désactivée")
            logger.info("Installez avec: pip install scikit-learn")
            return 0.0, None
        
        # Préparer corpus
        corpus = [new_text] + [post["text"] for post in existing_posts]
        
        # Vectorisation TF-IDF
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=500,
            ngram_range=(1, 2)  # Unigrams + Bigrams
        )
        
        tfidf_matrix = vectorizer.fit_transform(corpus)
        
        # Similarité cosinus
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])
        
        # Trouver max
        max_idx = similarities.argmax()
        max_similarity = float(similarities[0, max_idx])
        most_similar_id = existing_posts[max_idx]["id"]
        
        logger.debug(f"🔍 Similarité max: {max_similarity:.2%} (post {most_similar_id})")
        
        return max_similarity, most_similar_id
        
    except Exception as e:
        logger.error(f"Erreur calculate_similarity: {e}")
        return 0.0, None


def is_duplicate(content_id: str, threshold: float = SIMILARITY_THRESHOLD) -> Tuple[bool, float, Optional[str]]:
    """
    Vérifie si le contenu est un duplicate des posts récents
    
    Args:
        content_id: ID du contenu à vérifier
        threshold: Seuil de similarité (défaut 75%)
        
    Returns:
        tuple: (is_duplicate: bool, similarity: float, similar_post_id)
    """
    try:
        client = config.get_supabase_client()
        
        # Charger le nouveau contenu
        result = client.table("processed_content") \
            .select("generated_text") \
            .eq("id", content_id) \
            .execute()
        
        if not result.data:
            logger.warning(f"Contenu {content_id} introuvable")
            return False, 0.0, None
        
        new_text = result.data[0].get("generated_text", "")
        if not new_text:
            logger.warning(f"Contenu {content_id} vide")
            return False, 0.0, None
        
        # Charger posts récents
        recent_posts = get_recent_posts(hours=24)
        
        if not recent_posts:
            logger.info("Aucun post récent - pas de duplicate possible")
            return False, 0.0, None
        
        # Calculer similarité
        similarity, similar_id = calculate_similarity(new_text, recent_posts)
        
        # Vérifier seuil
        is_dup = similarity >= threshold
        
        if is_dup:
            logger.warning(
                f"⚠️ DUPLICATE DÉTECTÉ ! "
                f"Similarité {similarity:.2%} avec post {similar_id}"
            )
        else:
            logger.info(f"✅ Contenu unique (similarité {similarity:.2%})")
        
        return is_dup, similarity, similar_id
        
    except Exception as e:
        logger.error(f"Erreur is_duplicate: {e}")
        return False, 0.0, None


def mark_as_duplicate(content_id: str, similar_post_id: str, similarity: float) -> None:
    """
    Marque un contenu comme duplicate dans la DB
    
    Args:
        content_id: ID du contenu duplicate
        similar_post_id: ID du post similaire
        similarity: Score de similarité
    """
    try:
        client = config.get_supabase_client()
        
        client.table("processed_content") \
            .update({
                "status": "duplicate",
                "duplicate_of": similar_post_id,
                "similarity_score": similarity
            }) \
            .eq("id", content_id) \
            .execute()
        
        logger.info(f"Contenu {content_id} marqué comme duplicate")
        
    except Exception as e:
        logger.error(f"Erreur mark_as_duplicate: {e}")


def filter_unique_content(content_ids: List[str], threshold: float = SIMILARITY_THRESHOLD) -> List[str]:
    """
    Filtre une liste de content_ids pour ne garder que les uniques
    À utiliser avant la planification
    
    Args:
        content_ids: Liste des IDs à vérifier
        threshold: Seuil de similarité
        
    Returns:
        list: IDs des contenus uniques
    """
    unique_ids = []
    duplicates = 0
    
    for cid in content_ids:
        is_dup, similarity, similar_id = is_duplicate(cid, threshold)
        
        if not is_dup:
            unique_ids.append(cid)
        else:
            mark_as_duplicate(cid, similar_id, similarity)
            duplicates += 1
    
    logger.info(
        f"✅ Filtrage: {len(unique_ids)} uniques, {duplicates} duplicates sur {len(content_ids)} total"
    )
    
    return unique_ids


def simple_text_similarity(text1: str, text2: str) -> float:
    """
    Calcul de similarité simple sans sklearn (fallback)
    Basé sur les mots communs
    
    Args:
        text1: Premier texte
        text2: Deuxième texte
        
    Returns:
        float: Score de similarité (0-1)
    """
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union) if union else 0.0


if __name__ == "__main__":
    print("🔍 Test Duplicate Detector...")
    
    # Test similarité simple
    text1 = "OpenAI releases new GPT model with amazing capabilities"
    text2 = "OpenAI announces new GPT model with incredible features"
    text3 = "Apple launches new iPhone with better camera"
    
    print(f"\nSimilarité simple:")
    print(f"  Text1 vs Text2: {simple_text_similarity(text1, text2):.2%}")
    print(f"  Text1 vs Text3: {simple_text_similarity(text1, text3):.2%}")
    
    # Test avec posts récents
    print(f"\n📥 Chargement posts récents...")
    try:
        recent = get_recent_posts(24)
        print(f"  {len(recent)} posts trouvés")
    except Exception as e:
        print(f"  Erreur: {e}")
