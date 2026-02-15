"""
Unit tests for ai_generator module.

Tests cover:
- JSON parsing and recovery
- Batch generation
- Single article generation
- Content saving
- Article processing flow
"""

import json
import pytest
from unittest.mock import MagicMock, patch


class TestFixJsonString:
    """Tests for fix_json_string function."""

    def test_fix_trailing_comma(self):
        """Test removing trailing commas."""
        from ai_generator import fix_json_string

        broken = '{"name": "test", "value": 123,}'
        fixed = fix_json_string(broken)

        assert ",}" not in fixed

    def test_fix_trailing_comma_array(self):
        """Test removing trailing commas in arrays."""
        from ai_generator import fix_json_string

        broken = '["a", "b", "c",]'
        fixed = fix_json_string(broken)

        assert ",]" not in fixed


class TestParseJsonResponse:
    """Tests for parse_json_response function."""

    def test_parse_clean_json_object(self):
        """Test parsing clean JSON object."""
        from ai_generator import parse_json_response

        response = '{"hook": "Test hook", "body": "Test body"}'
        result = parse_json_response(response)

        assert result["hook"] == "Test hook"
        assert result["body"] == "Test body"

    def test_parse_clean_json_array(self):
        """Test parsing clean JSON array."""
        from ai_generator import parse_json_response

        response = '[{"index": 0, "text": "First"}, {"index": 1, "text": "Second"}]'
        result = parse_json_response(response)

        assert len(result) == 2
        assert result[0]["index"] == 0

    def test_parse_json_with_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        from ai_generator import parse_json_response

        response = """```json
        {"hook": "Test", "body": "Content"}
        ```"""
        result = parse_json_response(response)

        assert result["hook"] == "Test"

    def test_parse_json_with_surrounding_text(self):
        """Test parsing JSON with surrounding text."""
        from ai_generator import parse_json_response

        response = """Here is the result:
        {"hook": "Test hook", "body": "Test body"}
        Hope this helps!"""
        result = parse_json_response(response)

        assert result["hook"] == "Test hook"

    def test_parse_json_with_trailing_comma(self):
        """Test parsing JSON with trailing comma."""
        from ai_generator import parse_json_response

        response = '{"hook": "Test", "body": "Content",}'
        result = parse_json_response(response)

        assert result["hook"] == "Test"

    def test_parse_invalid_json_raises(self):
        """Test that invalid JSON raises error."""
        from ai_generator import parse_json_response

        with pytest.raises(ValueError):
            parse_json_response("This is not JSON at all")


class TestGenerateBatch:
    """Tests for generate_batch function."""

    @patch("ai_generator.get_openrouter_client")
    def test_generate_batch_success(
        self, mock_client_fn, sample_articles, mock_openrouter_response
    ):
        """Test successful batch generation."""
        from ai_generator import generate_batch

        mock_client = MagicMock()
        mock_client.call.return_value = json.dumps(
            [
                {
                    "article_index": 0,
                    "text_post": {
                        "hook": "🚨 Test hook!",
                        "body": "Test body content",
                        "cta": "Share your thoughts!",
                        "hashtags": ["#test", "#ai"],
                    },
                    "reel_script": "Test reel script",
                }
            ]
        )
        mock_client_fn.return_value = mock_client

        results = generate_batch(sample_articles[:1])

        assert len(results) >= 1
        mock_client.call.assert_called_once()

    def test_generate_batch_empty_input(self):
        """Test batch generation with empty input."""
        from ai_generator import generate_batch

        results = generate_batch([])

        assert results == []

    @patch("ai_generator.get_openrouter_client")
    def test_generate_batch_handles_rate_limit(self, mock_client_fn):
        """Test handling of rate limit errors."""
        from ai_generator import generate_batch
        from openrouter_client import AllKeysExhaustedError

        mock_client = MagicMock()
        mock_client.call.side_effect = AllKeysExhaustedError("All keys exhausted")
        mock_client_fn.return_value = mock_client

        with pytest.raises(AllKeysExhaustedError):
            generate_batch([{"title": "Test", "content": "Content"}])


class TestGenerateSingle:
    """Tests for generate_single function."""

    @patch("ai_generator.get_openrouter_client")
    def test_generate_single_text_post(self, mock_client_fn):
        """Test generating a single text post."""
        from ai_generator import generate_single

        mock_client = MagicMock()
        mock_client.call.return_value = json.dumps(
            {
                "hook": "🔥 Amazing news!",
                "body": "Content here",
                "cta": "What do you think?",
                "hashtags": ["#tech"],
                "reel_script": None,
            }
        )
        mock_client_fn.return_value = mock_client

        result = generate_single(
            {"title": "Test Article", "content": "Test content"}, post_type="text"
        )

        assert result["hook"] == "🔥 Amazing news!"

    @patch("ai_generator.get_openrouter_client")
    def test_generate_single_reel(self, mock_client_fn):
        """Test generating a reel script."""
        from ai_generator import generate_single

        mock_client = MagicMock()
        mock_client.call.return_value = json.dumps(
            {
                "hook": "🎬 Watch this!",
                "body": "",
                "cta": "Follow for more!",
                "hashtags": ["#reels"],
                "reel_script": "[Visual: Logo] Narration: Breaking news...",
            }
        )
        mock_client_fn.return_value = mock_client

        result = generate_single(
            {"title": "Test Article", "content": "Test content"}, post_type="reel"
        )

        assert "reel_script" in result


class TestSaveProcessedContent:
    """Tests for save_processed_content function."""

    @patch("config.get_supabase_client")
    def test_save_processed_content_success(self, mock_client_fn):
        """Test saving processed content."""
        from ai_generator import save_processed_content

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[{}])
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        save_processed_content(
            article_id="test-article-id",
            post_type="text",
            payload={
                "hook": "Test hook",
                "body": "Test body",
                "cta": "Test CTA",
                "hashtags": ["#test"],
            },
        )

        mock_client.table.assert_called_with("processed_content")
        mock_table.insert.assert_called_once()


class TestProcessPendingArticles:
    """Tests for process_pending_articles function."""

    @patch("ai_generator.mark_article_processed")
    @patch("ai_generator.save_processed_content")
    @patch("ai_generator.generate_batch")
    @patch("config.get_supabase_client")
    def test_process_pending_no_articles(self, mock_client_fn, mock_batch, mock_save, mock_mark):
        """Test processing when no pending articles."""
        from ai_generator import process_pending_articles

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        result = process_pending_articles(limit=5)

        assert result == 0
        mock_batch.assert_not_called()

    @patch("time.sleep")
    @patch("ai_generator.mark_article_processed")
    @patch("ai_generator.save_processed_content")
    @patch("ai_generator.generate_batch")
    @patch("config.get_supabase_client")
    def test_process_pending_with_articles(
        self, mock_client_fn, mock_batch, mock_save, mock_mark, mock_sleep, sample_articles
    ):
        """Test processing pending articles."""
        from ai_generator import process_pending_articles

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=sample_articles[:2])
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        mock_batch.return_value = [
            {
                "text_post": {"hook": "Test", "body": "Body", "cta": "CTA", "hashtags": []},
                "reel_script": "Script",
            }
            for _ in range(2)
        ]

        result = process_pending_articles(limit=2, batch_size=5)

        assert result >= 0
        mock_batch.assert_called()
