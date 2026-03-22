"""
Root-level compatibility shim — the canonical implementation lives in engine/publisher.py.
Import this module normally; all symbols are re-exported transparently.

Key public API:
  publish_content_by_id(content_id, user_id=None) -> Dict
  publish_due_posts(limit, user_id=None) -> Dict
  fetch_content(content_id, user_id=None) -> Optional[Dict]
  mark_published(content_id, post_id, user_id=None) -> None
"""
from engine.publisher import *  # noqa: F401, F403
from engine.publisher import (  # noqa: F401 – explicit re-export for static analysis
    publish_content_by_id,
    publish_due_posts,
    fetch_content,
    fetch_due_posts,
    mark_published,
    update_schedule_status,
    cas_update_content_status,
    publish_text_post,
    publish_photo_post,
    publish_with_duplicate_check,
    get_publication_status,
)
# Backward-compat alias (used by older scripts)
publish_posts = publish_due_posts  # noqa: F401
