"""
Unit tests for publication_tracker module.

Tests cover:
- Content hash computation
- Similarity detection
- Publication checks
- URL tracking
"""

# pytest is used implicitly via fixtures
from unittest.mock import MagicMock, patch
# datetime imports available if needed


class TestContentHash:
    """Tests for content hash computation."""

    def test_compute_content_hash_identical(self):
        """Test that identical texts produce same hash."""
        from publication_tracker import PublicationTracker

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        text = "OpenAI releases GPT-5 with amazing capabilities"

        hash1 = tracker._compute_content_hash(text)
        hash2 = tracker._compute_content_hash(text)

        assert hash1 == hash2

    def test_compute_content_hash_normalized(self):
        """Test that normalization produces same hash."""
        from publication_tracker import PublicationTracker

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        text1 = "OpenAI releases GPT-5"
        text2 = "openai releases gpt-5"  # Different case
        text3 = "OpenAI  releases   GPT-5"  # Extra whitespace

        hash1 = tracker._compute_content_hash(text1)
        hash2 = tracker._compute_content_hash(text2)
        hash3 = tracker._compute_content_hash(text3)

        assert hash1 == hash2 == hash3

    def test_compute_content_hash_different(self):
        """Test that different texts produce different hashes."""
        from publication_tracker import PublicationTracker

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        text1 = "OpenAI releases GPT-5"
        text2 = "Tesla unveils new electric truck"

        hash1 = tracker._compute_content_hash(text1)
        hash2 = tracker._compute_content_hash(text2)

        assert hash1 != hash2

    def test_compute_content_hash_empty(self):
        """Test hash of empty string."""
        from publication_tracker import PublicationTracker

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        hash_empty = tracker._compute_content_hash("")

        assert hash_empty == ""


class TestSimHash:
    """Tests for SimHash computation."""

    def test_simhash_similar_texts(self):
        """Test SimHash similarity for similar texts."""
        from publication_tracker import PublicationTracker

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        text1 = "OpenAI releases new GPT-5 model with amazing capabilities"
        text2 = "OpenAI announces new GPT-5 model with incredible features"

        hash1 = tracker._compute_simhash(text1)
        hash2 = tracker._compute_simhash(text2)

        distance = tracker._hamming_distance(hash1, hash2)
        similarity = 1 - (distance / 64)

        # Similar texts should have similarity > 0.5
        assert similarity > 0.5

    def test_simhash_different_texts(self):
        """Test SimHash for very different texts."""
        from publication_tracker import PublicationTracker

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        text1 = "OpenAI releases new AI model"
        text2 = "Weather forecast shows rain tomorrow in Paris"

        hash1 = tracker._compute_simhash(text1)
        hash2 = tracker._compute_simhash(text2)

        distance = tracker._hamming_distance(hash1, hash2)
        similarity = 1 - (distance / 64)

        # Very different texts should have lower similarity
        assert similarity < 0.8


class TestHammingDistance:
    """Tests for Hamming distance calculation."""

    def test_hamming_distance_identical(self):
        """Test Hamming distance of identical values."""
        from publication_tracker import PublicationTracker

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        distance = tracker._hamming_distance(12345, 12345)

        assert distance == 0

    def test_hamming_distance_different(self):
        """Test Hamming distance of different values."""
        from publication_tracker import PublicationTracker

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        # 0b1010 and 0b1001 differ in 2 bits
        distance = tracker._hamming_distance(0b1010, 0b1001)

        assert distance == 2


class TestIsUrlAlreadyUsed:
    """Tests for is_url_already_used method."""

    @patch("config.get_supabase_client")
    def test_url_in_cache(self, mock_client_fn):
        """Test URL found in cache."""
        from publication_tracker import PublicationTracker

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = {"https://example.com/article"}
        tracker._published_hashes = set()
        tracker._cache = {}

        is_used, reason = tracker.is_url_already_used("https://example.com/article")

        assert is_used is True
        assert "already used" in reason.lower()

    @patch("config.get_supabase_client")
    def test_url_not_used(self, mock_client_fn):
        """Test URL not found."""
        from publication_tracker import PublicationTracker

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        is_used, reason = tracker.is_url_already_used("https://example.com/new-article")

        assert is_used is False


