"""
analytics_tracker — Engagement sync stub.
Full implementation arrives in Phase 4.
"""
import config

logger = config.get_logger("analytics_tracker")


def sync_all_posts(user_id: str = None) -> int:
    """Sync engagement metrics for all published posts (stub)."""
    logger.info("analytics_tracker: sync_all_posts called (stub, user_id=%s)", user_id)
    return 0
