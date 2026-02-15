"""
Analytics Tracker - Collecte métriques Facebook/Instagram
Ajoute à votre pipeline pour mesurer la performance réelle
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import config

logger = config.get_logger("analytics")


def fetch_post_insights(post_id: str) -> Optional[Dict]:
    """
    Récupère les métriques d'un post Facebook/Instagram

    Args:
        post_id: ID du post publié

    Returns:
        dict: Métriques (reach, engagement, clicks)
    """
    try:
        import requests

        fb_token = config.FACEBOOK_ACCESS_TOKEN
        if not fb_token:
            logger.warning("FACEBOOK_ACCESS_TOKEN non configuré")
            return None

        # API Facebook Graph
        url = f"https://graph.facebook.com/v18.0/{post_id}/insights"
        params = {
            "metric": "post_impressions,post_engaged_users,post_clicks",
            "access_token": fb_token,
        }

        response = requests.get(url, params=params, timeout=15)
        data = response.json()

        if "data" not in data:
            logger.warning(f"Pas de données analytics pour {post_id}")
            return None

        # Extraction métriques
        metrics = {}
        for metric in data["data"]:
            name = metric["name"]
            value = metric["values"][0]["value"] if metric.get("values") else 0

            if name == "post_impressions":
                metrics["reach"] = value
            elif name == "post_engaged_users":
                metrics["engaged_users"] = value
            elif name == "post_clicks":
                metrics["clicks"] = value

        # Calcul engagement rate
        if metrics.get("reach", 0) > 0:
            metrics["engagement_rate"] = (metrics.get("engaged_users", 0) / metrics["reach"]) * 100
        else:
            metrics["engagement_rate"] = 0.0

        logger.info(
            f"📊 Métriques {post_id}: reach={metrics.get('reach', 0)}, engagement={metrics.get('engagement_rate', 0):.2f}%"
        )
        return metrics

    except Exception as e:
        logger.error(f"Erreur fetch insights {post_id}: {e}")
        return None


def save_analytics_to_db(post_id: str, content_id: str, metrics: Dict) -> Optional[Dict]:
    """
    Sauvegarde les métriques dans Supabase

    Args:
        post_id: ID du post Facebook
        content_id: ID du contenu dans processed_content
        metrics: Dict des métriques
    """
    try:
        client = config.get_supabase_client()

        # Structure données
        analytics_data = {
            "post_id": post_id,
            "content_id": content_id,
            "reach": metrics.get("reach", 0),
            "engaged_users": metrics.get("engaged_users", 0),
            "clicks": metrics.get("clicks", 0),
            "engagement_rate": metrics.get("engagement_rate", 0.0),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        # Insert Supabase
        result = client.table("post_analytics").insert(analytics_data).execute()

        logger.info(f"✅ Analytics sauvegardées pour post {post_id}")
        return result.data[0] if result.data else None

    except Exception as e:
        logger.error(f"Erreur save analytics: {e}")
        return None


def get_best_performing_topics(limit: int = 10) -> List[Dict]:
    """
    Identifie les topics les plus performants

    Args:
        limit: Nombre de topics à retourner

    Returns:
        list: Top topics par engagement_rate moyen
    """
    try:
        client = config.get_supabase_client()

        # Récupérer analytics avec contenu
        result = (
            client.table("post_analytics")
            .select("*, processed_content(article_id, hook)")
            .order("engagement_rate", desc=True)
            .limit(limit)
            .execute()
        )

        if result.data:
            logger.info(f"📈 Top {len(result.data)} posts performants identifiés")
            for i, item in enumerate(result.data[:5], 1):
                logger.info(
                    f"  {i}. Engagement: {item.get('engagement_rate', 0):.2f}% "
                    f"- Reach: {item.get('reach', 0)}"
                )

        return result.data or []

    except Exception as e:
        logger.error(f"Erreur get_best_topics: {e}")
        return []


def collect_all_analytics() -> int:
    """
    Collecte les analytics pour tous les posts publiés sans métriques
    Exécuter quotidiennement via cron job

    Returns:
        int: Nombre d'analytics collectées
    """
    try:
        client = config.get_supabase_client()

        # Posts publiés sans analytics collectées
        result = (
            client.table("published_posts")
            .select("id, fb_post_id, content_id")
            .eq("analytics_collected", False)
            .limit(50)
            .execute()
        )

        posts = result.data or []
        logger.info(f"📥 Collecte analytics pour {len(posts)} posts")

        collected = 0
        for post in posts:
            fb_post_id = post.get("fb_post_id")
            if not fb_post_id:
                continue

            metrics = fetch_post_insights(fb_post_id)

            if metrics:
                save_analytics_to_db(fb_post_id, post.get("content_id"), metrics)

                # Marquer comme collecté
                client.table("published_posts").update({"analytics_collected": True}).eq(
                    "id", post["id"]
                ).execute()

                collected += 1

        logger.info(f"✅ {collected}/{len(posts)} analytics collectées")

        # Analyse des meilleurs topics
        if collected > 0:
            get_best_performing_topics()

        return collected

    except Exception as e:
        logger.error(f"Erreur collect_all_analytics: {e}")
        return 0


def get_daily_stats() -> Dict:
    """
    Calcule les statistiques des dernières 24h

    Returns:
        dict: Statistiques quotidiennes
    """
    try:
        client = config.get_supabase_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        # Articles collectés
        raw = (
            client.table("raw_articles")
            .select("id", count="exact")
            .gte("scraped_at", cutoff)
            .execute()
        )

        # Contenus générés
        processed = (
            client.table("processed_content")
            .select("id", count="exact")
            .gte("created_at", cutoff)
            .execute()
        )

        # Posts publiés
        published = (
            client.table("published_posts")
            .select("id", count="exact")
            .gte("published_at", cutoff)
            .execute()
        )

        stats = {
            "articles_collected": raw.count if hasattr(raw, "count") else len(raw.data or []),
            "content_generated": (
                processed.count if hasattr(processed, "count") else len(processed.data or [])
            ),
            "posts_published": (
                published.count if hasattr(published, "count") else len(published.data or [])
            ),
            "images_created": (
                processed.count if hasattr(processed, "count") else len(processed.data or [])
            ),
            "errors": 0,  # TODO: compter depuis logs
            "success_rate": 95.0,  # TODO: calculer réel
        }

        logger.info(f"📊 Stats 24h: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Erreur get_daily_stats: {e}")
        return {}


if __name__ == "__main__":
    print("🔍 Test Analytics Tracker...")

    # Stats quotidiennes
    print("\n📊 Statistiques 24h:")
    stats = get_daily_stats()
    for key, value in stats.items():
        print(f"  - {key}: {value}")

    # Collecte analytics
    print("\n📥 Collecte analytics...")
    collected = collect_all_analytics()
    print(f"  Collectées: {collected}")

    # Best topics
    print("\n📈 Meilleurs topics:")
    topics = get_best_performing_topics(5)
    for t in topics:
        print(f"  - Engagement: {t.get('engagement_rate', 0):.2f}%")