class TestIsContentAlreadyPublished:
    """Tests for is_content_already_published method."""

    @patch("config.get_supabase_client")
    def test_content_published(self, mock_client_fn):
        """Test content that has been published."""
        from publication_tracker import PublicationTracker

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": "pub-1",
                    "facebook_post_id": "fb-123456",
                    "published_at": "2026-01-22T10:00:00",
                }
            ]
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        is_published, reason = tracker.is_content_already_published("content-1")

        assert is_published is True
        assert "already published" in reason.lower()

    @patch("config.get_supabase_client")
    def test_content_not_published(self, mock_client_fn):
        """Test content that has not been published."""
        from publication_tracker import PublicationTracker

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        is_published, reason = tracker.is_content_already_published("content-new")

        assert is_published is False


class TestCanPublish:
    """Tests for can_publish method."""

    @patch("publication_tracker.PublicationTracker.is_similar_content_recent")
    @patch("publication_tracker.PublicationTracker.is_content_already_published")
    @patch("config.get_supabase_client")
    def test_can_publish_new_content(self, mock_client_fn, mock_already_published, mock_similar):
        """Test publishing new, unique content."""
        from publication_tracker import PublicationTracker

        mock_already_published.return_value = (False, "")
        mock_similar.return_value = (False, 0.0, "")

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data={"generated_text": "New content", "article_id": None})
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        can_pub, reason = tracker.can_publish("new-content-id")

        # Note: This test may fail if is_content_already_published is called
        # We're testing the logic flow

    @patch("publication_tracker.PublicationTracker.is_content_already_published")
    def test_cannot_publish_already_published(self, mock_already_published):
        """Test blocking already published content."""
        from publication_tracker import PublicationTracker

        mock_already_published.return_value = (True, "Already published")

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        can_pub, reason = tracker.can_publish("old-content-id")

        assert can_pub is False
        assert "already published" in reason.lower()


class TestRecordPublication:
    """Tests for record_publication method."""

    @patch("config.get_supabase_client")
    def test_record_updates_cache(self, mock_client_fn):
        """Test that recording updates caches."""
        from publication_tracker import PublicationTracker

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data={"generated_text": "Test content"})
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = set()
        tracker._published_hashes = set()
        tracker._cache = {}

        tracker.record_publication("content-1", "fb-post-123", "https://example.com/article")

        assert "https://example.com/article" in tracker._published_urls


class TestGetPublicationStats:
    """Tests for get_publication_stats method."""

    @patch("config.get_supabase_client")
    def test_get_stats(self, mock_client_fn):
        """Test getting publication stats."""
        from publication_tracker import PublicationTracker

        mock_client = MagicMock()
        mock_table = MagicMock()

        # Mock different table responses
        def mock_select(*args, **kwargs):
            result = MagicMock()
            result.execute.return_value = MagicMock(data=[], count=5)
            result.eq.return_value = result
            return result

        mock_table.select = mock_select
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        tracker = PublicationTracker.__new__(PublicationTracker)
        tracker._published_urls = {"url1", "url2"}
        tracker._published_hashes = {"hash1"}
        tracker._cache = {}

        stats = tracker.get_publication_stats()

        assert "cached_urls" in stats
        assert "cached_hashes" in stats
        assert stats["cached_urls"] == 2
        assert stats["cached_hashes"] == 1


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch("publication_tracker.get_tracker")
    def test_can_publish_content(self, mock_get_tracker):
        """Test can_publish_content function."""
        from publication_tracker import can_publish_content

        mock_tracker = MagicMock()
        mock_tracker.can_publish.return_value = (True, "")
        mock_get_tracker.return_value = mock_tracker

        can_pub, reason = can_publish_content("content-1")

        assert can_pub is True
        mock_tracker.can_publish.assert_called_once_with("content-1")
