"""
Publication Tracker - Prevent duplicate publications and manage content lifecycle.

This module tracks:
- What content has been published
- When it was published
- Article source tracking to prevent same news being reposted
- Content similarity to avoid repetitive posts
- Publication cooldown periods

Author: Content Factory Team
Version: 2.0.0
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import config

logger = config.get_logger("publication_tracker")


def _get_client():
    """
    Return the configured database adapter through the legacy compatibility
    alias first.

    Several older tests and call sites still patch
    ``config.get_supabase_client()``. That helper now returns the configured
    database adapter, so using it here preserves compatibility while still
    working with the real runtime client.
    """
    return config.get_supabase_client()


@dataclass
class PublicationRecord:
    """Record of a published post."""

    content_id: str
    article_id: str
    facebook_post_id: str
    published_at: datetime
    article_url: str
    article_title: str
    content_hash: str
    hook: str


class PublicationTracker:
    """
    Track publications to prevent duplicates.

    Prevents:
    1. Same article being processed twice
    2. Same generated content being published twice
    3. Similar content being published too close together
    4. Same source URL being used multiple times
    """

    # Cooldown period - don't repost similar content within this window
    CONTENT_COOLDOWN_HOURS = 72  # 3 days

    # Source cooldown - don't use same source URL within this window
    SOURCE_COOLDOWN_HOURS = 168  # 7 days

    # Hash similarity threshold
    HASH_SIMILARITY_THRESHOLD = 0.8

    def __init__(self, user_id: Optional[str] = None):
        self.user_id = str(user_id).strip() if user_id else None
        self._cache: Dict[str, PublicationRecord] = {}
        self._published_urls: Set[str] = set()
        self._published_hashes: Set[str] = set()
        self._published_simhashes: list[int] = []
        self._load_recent_publications()

    def _scope_query(self, query, field: str = "user_id"):
        """Apply tenant scoping when the tracker is bound to a specific user."""
        user_id = getattr(self, "user_id", None)
        if user_id:
            return query.eq(field, user_id)
        return query

    def _load_recent_publications(self) -> None:
        """Load recent publications from database."""
        try:
            client = _get_client()

            # Load publications from last 7 days
            cutoff = (datetime.now() - timedelta(hours=self.SOURCE_COOLDOWN_HOURS)).isoformat()

            response = (
                self._scope_query(
                    client.table("published_posts")
                    .select("content_id, facebook_post_id, instagram_post_id, facebook_status, instagram_status, published_at")
                    .gte("published_at", cutoff)
                )
                .execute()
            )

            published_content_ids = set()
            for row in response.data or []:
                content_id = row.get("content_id")
                # Only count rows where at least one platform actually succeeded.
                # Failure-only diagnostic rows must not pollute the hash set.
                if content_id and (
                    row.get("facebook_post_id")
                    or row.get("instagram_post_id")
                    or row.get("facebook_status") == "published"
                    or row.get("instagram_status") == "published"
                ):
                    published_content_ids.add(content_id)

            published_article_ids: Set[str] = set()

            # Load content details for published posts
            if published_content_ids:
                content_response = (
                    self._scope_query(
                        client.table("processed_content")
                        .select("id, article_id, hook, generated_text")
                        .in_("id", list(published_content_ids))
                    )
                    .execute()
                )

                for content in content_response.data or []:
                    text = content.get("generated_text", "")
                    content_hash = self._compute_content_hash(text)
                    self._published_hashes.add(content_hash)
                    simhash = self._compute_simhash(text)
                    if simhash:
                        self._published_simhashes.append(simhash)
                    article_id = content.get("article_id")
                    if article_id:
                        published_article_ids.add(str(article_id))

            # Only preload source URLs that are tied to successfully published
            # content. A merely processed article must not poison duplicate
            # gating for future drafts.
            if published_article_ids:
                article_response = (
                    self._scope_query(
                        client.table("raw_articles")
                        .select("id, url")
                        .in_("id", list(published_article_ids))
                    )
                    .execute()
                )

                for article in article_response.data or []:
                    url = article.get("url")
                    if url:
                        self._published_urls.add(url.lower().strip().rstrip("/"))

            logger.info(
                "Loaded publication history: %d posts, %d URLs, %d hashes",
                len(published_content_ids),
                len(self._published_urls),
                len(self._published_hashes),
            )

        except Exception as e:
            logger.error("Failed to load publication history: %s", e)

    def _compute_content_hash(self, text: str) -> str:
        """
        Compute hash of content for similarity checking.

        Uses a normalized form to catch slight variations.
        """
        if not text:
            return ""

        # Normalize text
        normalized = text.lower().strip()
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        # Remove common punctuation for comparison
        normalized = "".join(c for c in normalized if c.isalnum() or c.isspace())

        return hashlib.md5(normalized.encode()).hexdigest()

    def _compute_simhash(self, text: str) -> int:
        """
        Compute SimHash for fuzzy similarity comparison.

        SimHash allows detecting similar (not just identical) content.
        """
        if not text:
            return 0

        # Tokenize
        words = text.lower().split()

        # Initialize vector
        v = [0] * 64

        for word in words:
            # Hash each word
            word_hash = int(hashlib.md5(word.encode()).hexdigest(), 16)

            for i in range(64):
                bit = (word_hash >> i) & 1
                if bit:
                    v[i] += 1
                else:
                    v[i] -= 1

        # Convert to fingerprint
        fingerprint = 0
        for i in range(64):
            if v[i] > 0:
                fingerprint |= 1 << i

        return fingerprint

    def _hamming_distance(self, hash1: int, hash2: int) -> int:
        """Compute Hamming distance between two hashes."""
        xor = hash1 ^ hash2
        distance = 0
        while xor:
            distance += xor & 1
            xor >>= 1
        return distance

    def is_url_already_used(self, url: str) -> Tuple[bool, str]:
        """
        Check if a source URL has already been used.

        Args:
            url: Source article URL

        Returns:
            Tuple of (is_used, reason)
        """
        if not url:
            return False, ""

        # Normalize URL
        normalized_url = url.lower().strip().rstrip("/")

        if normalized_url in self._published_urls:
            return True, f"URL already used: {url[:50]}..."

        # Check database for older records
        try:
            client = _get_client()

            response = (
                self._scope_query(
                    client.table("raw_articles")
                    .select("id, status, scraped_at")
                    .eq("url", url)
                )
                .execute()
            )

            if response.data:
                article = response.data[0]
                status = article.get("status")
                article_id = article.get("id")

                # Only reject if article was explicitly rejected (not just processed)
                if status == "rejected":
                    return True, "Article was previously rejected"

                # Check if this article's content was actually PUBLISHED to Facebook
                # (processed doesn't mean published)
                if article_id:
                    pub_check = (
                        client.table("processed_content")
                        .select("id")
                        .eq("article_id", article_id)
                    )
                    if getattr(self, "user_id", None):
                        pub_check = pub_check.eq("user_id", self.user_id)
                    pub_check = (
                        pub_check
                        .execute()
                    )
                    for content in pub_check.data or []:
                        content_id = content.get("id")
                        pub_response = (
                            self._scope_query(
                                client.table("published_posts")
                                .select("id")
                                .eq("content_id", content_id)
                            )
                            .execute()
                        )
                        if pub_response.data:
                            return True, f"Article already published to Facebook (ID: {article_id[:8]})"

        except Exception as e:
            logger.warning("URL check failed: %s", e)

        return False, ""

    def is_content_already_published(self, content_id: str) -> Tuple[bool, str]:
        """
        Check if content has already been successfully published to at least one platform.

        A row in published_posts is only treated as "already published" when at least one
        platform succeeded — determined by a non-null facebook_post_id, a non-null
        instagram_post_id, or facebook_status/instagram_status == 'published'.
        Failure-only rows (inserted for diagnostic telemetry) do NOT block re-publishing.

        Args:
            content_id: Content ID to check

        Returns:
            Tuple of (is_published, reason)
        """
        try:
            client = _get_client()

            response = (
                self._scope_query(
                    client.table("published_posts")
                    .select("id, facebook_post_id, instagram_post_id, facebook_status, instagram_status, published_at")
                    .eq("content_id", content_id)
                )
                .execute()
            )

            if response.data:
                for post in response.data:
                    fb_id = post.get("facebook_post_id") or ""
                    ig_id = post.get("instagram_post_id") or ""
                    fb_status = post.get("facebook_status") or ""
                    ig_status = post.get("instagram_status") or ""
                    # Treat as published only when at least one platform actually succeeded
                    if fb_id or ig_id or fb_status == "published" or ig_status == "published":
                        published_at = post.get("published_at", "")
                        platform_hint = ""
                        if fb_id:
                            platform_hint = f"FB: {fb_id[:15]}"
                        elif ig_id:
                            platform_hint = f"IG: {ig_id[:15]}"
                        return True, f"Already published at {published_at} ({platform_hint})"

        except Exception as e:
            logger.warning("Publication check failed: %s", e)

        return False, ""

    def is_similar_content_recent(self, text: str, hours: int = None) -> Tuple[bool, float, str]:
        """
        Check if similar content was published recently.

        Args:
            text: Content text to check
            hours: Cooldown window (default: CONTENT_COOLDOWN_HOURS)

        Returns:
            Tuple of (is_similar, similarity_score, reason)
        """
        if hours is None:
            hours = self.CONTENT_COOLDOWN_HOURS

        content_hash = self._compute_content_hash(text)

        # Exact match check
        if content_hash in self._published_hashes:
            return True, 1.0, "Exact content match found"

        try:
            new_simhash = self._compute_simhash(text)
            for existing_simhash in getattr(self, "_published_simhashes", []):
                distance = self._hamming_distance(new_simhash, existing_simhash)
                similarity = 1 - (distance / 64)
                if similarity >= self.HASH_SIMILARITY_THRESHOLD:
                    return True, similarity, f"Similar content found (similarity: {similarity:.1%})"
        except Exception as e:
            logger.warning("Similarity check failed: %s", e)

        return False, 0.0, ""

    def can_publish(self, content_id: str) -> Tuple[bool, str]:
        """
        Check if content can be published.

        Performs all checks:
        1. Not already published
        2. No similar content recently
        3. Source URL not reused

        Args:
            content_id: Content ID to check

        Returns:
            Tuple of (can_publish, reason if not)
        """
        # Check 1: Already published?
        is_published, reason = self.is_content_already_published(content_id)
        if is_published:
            logger.warning("❌ Cannot publish %s: %s", content_id[:8], reason)
            return False, reason

        # Get content details
        try:
            client = _get_client()

            response = (
                self._scope_query(
                    client.table("processed_content")
                    .select("generated_text, article_id")
                    .eq("id", content_id)
                )
                .single()
                .execute()
            )

            if not response.data:
                return False, "Content not found"

            content = response.data
            text = content.get("generated_text", "")
            article_id = content.get("article_id")

            # Check 2: Similar content?
            is_similar, similarity, reason = self.is_similar_content_recent(text)
            if is_similar:
                logger.warning("❌ Cannot publish %s: %s", content_id[:8], reason)
                return False, reason

            # Check 3: Source URL reused?
            if article_id:
                article_response = (
                    client.table("raw_articles")
                    .select("url")
                    .eq("id", article_id)
                    .single()
                    .execute()
                )

                if article_response.data:
                    url = article_response.data.get("url", "")
                    is_used, reason = self.is_url_already_used(url)
                    if is_used:
                        logger.warning("❌ Cannot publish %s: %s", content_id[:8], reason)
                        return False, reason

        except Exception as e:
            logger.error("Publication check failed: %s", e)
            return False, f"Check failed: {e}"

        logger.info("✅ Content %s cleared for publication", content_id[:8])
        return True, ""

    def record_publication(
        self,
        content_id: str,
        facebook_post_id: str,
        article_url: str = "",
    ) -> None:
        """
        Record a successful publication.

        Args:
            content_id: Published content ID
            facebook_post_id: Facebook post ID
            article_url: Source article URL
        """
        # Update caches
        if article_url:
            self._published_urls.add(article_url.lower().strip())

        try:
            client = _get_client()

            # Get content text for hash
            response = (
                self._scope_query(
                    client.table("processed_content")
                    .select("generated_text")
                    .eq("id", content_id)
                )
                .single()
                .execute()
            )

            if response.data:
                text = response.data.get("generated_text", "")
                content_hash = self._compute_content_hash(text)
                self._published_hashes.add(content_hash)
                simhash = self._compute_simhash(text)
                if simhash:
                    if not hasattr(self, "_published_simhashes"):
                        self._published_simhashes = []
                    self._published_simhashes.append(simhash)

            logger.info(
                "📝 Recorded publication: content=%s, fb=%s", content_id[:8], facebook_post_id[:15]
            )

        except Exception as e:
            logger.warning("Failed to record publication: %s", e)

    def get_unpublished_content(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get content that hasn't been published yet.

        Args:
            limit: Maximum items to return

        Returns:
            List of content items ready for publishing
        """
        unpublished = []

        try:
            client = _get_client()

            # Get all processed content
            content_response = (
                self._scope_query(
                    client.table("processed_content")
                    .select("id, article_id, hook, post_type, generated_at, generated_text")
                    .order("generated_at", desc=True)
                    .limit(limit * 2)
                )
                .execute()
            )

            # Get successfully published content IDs only.
            # Failure-only rows (diagnostic telemetry) must not prevent re-publishing.
            published_response = (
                self._scope_query(
                    client.table("published_posts")
                    .select("content_id, facebook_post_id, instagram_post_id, facebook_status, instagram_status")
                )
                .execute()
            )

            published_ids = {
                row.get("content_id")
                for row in (published_response.data or [])
                if row.get("content_id") and (
                    row.get("facebook_post_id")
                    or row.get("instagram_post_id")
                    or row.get("facebook_status") == "published"
                    or row.get("instagram_status") == "published"
                )
            }

            article_ids = [
                row.get("article_id")
                for row in (content_response.data or [])
                if row.get("article_id")
            ]
            article_url_lookup: Dict[str, str] = {}
            if article_ids:
                article_rows = (
                    client.table("raw_articles")
                    .select("id, url")
                    .in_("id", article_ids)
                    .execute()
                ).data or []
                article_url_lookup = {
                    str(article.get("id")): str(article.get("url") or "")
                    for article in article_rows
                }

            # Filter to unpublished using the preloaded publication snapshot only.
            for content in content_response.data or []:
                content_id = content.get("id")
                article_url = article_url_lookup.get(str(content.get("article_id") or ""), "")

                if content_id in published_ids:
                    logger.debug("Skipping %s: already published", str(content_id or "")[:8])
                    continue

                text = str(content.get("generated_text") or "")
                is_similar, _similarity, reason = self.is_similar_content_recent(text)
                if is_similar:
                    logger.debug("Skipping %s: %s", str(content_id or "")[:8], reason)
                    continue

                normalized_url = article_url.lower().strip().rstrip("/")
                if normalized_url and normalized_url in self._published_urls:
                    logger.debug("Skipping %s: source URL already used", str(content_id or "")[:8])
                    continue

                unpublished.append(content)

                if len(unpublished) >= limit:
                    break

            logger.info("Found %d unpublished content items", len(unpublished))

        except Exception as e:
            logger.error("Failed to get unpublished content: %s", e)

        return unpublished

    def get_publication_stats(self) -> Dict[str, Any]:
        """
        Get publication statistics.

        Returns:
            Dict with stats
        """
        try:
            client = _get_client()

            # Count total processed
            processed = client.table("processed_content").select("id", count="exact").execute()
            if getattr(self, "user_id", None):
                processed = self._scope_query(client.table("processed_content").select("id", count="exact")).execute()

            # Count published
            published = self._scope_query(client.table("published_posts").select("id", count="exact")).execute()

            # Count scheduled
            scheduled = (
                self._scope_query(
                    client.table("scheduled_posts")
                    .select("id", count="exact")
                    .eq("status", "scheduled")
                )
                .execute()
            )

            # Count pending articles
            pending = (
                self._scope_query(
                    client.table("raw_articles")
                    .select("id", count="exact")
                    .eq("status", "pending")
                )
                .execute()
            )

            processed_count = (
                processed.count if hasattr(processed, "count") else len(processed.data or [])
            )
            published_count = (
                published.count if hasattr(published, "count") else len(published.data or [])
            )
            scheduled_count = (
                scheduled.count if hasattr(scheduled, "count") else len(scheduled.data or [])
            )
            pending_count = pending.count if hasattr(pending, "count") else len(pending.data or [])

            return {
                "total_processed": processed_count,
                "total_published": published_count,
                "total_scheduled": scheduled_count,
                "articles_pending": pending_count,
                "publication_rate": round(published_count / max(processed_count, 1) * 100, 1),
                "cached_urls": len(self._published_urls),
                "cached_hashes": len(self._published_hashes),
            }

        except Exception as e:
            logger.error("Failed to get stats: %s", e)
            return {"error": str(e)}

    def cleanup_old_cache(self, days: int = 30) -> int:
        """
        Clean up old entries from cache.

        Args:
            days: Remove entries older than this

        Returns:
            Number of entries removed
        """
        # For memory caches, we keep them as they don't grow too large
        # Database cleanup should be done via SQL functions

        try:
            # TODO: Implement actual database cleanup via SQL function
            # client = config.get_database_client()
            # cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            # This would be implemented with proper SQL function
            logger.info("Cache cleanup completed (retention: %d days)", days)

            return 0

        except Exception as e:
            logger.error("Cleanup failed: %s", e)
            return 0


