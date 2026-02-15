"""
Unit tests for duplicate_detector module.

Tests cover:
- Simple text similarity
- TF-IDF similarity calculation
- Duplicate detection
- Content filtering
"""

# pytest is used implicitly via fixtures
from unittest.mock import MagicMock, patch


class TestSimpleTextSimilarity:
    """Tests for simple_text_similarity function."""

    def test_identical_texts(self):
        """Test similarity of identical texts."""
        from duplicate_detector import simple_text_similarity

        text1 = "OpenAI releases new GPT model"
        text2 = "OpenAI releases new GPT model"

        similarity = simple_text_similarity(text1, text2)

        assert similarity == 1.0

    def test_completely_different_texts(self):
        """Test similarity of completely different texts."""
        from duplicate_detector import simple_text_similarity

        text1 = "OpenAI releases new GPT model"
        text2 = "Weather forecast for tomorrow"

        similarity = simple_text_similarity(text1, text2)

        assert similarity < 0.3

    def test_similar_texts(self):
        """Test similarity of similar texts."""
        from duplicate_detector import simple_text_similarity

        text1 = "OpenAI releases new GPT model with amazing capabilities"
        text2 = "OpenAI announces new GPT model with incredible features"

        similarity = simple_text_similarity(text1, text2)

        assert 0.3 < similarity < 1.0

    def test_empty_texts(self):
        """Test similarity with empty texts."""
        from duplicate_detector import simple_text_similarity

        assert simple_text_similarity("", "") == 0.0
        assert simple_text_similarity("text", "") == 0.0
        assert simple_text_similarity("", "text") == 0.0

    def test_case_insensitive(self):
        """Test case insensitivity."""
        from duplicate_detector import simple_text_similarity

        text1 = "OpenAI GPT"
        text2 = "openai gpt"

        similarity = simple_text_similarity(text1, text2)

        assert similarity == 1.0


class TestCalculateSimilarity:
    """Tests for calculate_similarity function."""

    def test_calculate_similarity_empty_posts(self):
        """Test with empty existing posts."""
        from duplicate_detector import calculate_similarity

        similarity, similar_id = calculate_similarity("New text", [])

        assert similarity == 0.0
        assert similar_id is None

    def test_calculate_similarity_empty_new_text(self):
        """Test with empty new text."""
        from duplicate_detector import calculate_similarity

        posts = [{"id": "1", "text": "Existing post"}]
        similarity, similar_id = calculate_similarity("", posts)

        assert similarity == 0.0

    @patch("sklearn.metrics.pairwise.cosine_similarity")
    @patch("sklearn.feature_extraction.text.TfidfVectorizer")
    def test_calculate_similarity_with_sklearn(self, mock_vectorizer, mock_cosine):
        """Test similarity calculation with sklearn."""
        from duplicate_detector import calculate_similarity
        import numpy as np

        mock_vec_instance = MagicMock()
        mock_vec_instance.fit_transform.return_value = MagicMock()
        mock_vectorizer.return_value = mock_vec_instance

        mock_cosine.return_value = np.array([[0.8, 0.3]])

        posts = [{"id": "1", "text": "Similar post"}, {"id": "2", "text": "Different post"}]

        similarity, similar_id = calculate_similarity("New text", posts)

        assert similarity == 0.8
        assert similar_id == "1"


class TestIsDuplicate:
    """Tests for is_duplicate function."""

    @patch("duplicate_detector.calculate_similarity")
    @patch("duplicate_detector.get_recent_posts")
    @patch("config.get_supabase_client")
    def test_is_duplicate_true(self, mock_client_fn, mock_recent, mock_calc):
        """Test detecting a duplicate."""
        from duplicate_detector import is_duplicate

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"generated_text": "Test content"}]
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        mock_recent.return_value = [{"id": "1", "text": "Similar content"}]
        mock_calc.return_value = (0.85, "1")  # High similarity

        is_dup, similarity, similar_id = is_duplicate("content-1", threshold=0.75)

        assert is_dup is True
        assert similarity == 0.85
        assert similar_id == "1"

    @patch("duplicate_detector.calculate_similarity")
    @patch("duplicate_detector.get_recent_posts")
    @patch("config.get_supabase_client")
    def test_is_duplicate_false(self, mock_client_fn, mock_recent, mock_calc):
        """Test detecting a non-duplicate."""
        from duplicate_detector import is_duplicate

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"generated_text": "Unique content"}]
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        mock_recent.return_value = [{"id": "1", "text": "Different content"}]
        mock_calc.return_value = (0.3, "1")  # Low similarity

        is_dup, similarity, similar_id = is_duplicate("content-1", threshold=0.75)

        assert is_dup is False
        assert similarity == 0.3

    @patch("duplicate_detector.get_recent_posts")
    @patch("config.get_supabase_client")
    def test_is_duplicate_no_recent_posts(self, mock_client_fn, mock_recent):
        """Test with no recent posts."""
        from duplicate_detector import is_duplicate

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"generated_text": "Content"}]
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        mock_recent.return_value = []

        is_dup, similarity, similar_id = is_duplicate("content-1")

        assert is_dup is False


class TestGetRecentPosts:
    """Tests for get_recent_posts function."""

    @patch("config.get_supabase_client")
    def test_get_recent_posts_success(self, mock_client_fn):
        """Test getting recent posts."""
        from duplicate_detector import get_recent_posts

        mock_client = MagicMock()
        mock_table = MagicMock()

        # Mock published_posts query
        mock_table.select.return_value.gte.return_value.execute.return_value = MagicMock(
            data=[{"id": "1", "content_id": "c1", "published_at": "2026-01-22T10:00:00"}]
        )

        # Mock processed_content query for text
        def mock_select_side_effect(*args, **kwargs):
            result = MagicMock()
            result.eq.return_value.execute.return_value = MagicMock(
                data=[{"generated_text": "Post content"}]
            )
            result.gte.return_value.execute.return_value = MagicMock(
                data=[{"id": "1", "content_id": "c1"}]
            )
            return result

        mock_table.select.side_effect = mock_select_side_effect
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        posts = get_recent_posts(hours=24)

        # Should return posts with text
        assert isinstance(posts, list)


class TestFilterUniqueContent:
    """Tests for filter_unique_content function."""

    @patch("duplicate_detector.mark_as_duplicate")
    @patch("duplicate_detector.is_duplicate")
    def test_filter_unique_content(self, mock_is_dup, mock_mark):
        """Test filtering unique content."""
        from duplicate_detector import filter_unique_content

        # First is unique, second is duplicate
        mock_is_dup.side_effect = [(False, 0.3, None), (True, 0.9, "existing-1")]

        content_ids = ["new-1", "new-2"]
        unique = filter_unique_content(content_ids, threshold=0.75)

        assert len(unique) == 1
        assert unique[0] == "new-1"
        mock_mark.assert_called_once()


class TestSimilarityThreshold:
    """Tests for similarity threshold."""

    def test_default_threshold(self):
        """Test default similarity threshold value."""
        from duplicate_detector import SIMILARITY_THRESHOLD

        assert SIMILARITY_THRESHOLD == 0.75
        assert 0 < SIMILARITY_THRESHOLD <= 1
