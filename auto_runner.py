"""
Automated Content Factory Runner

Ce script exécute le pipeline complet de manière autonome.
Idéal pour: cron jobs, Task Scheduler Windows, ou services cloud.

Usage:
    python auto_runner.py                 # Exécute tout
    python auto_runner.py --scrape-only   # Seulement scraping
    python auto_runner.py --publish-only  # Seulement publication
"""

from __future__ import annotations

import sys
import argparse
import traceback
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

import config

# Load environment first
config.load_dotenv()

import ai_generator
import analytics
import publisher
import scheduler
import scraper

logger = config.get_logger("auto_runner")

# Stats tracking
RUN_STATS = {
    "start_time": None,
    "articles_scraped": 0,
    "content_generated": 0,
    "posts_scheduled": 0,
    "posts_published": 0,
    "errors": [],
}


def log_stats():
    """Log run statistics."""
    duration = (datetime.now(timezone.utc) - RUN_STATS["start_time"]).total_seconds()
    
    logger.info("=" * 50)
    logger.info("📊 RUN STATISTICS")
    logger.info("=" * 50)
    logger.info("⏱️  Duration: %.1f seconds", duration)
    logger.info("📰 Articles scraped: %d", RUN_STATS["articles_scraped"])
    logger.info("🤖 Content generated: %d", RUN_STATS["content_generated"])
    logger.info("📅 Posts scheduled: %d", RUN_STATS["posts_scheduled"])
    logger.info("✅ Posts published: %d", RUN_STATS["posts_published"])
    
    if RUN_STATS["errors"]:
        logger.warning("⚠️  Errors encountered: %d", len(RUN_STATS["errors"]))
        for err in RUN_STATS["errors"]:
            logger.warning("   - %s", err)
    else:
        logger.info("✅ No errors!")
    
    logger.info("=" * 50)


def run_scraper():
    """Step 1: Scrape new articles."""
    logger.info("📰 [1/5] Starting scraper...")
    try:
        count = scraper.run()
        RUN_STATS["articles_scraped"] = count
        logger.info("✅ Scraped %d new articles", count)
        return True
    except Exception as e:
        error_msg = f"Scraper failed: {e}"
        RUN_STATS["errors"].append(error_msg)
        logger.error("❌ %s", error_msg)
        return False


def run_generator(limit: int = 10):
    """Step 2: Generate content from articles."""
    logger.info("🤖 [2/5] Starting content generation...")
    try:
        count = ai_generator.process_pending_articles(limit=limit)
        RUN_STATS["content_generated"] = count
        logger.info("✅ Generated %d content pieces", count)
        return True
    except Exception as e:
        error_msg = f"Generator failed: {e}"
        RUN_STATS["errors"].append(error_msg)
        logger.error("❌ %s", error_msg)
        return False


def run_scheduler():
    """Step 3: Schedule posts for publication."""
    logger.info("📅 [3/5] Starting scheduler...")
    try:
        count = scheduler.schedule_posts()
        RUN_STATS["posts_scheduled"] = count
        logger.info("✅ Scheduled %d posts", count)
        return True
    except Exception as e:
        error_msg = f"Scheduler failed: {e}"
        RUN_STATS["errors"].append(error_msg)
        logger.error("❌ %s", error_msg)
        return False


def run_publisher(limit: int = 5):
    """Step 4: Publish due posts to Facebook."""
    logger.info("📤 [4/5] Starting publisher...")
    try:
        count = publisher.publish_due_posts(limit=limit)
        RUN_STATS["posts_published"] = count
        logger.info("✅ Published %d posts", count)
        return True
    except Exception as e:
        error_msg = f"Publisher failed: {e}"
        RUN_STATS["errors"].append(error_msg)
        logger.error("❌ %s", error_msg)
        # Check if it's a token error
        if "token" in str(e).lower() or "expired" in str(e).lower():
            logger.critical("🚨 FACEBOOK TOKEN MAY BE EXPIRED!")
            try:
                from alert_system import send_critical_alert
                send_critical_alert(
                    "Facebook Token Expired",
                    "The Facebook access token appears to be expired. Please renew it."
                )
            except Exception:
                pass
        return False


def run_analytics(limit: int = 20):
    """Step 5: Sync engagement metrics."""
    logger.info("📊 [5/5] Starting analytics sync...")
    try:
        count = analytics.sync_metrics(limit=limit)
        logger.info("✅ Synced metrics for %d posts", count)
        return True
    except Exception as e:
        error_msg = f"Analytics failed: {e}"
        RUN_STATS["errors"].append(error_msg)
        logger.error("❌ %s", error_msg)
        return False


def run_full_pipeline(generate_limit: int = 10, publish_limit: int = 5):
    """Run the complete content factory pipeline."""
    RUN_STATS["start_time"] = datetime.now(timezone.utc)
    
    logger.info("")
    logger.info("🚀" + "=" * 48 + "🚀")
    logger.info("   CONTENT FACTORY - AUTONOMOUS RUN")
    logger.info("   Started: %s", RUN_STATS["start_time"].strftime("%Y-%m-%d %H:%M:%S UTC"))
    logger.info("🚀" + "=" * 48 + "🚀")
    logger.info("")
    
    # Run each step (continue even if one fails)
    run_scraper()
    run_generator(limit=generate_limit)
    run_scheduler()
    run_publisher(limit=publish_limit)
    run_analytics()
    
    # Log final stats
    log_stats()
    
    # Send daily summary if configured
    try:
        from alert_system import send_daily_summary
        send_daily_summary(RUN_STATS)
    except Exception as e:
        logger.debug("Could not send daily summary: %s", e)
    
    # Return success status
    return len(RUN_STATS["errors"]) == 0


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Content Factory Automated Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python auto_runner.py                    # Run full pipeline
  python auto_runner.py --scrape-only      # Only scrape articles
  python auto_runner.py --publish-only     # Only publish due posts
  python auto_runner.py --limit 20         # Generate 20 content pieces
        """
    )
    
    parser.add_argument(
        "--scrape-only", 
        action="store_true",
        help="Only run the scraper"
    )
    parser.add_argument(
        "--generate-only",
        action="store_true", 
        help="Only run content generation"
    )
    parser.add_argument(
        "--publish-only",
        action="store_true",
        help="Only publish due posts"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit for content generation (default: 10)"
    )
    parser.add_argument(
        "--publish-limit",
        type=int,
        default=5,
        help="Limit for publishing (default: 5)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        if args.scrape_only:
            RUN_STATS["start_time"] = datetime.now(timezone.utc)
            run_scraper()
            log_stats()
        elif args.generate_only:
            RUN_STATS["start_time"] = datetime.now(timezone.utc)
            run_generator(limit=args.limit)
            log_stats()
        elif args.publish_only:
            RUN_STATS["start_time"] = datetime.now(timezone.utc)
            run_publisher(limit=args.publish_limit)
            log_stats()
        else:
            success = run_full_pipeline(
                generate_limit=args.limit,
                publish_limit=args.publish_limit
            )
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.critical("💥 Fatal error: %s", e)
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