# Global instance for easy access
_tracker_instances: Dict[Optional[str], PublicationTracker] = {}


def get_tracker(user_id: Optional[str] = None) -> PublicationTracker:
    """Get or create a publication tracker instance scoped to a tenant."""
    key = str(user_id).strip() if user_id else None
    if key not in _tracker_instances:
        _tracker_instances[key] = PublicationTracker(user_id=key)
    return _tracker_instances[key]


# Convenience functions


def can_publish_content(content_id: str, user_id: Optional[str] = None) -> Tuple[bool, str]:
    """Check if content can be published."""
    return get_tracker(user_id=user_id).can_publish(content_id)


def record_publication(
    content_id: str,
    facebook_post_id: str,
    article_url: str = "",
    user_id: Optional[str] = None,
) -> None:
    """Record a successful publication."""
    get_tracker(user_id=user_id).record_publication(content_id, facebook_post_id, article_url)


def get_unpublished_content(limit: int = 50, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get content ready for publishing."""
    return get_tracker(user_id=user_id).get_unpublished_content(limit)


def get_publication_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get publication statistics."""
    return get_tracker(user_id=user_id).get_publication_stats()


if __name__ == "__main__":
    print("📊 Publication Tracker Demo\n")

    tracker = PublicationTracker()

    # Show stats
    stats = tracker.get_publication_stats()
    print("📈 Publication Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Check for unpublished content
    print("\n📝 Unpublished Content:")
    unpublished = tracker.get_unpublished_content(limit=5)
    for content in unpublished:
        print(f"  - {content.get('id', '')[:8]}: {content.get('hook', 'No hook')[:40]}...")

    # Demo similarity check
    print("\n🔍 Similarity Check:")
    test_text = "OpenAI has released GPT-5 with amazing new capabilities"
    is_similar, score, reason = tracker.is_similar_content_recent(test_text)
    print(f"  Text: '{test_text[:40]}...'")
    print(f"  Is similar: {is_similar}")
    print(f"  Score: {score}")
    print(f"  Reason: {reason or 'N/A'}")

    print("\n✅ Publication tracker ready!")
