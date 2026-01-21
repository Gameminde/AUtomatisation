"""CLI entry point for the content factory."""

from __future__ import annotations

import argparse

import ai_generator
import analytics
import config
import publisher
import scheduler
import scraper


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Content Factory Orchestrator")
    parser.add_argument(
        "command",
        choices=["scrape", "generate", "schedule", "publish", "analytics", "run-all"],
        help="Action to run",
    )
    parser.add_argument("--limit", type=int, default=10, help="Limit items processed")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "scrape":
        scraper.run()
    elif args.command == "generate":
        ai_generator.process_pending_articles(limit=args.limit)
    elif args.command == "schedule":
        scheduler.schedule_posts()
    elif args.command == "publish":
        publisher.publish_due_posts(limit=args.limit)
    elif args.command == "analytics":
        analytics.sync_metrics(limit=args.limit)
    elif args.command == "run-all":
        scraper.run()
        ai_generator.process_pending_articles(limit=args.limit)
        scheduler.schedule_posts()
        publisher.publish_due_posts(limit=args.limit)
        analytics.sync_metrics(limit=args.limit)


if __name__ == "__main__":
    config.load_dotenv()
    main()
