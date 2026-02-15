"""
Alert System - Notifications via Discord webhook and/or email.
Supports: Discord webhook (preferred), SMTP email, log-only fallback.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Dict, Optional

import requests

import config

logger = config.get_logger("alerts")

# Configuration SMTP
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # App password Gmail

# Discord webhook
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


class AlertLevel:
    """Niveaux d'alerte"""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def send_email_alert(subject: str, body: str, level: str = AlertLevel.ERROR) -> bool:
    """
    Envoie une alerte email

    Args:
        subject: Sujet de l'email
        body: Corps du message
        level: Niveau d'alerte (INFO/WARNING/ERROR/CRITICAL)

    Returns:
        bool: True si envoyé avec succès
    """
    try:
        if not SMTP_USERNAME or not SMTP_PASSWORD or not ALERT_EMAIL:
            logger.warning("⚠️ SMTP non configuré - alerte non envoyée")
            logger.info("[%s] %s", level, subject)
            logger.info(body)
            return False

        # Emoji selon niveau
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨",
        }

        # Couleur selon niveau
        color_map = {
            AlertLevel.INFO: "#2196F3",
            AlertLevel.WARNING: "#ff9800",
            AlertLevel.ERROR: "#f44336",
            AlertLevel.CRITICAL: "#d32f2f",
        }

        # Création message
        msg = MIMEMultipart()
        msg["From"] = SMTP_USERNAME
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = f"{emoji_map.get(level, '')} [{level}] Content Factory: {subject}"

        # Template HTML
        color = color_map.get(level, "#666")
        emoji = emoji_map.get(level, "")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px;">
            <div style="background: {color}; padding: 20px; border-radius: 5px 5px 0 0;">
                <h2 style="margin: 0; color: white;">
                    {emoji} Alerte Pipeline Content Factory
                </h2>
            </div>

            <div style="padding: 20px; background: #f5f5f5; border-radius: 0 0 5px 5px;">
                <h3 style="margin-top: 0;">{subject}</h3>

                <pre style="background: white; padding: 15px; border-left: 4px solid {color};
                            overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;">
{body}
                </pre>

                <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">

                <p style="color: #666; font-size: 12px; margin: 0;">
                    ⏰ {timestamp} | 📧 Content Factory Automation
                </p>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html_body, "html"))

        # Envoi SMTP
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)

        logger.info("✅ Alerte email envoyée: %s", subject)
        return True

    except Exception as e:
        logger.error("❌ Erreur envoi email: %s", e)
        return False


