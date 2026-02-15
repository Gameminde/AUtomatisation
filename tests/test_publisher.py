"""
Unit tests for publisher module.

Tests cover:
- Text post publishing
- Photo post publishing
- Reel publishing
- Due posts fetching
- Content fetching
- Status updates
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
# datetime available if needed


class TestGraphUrl:
    """Tests for _graph_url helper function."""

    def test_graph_url_format(self):
        """Test Graph API URL formatting."""
        from publisher import _graph_url, GRAPH_API_VERSION

        url = _graph_url("/me/feed")

        assert GRAPH_API_VERSION in url
        assert url.startswith("https://graph.facebook.com/")
        assert url.endswith("/me/feed")

    def test_graph_url_strips_leading_slash(self):
        """Test leading slash handling."""
        from publisher import _graph_url

        url1 = _graph_url("me/feed")
        url2 = _graph_url("/me/feed")

        assert url1 == url2


class TestPublishTextPost:
    """Tests for publish_text_post function."""

    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_text_post_success(self, mock_env, mock_post):
        """Test successful text post publishing."""
        from publisher import publish_text_post

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "test-token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "123456_789"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        post_id = publish_text_post("Test message")

        assert post_id == "123456_789"
        mock_post.assert_called_once()

    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_text_post_missing_id(self, mock_env, mock_post):
        """Test handling of missing post ID in response."""
        from publisher import publish_text_post

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "test-token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(RuntimeError, match="missing post id"):
            publish_text_post("Test message")

    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_text_post_request_error(self, mock_env, mock_post):
        """Test handling of request errors."""
        from publisher import publish_text_post
        import requests

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "test-token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]

        mock_post.side_effect = requests.RequestException("Network error")

        with pytest.raises(RuntimeError, match="Facebook post failed"):
            publish_text_post("Test message")


class TestPublishPhotoPost:
    """Tests for publish_photo_post function."""

    @patch("builtins.open", mock_open(read_data=b"fake image data"))
    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_photo_post_success(self, mock_env, mock_post):
        """Test successful photo post publishing."""
        from publisher import publish_photo_post

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "test-token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]

        mock_response = MagicMock()
        mock_response.json.return_value = {"post_id": "123456_photo"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        post_id = publish_photo_post("Test caption", "path/to/image.jpg")

        assert post_id == "123456_photo"

    @patch("config.require_env")
    def test_publish_photo_post_file_not_found(self, mock_env):
        """Test handling of missing image file."""
        from publisher import publish_photo_post

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "test-token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]

        with pytest.raises(RuntimeError, match="Image not found"):
            publish_photo_post("Test", "/nonexistent/path.jpg")


class TestPublishReel:
    """Tests for publish_reel function."""

    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_reel_success(self, mock_env, mock_post):
        """Test successful reel publishing."""
        from publisher import publish_reel

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "test-token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "reel_123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        post_id = publish_reel("https://example.com/video.mp4", "Test description")

        assert post_id == "reel_123"


class TestFetchDuePosts:
    """Tests for fetch_due_posts function."""

    @patch("config.get_supabase_client")
    def test_fetch_due_posts_returns_posts(self, mock_client_fn):
        """Test fetching due posts."""
        from publisher import fetch_due_posts

        mock_client = MagicMock()
        mock_table = MagicMock()

        expected_posts = [
            {
                "id": "1",
                "content_id": "c1",
                "scheduled_time": "2026-01-22T10:00:00",
                "status": "scheduled",
            },
            {
                "id": "2",
                "content_id": "c2",
                "scheduled_time": "2026-01-22T11:00:00",
                "status": "scheduled",
            },
        ]

        mock_table.select.return_value.lte.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=expected_posts
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        posts = fetch_due_posts(limit=5)

        assert len(posts) == 2

    @patch("config.get_supabase_client")
    def test_fetch_due_posts_empty(self, mock_client_fn):
        """Test fetching when no due posts."""
        from publisher import fetch_due_posts

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.lte.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        posts = fetch_due_posts()

        assert posts == []


class TestFetchContent:
    """Tests for fetch_content function."""

    @patch("config.get_supabase_client")
    def test_fetch_content_success(self, mock_client_fn):
        """Test fetching content by ID."""
        from publisher import fetch_content

        mock_client = MagicMock()
        mock_table = MagicMock()

        expected_content = {
            "id": "content-1",
            "post_type": "text",
            "generated_text": "Test content",
            "hook": "Test hook",
            "call_to_action": "Test CTA",
        }

        mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data=expected_content)
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        content = fetch_content("content-1")

        assert content["id"] == "content-1"
        assert content["post_type"] == "text"


class TestUpdateScheduleStatus:
    """Tests for update_schedule_status function."""

    @patch("config.get_supabase_client")
    def test_update_schedule_status(self, mock_client_fn):
        """Test updating schedule status."""
        from publisher import update_schedule_status

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        update_schedule_status("schedule-1", "published")

        mock_table.update.assert_called_once_with({"status": "published"})


class TestMarkPublished:
    """Tests for mark_published function."""

    @patch("config.get_supabase_client")
    def test_mark_published(self, mock_client_fn):
        """Test marking content as published."""
        from publisher import mark_published

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[{}])
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        mark_published("content-1", "fb-post-123")

        mock_client.table.assert_called_with("published_posts")
        mock_table.insert.assert_called_once()


class TestPublishDuePosts:
    """Tests for publish_due_posts function."""

    @patch("time.sleep")
    @patch("publisher.record_publication")
    @patch("publisher.can_publish_content")
    @patch("publisher.update_schedule_status")
    @patch("publisher.mark_published")
    @patch("publisher.publish_text_post")
    @patch("publisher.fetch_content")
    @patch("publisher.fetch_due_posts")
    def test_publish_due_posts_success(
        self,
        mock_fetch_due,
        mock_fetch_content,
        mock_publish,
        mock_mark,
        mock_update,
        mock_can_publish,
        mock_record,
        mock_sleep,
    ):
        """Test publishing due posts."""
        from publisher import publish_due_posts

        mock_fetch_due.return_value = [{"id": "s1", "content_id": "c1"}]
        mock_can_publish.return_value = (True, None)  # Allow publishing

        mock_fetch_content.return_value = {
            "id": "c1",
            "post_type": "text",
            "generated_text": "Content",
            "hook": "Hook",
            "call_to_action": "CTA",
        }

        mock_publish.return_value = "fb-post-123"

        result = publish_due_posts(limit=1)

        assert result == 1
        mock_publish.assert_called_once()
        mock_mark.assert_called_once()
        mock_update.assert_called_with("s1", "published")
