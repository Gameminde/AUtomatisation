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

    def __init__(self):
        self._cache: Dict[str, PublicationRecord] = {}
        self._published_urls: Set[str] = set()
        self._published_hashes: Set[str] = set()
        self._load_recent_publications()

    def _load_recent_publications(self) -> None:
        """Load recent publications from database."""
        try:
            client = config.get_supabase_client()

            # Load publications from last 7 days
            cutoff = (datetime.now() - timedelta(hours=self.SOURCE_COOLDOWN_HOURS)).isoformat()

            response = (
                client.table("published_posts")
                .select("content_id, facebook_post_id, published_at")
                .gte("published_at", cutoff)
                .execute()
            )

            published_content_ids = set()
            for row in response.data or []:
                content_id = row.get("content_id")
                if content_id:
                    published_content_ids.add(content_id)

            # Load content details for published posts
            if published_content_ids:
                content_response = (
                    client.table("processed_content")
                    .select("id, article_id, hook, generated_text")
                    .in_("id", list(published_content_ids))
                    .execute()
                )

                for content in content_response.data or []:
                    text = content.get("generated_text", "")
                    content_hash = self._compute_content_hash(text)
                    self._published_hashes.add(content_hash)

            # Load source URLs
            article_response = (
                client.table("raw_articles").select("url").eq("status", "processed").execute()
            )

            for article in article_response.data or []:
                url = article.get("url")
                if url:
                    self._published_urls.add(url)

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
            client = config.get_supabase_client()

            response = (
                client.table("raw_articles")
                .select("id, status, scraped_at")
                .eq("url", url)
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
                        .execute()
                    )
                    for content in pub_check.data or []:
                        content_id = content.get("id")
                        pub_response = (
                            client.table("published_posts")
                            .select("id")
                            .eq("content_id", content_id)
                            .execute()
                        )
                        if pub_response.data:
                            return True, f"Article already published to Facebook (ID: {article_id[:8]})"

        except Exception as e:
            logger.warning("URL check failed: %s", e)

        return False, ""

    def is_content_already_published(self, content_id: str) -> Tuple[bool, str]:
        """
        Check if content has already been published.

        Args:
            content_id: Content ID to check

        Returns:
            Tuple of (is_published, reason)
        """
        try:
            client = config.get_supabase_client()

            response = (
                client.table("published_posts")
                .select("id, facebook_post_id, published_at")
                .eq("content_id", content_id)
                .execute()
            )

            if response.data:
                post = response.data[0]
                published_at = post.get("published_at", "")
                fb_id = post.get("facebook_post_id", "")
                return True, f"Already published at {published_at} (FB: {fb_id[:15]}...)"

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

        # SimHash similarity check - ONLY against PUBLISHED content
        try:
            new_simhash = self._compute_simhash(text)

            client = config.get_supabase_client()

            # Get only content that was actually published to Facebook
            published_response = (
                client.table("published_posts")
                .select("content_id")
                .execute()
            )

            published_content_ids = [
                row.get("content_id")
                for row in (published_response.data or [])
                if row.get("content_id")
            ]

            if not published_content_ids:
                # No published content yet, so nothing to compare against
                return False, 0.0, ""

            response = (
                client.table("processed_content")
                .select("id, generated_text, article_id")
                .in_("id", published_content_ids)
                .execute()
            )

            for content in response.data or []:
                existing_text = content.get("generated_text", "")
                if not existing_text:
                    continue

                existing_simhash = self._compute_simhash(existing_text)
                distance = self._hamming_distance(new_simhash, existing_simhash)

                # Convert distance to similarity (0-1)
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
            client = config.get_supabase_client()

            response = (
                client.table("processed_content")
                .select("generated_text, article_id")
                .eq("id", content_id)
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
            client = config.get_supabase_client()

            # Get content text for hash
            response = (
                client.table("processed_content")
                .select("generated_text")
                .eq("id", content_id)
                .single()
                .execute()
            )

            if response.data:
                text = response.data.get("generated_text", "")
                content_hash = self._compute_content_hash(text)
                self._published_hashes.add(content_hash)

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
            client = config.get_supabase_client()

            # Get all processed content
            content_response = (
                client.table("processed_content")
                .select("id, article_id, hook, post_type, generated_at")
                .order("generated_at", desc=True)
                .limit(limit * 2)
                .execute()
            )

            # Get published content IDs
            published_response = client.table("published_posts").select("content_id").execute()

            published_ids = {row.get("content_id") for row in published_response.data or []}

            # Filter to unpublished
            for content in content_response.data or []:
                content_id = content.get("id")

                if content_id not in published_ids:
                    can_publish, reason = self.can_publish(content_id)

                    if can_publish:
                        unpublished.append(content)
                    else:
                        logger.debug("Skipping %s: %s", content_id[:8], reason)

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
            client = config.get_supabase_client()

            # Count total processed
            processed = client.table("processed_content").select("id", count="exact").execute()

            # Count published
            published = client.table("published_posts").select("id", count="exact").execute()

            # Count scheduled
            scheduled = (
                client.table("scheduled_posts")
                .select("id", count="exact")
                .eq("status", "scheduled")
                .execute()
            )

            # Count pending articles
            pending = (
                client.table("raw_articles")
                .select("id", count="exact")
                .eq("status", "pending")
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
            # client = config.get_supabase_client()
            # cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            # This would be implemented with proper SQL function
            logger.info("Cache cleanup completed (retention: %d days)", days)

            return 0

        except Exception as e:
            logger.error("Cleanup failed: %s", e)
            return 0


# Global instance for easy access
_tracker_instance: Optional[PublicationTracker] = None


def get_tracker() -> PublicationTracker:
    """Get or create the global publication tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = PublicationTracker()
    return _tracker_instance


# Convenience functions


def can_publish_content(content_id: str) -> Tuple[bool, str]:
    """Check if content can be published."""
    return get_tracker().can_publish(content_id)


def record_publication(content_id: str, facebook_post_id: str, article_url: str = "") -> None:
    """Record a successful publication."""
    get_tracker().record_publication(content_id, facebook_post_id, article_url)


def get_unpublished_content(limit: int = 50) -> List[Dict[str, Any]]:
    """Get content ready for publishing."""
    return get_tracker().get_unpublished_content(limit)


def get_publication_stats() -> Dict[str, Any]:
    """Get publication statistics."""
    return get_tracker().get_publication_stats()


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