def send_discord_alert(subject: str, body: str, level: str = AlertLevel.ERROR) -> bool:
    """
    Send an alert to a Discord channel via webhook.

    Returns:
        bool: True if sent successfully
    """
    if not DISCORD_WEBHOOK_URL:
        logger.debug("Discord webhook not configured")
        return False

    color_map = {
        AlertLevel.INFO: 0x2196F3,     # blue
        AlertLevel.WARNING: 0xFF9800,  # orange
        AlertLevel.ERROR: 0xF44336,    # red
        AlertLevel.CRITICAL: 0xD32F2F, # dark red
    }
    emoji_map = {
        AlertLevel.INFO: "ℹ️",
        AlertLevel.WARNING: "⚠️",
        AlertLevel.ERROR: "❌",
        AlertLevel.CRITICAL: "🚨",
    }

    payload = {
        "embeds": [{
            "title": f"{emoji_map.get(level, '')} [{level}] {subject}",
            "description": body[:4000],  # Discord limit
            "color": color_map.get(level, 0x666666),
            "footer": {
                "text": f"Content Factory • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            },
        }]
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("✅ Discord alert sent: %s", subject)
        return True
    except Exception as e:
        logger.error("❌ Discord webhook error: %s", e)
        return False


def send_alert(subject: str, body: str, level: str = AlertLevel.ERROR) -> bool:
    """
    Send an alert via the best available channel.

    Priority: Discord webhook > Email > Log-only.
    """
    if DISCORD_WEBHOOK_URL:
        return send_discord_alert(subject, body, level)
    if SMTP_USERNAME and SMTP_PASSWORD and ALERT_EMAIL:
        return send_email_alert(subject, body, level)
    # Fallback: log only
    logger.info("[%s] %s: %s", level, subject, body[:200])
    return False


def alert_pipeline_failure(stage: str, error_details: str) -> None:
    """
    Alerte pour échec d'une étape du pipeline

    Args:
        stage: Nom de l'étape (scrape/generate/schedule/publish)
        error_details: Détails de l'erreur
    """
    subject = f"Échec Pipeline - Étape {stage.upper()}"

    body = f"""
Étape échouée: {stage}
Erreur: {error_details}

Actions recommandées:
1. Vérifier les logs: logs/{stage}.log
2. Vérifier les logs généraux: logs/pipeline.log
3. Vérifier la connexion Supabase
4. Vérifier les clés API (OpenRouter, Pexels)
5. Relancer: python main.py {stage}

Dashboard: streamlit run dashboard.py
    """

    send_email_alert(subject, body, AlertLevel.CRITICAL)


def alert_api_quota_low(api_name: str, remaining_quota: int) -> None:
    """
    Alerte quota API faible

    Args:
        api_name: Nom de l'API (OpenRouter/Pexels)
        remaining_quota: Quota restant
    """
    subject = f"Quota {api_name} Faible ({remaining_quota} restant)"

    body = f"""
API: {api_name}
Quota restant: {remaining_quota}

⚠️ Risque de blocage imminent !

Actions:
- Réduire limite génération (--limit)
- Vérifier facturation API
- Ajouter clés API supplémentaires dans .env
    """

    send_email_alert(subject, body, AlertLevel.WARNING)


def alert_zero_articles_collected() -> None:
    """Alerte si aucun article collecté"""
    subject = "Aucun Article Collecté"

    body = """
Le scraper n'a collecté aucun article lors de la dernière exécution.

Causes possibles:
- Sources RSS/API inaccessibles
- Critères de filtrage trop stricts
- Problème de connexion Internet

Vérifications:
1. Tester connexion Internet
2. Vérifier logs/scraper.log
3. Relancer: python main.py scrape
    """

    send_email_alert(subject, body, AlertLevel.ERROR)


def alert_daily_summary(stats: Dict) -> None:
    """
    Résumé quotidien des stats

    Args:
        stats: Dict avec statistiques (articles, posts, erreurs)
    """
    subject = "Résumé Quotidien Pipeline"

    articles = stats.get("articles_collected", 0)
    generated = stats.get("content_generated", 0)
    images = stats.get("images_created", 0)
    published = stats.get("posts_published", 0)
    errors = stats.get("errors", 0)
    success_rate = stats.get("success_rate", 0)

    body = f"""
📊 Statistiques des dernières 24h:

Articles collectés: {articles}
Contenus générés: {generated}
Images créées: {images}
Posts publiés: {published}

❌ Erreurs: {errors}

Taux de réussite: {success_rate:.1f}%

---------------------
Performances:
- Collecte: {stats.get('avg_scrape_time', 0):.1f}s
- Génération: {stats.get('avg_generation_time', 0):.1f}s
- Publication: {stats.get('avg_publish_time', 0):.1f}s
    """

    send_email_alert(subject, body, AlertLevel.INFO)


def alert_content_going_viral(post_id: str, engagement_rate: float) -> None:
    """
    Notification quand un post devient viral

    Args:
        post_id: ID du post
        engagement_rate: Taux d'engagement (%)
    """
    subject = f"🔥 Post Viral ! Engagement {engagement_rate:.1f}%"

    body = f"""
🎉 Un de vos posts performe exceptionnellement !

Post ID: {post_id}
Taux d'engagement: {engagement_rate:.1f}%

🚀 Ce type de contenu fonctionne bien - à reproduire !

Voir détails: streamlit run dashboard.py
    """

    send_email_alert(subject, body, AlertLevel.INFO)


def with_alert_on_failure(stage_name: str) -> Callable:
    """
    Décorateur pour alerter automatiquement en cas d'échec

    Usage:
        @with_alert_on_failure("generate")
        def generate_content():
            # votre code
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                alert_pipeline_failure(stage_name, str(e))
                raise

        return wrapper

    return decorator


def check_and_alert_quota(api_name: str, remaining: Optional[int]) -> None:
    """
    Vérifie le quota et alerte si nécessaire

    Args:
        api_name: Nom de l'API
        remaining: Quota restant (None si inconnu)
    """
    if remaining is not None and remaining <= 10:
        alert_api_quota_low(api_name, remaining)


if __name__ == "__main__":
    print("📧 Test Alert System...")

    # Vérifier configuration
    print("\n⚙️ Configuration SMTP:")
    print(f"  Server: {SMTP_SERVER}:{SMTP_PORT}")
    print(f"  Username: {'✅ Configuré' if SMTP_USERNAME else '❌ Non configuré'}")
    print(f"  Password: {'✅ Configuré' if SMTP_PASSWORD else '❌ Non configuré'}")
    print(f"  Alert Email: {ALERT_EMAIL or '❌ Non configuré'}")

    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("\n⚠️ Pour activer les alertes email, ajoutez dans .env:")
        print("  SMTP_USERNAME=votre@gmail.com")
        print("  SMTP_PASSWORD=votre_app_password")
        print("  ALERT_EMAIL=destination@email.com")
        print("\n💡 Pour Gmail, créez un 'App Password' sur:")
        print("  https://myaccount.google.com/apppasswords")
    else:
        # Test envoi
        print("\n📧 Envoi test...")
        test_stats = {
            "articles_collected": 45,
            "content_generated": 40,
            "images_created": 40,
            "posts_published": 35,
            "errors": 2,
            "success_rate": 95.5,
        }
        success = send_email_alert(
            "Test Alert System", "Ceci est un test du système d'alerte.", AlertLevel.INFO
        )
        print(f"  Résultat: {'✅ Envoyé' if success else '❌ Échec'}")
