"""Unit tests for publisher module aligned with the current runtime."""

from unittest.mock import MagicMock, mock_open, patch

import pytest


def _table_chain(data=None):
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.eq.return_value = table
    table.lte.return_value = table
    table.limit.return_value = table
    table.order.return_value = table
    table.single.return_value = table
    table.execute.return_value = MagicMock(data=data or [])
    return table


class TestGraphUrl:
    def test_graph_url_format(self):
        from publisher import GRAPH_API_VERSION, _graph_url

        url = _graph_url("/me/feed")

        assert GRAPH_API_VERSION in url
        assert url.startswith("https://graph.facebook.com/")
        assert url.endswith("/me/feed")

    def test_graph_url_strips_leading_slash(self):
        from publisher import _graph_url

        assert _graph_url("me/feed") == _graph_url("/me/feed")


class TestPublishLowLevelHelpers:
    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_text_post_success_from_env(self, mock_env, mock_post):
        from publisher import publish_text_post

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"id": "123456_789"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        assert publish_text_post("Test message") == "123456_789"

    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_text_post_explicit_credentials_override_env(self, mock_env, mock_post):
        from publisher import publish_text_post

        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"id": "explicit-post"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        assert publish_text_post("Hi", access_token="token", page_id="page") == "explicit-post"
        mock_env.assert_not_called()

    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_text_post_missing_id(self, mock_env, mock_post):
        from publisher import publish_text_post

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with pytest.raises(RuntimeError, match="missing post id"):
            publish_text_post("Test")

    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_text_post_request_error(self, mock_env, mock_post):
        from publisher import publish_text_post
        import requests

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]
        mock_post.side_effect = requests.RequestException("Network error")

        with pytest.raises(RuntimeError, match="Facebook post failed"):
            publish_text_post("Test")

    @patch("builtins.open", mock_open(read_data=b"fake image data"))
    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_photo_post_success(self, mock_env, mock_post):
        from publisher import publish_photo_post

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]
        mock_response = MagicMock()
        mock_response.json.return_value = {"post_id": "photo_123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        assert publish_photo_post("Caption", "path/to/image.jpg") == "photo_123"

    @patch("config.require_env")
    def test_publish_photo_post_missing_file(self, mock_env):
        from publisher import publish_photo_post

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]

        with pytest.raises(RuntimeError, match="Image not found"):
            publish_photo_post("Caption", "missing.jpg")

    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_reel_success(self, mock_env, mock_post):
        from publisher import publish_reel

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "reel_123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        assert publish_reel("https://example.com/video.mp4", "Description") == "reel_123"

    @patch("engine.image_generator.generate_carousel_slide", return_value="slide1.png")
    @patch("builtins.open", mock_open(read_data=b"fake image data"))
    @patch("requests.post")
    @patch("config.require_env")
    def test_publish_carousel_post_success(self, mock_env, mock_post, _mock_slide):
        from publisher import publish_carousel_post

        mock_env.side_effect = lambda key: {
            "FACEBOOK_ACCESS_TOKEN": "token",
            "FACEBOOK_PAGE_ID": "123456",
        }[key]
        upload_response = MagicMock()
        upload_response.json.return_value = {"id": "photo-1"}
        upload_response.raise_for_status = MagicMock()
        feed_response = MagicMock()
        feed_response.json.return_value = {"id": "post-123"}
        feed_response.raise_for_status = MagicMock()
        mock_post.side_effect = [upload_response, feed_response]

        result = publish_carousel_post(
            "Caption",
            [{"slide_number": 1, "headline": "Headline", "body": "Body"}],
        )

        assert result == "post-123"
        assert mock_post.call_count == 2


class TestDbHelpers:
    @patch("config.get_database_client")
    def test_fetch_due_posts_returns_rows(self, mock_client_fn):
        from publisher import fetch_due_posts

        expected = [
            {"id": "1", "content_id": "c1", "status": "scheduled"},
            {"id": "2", "content_id": "c2", "status": "scheduled"},
        ]
        table = _table_chain(expected)
        client = MagicMock()
        client.table.return_value = table
        mock_client_fn.return_value = client

        posts = fetch_due_posts(limit=5)

        assert posts == expected

    @patch("config.get_database_client")
    def test_fetch_due_posts_scopes_user(self, mock_client_fn):
        from publisher import fetch_due_posts

        table = _table_chain([])
        client = MagicMock()
        client.table.return_value = table
        mock_client_fn.return_value = client

        fetch_due_posts(limit=2, user_id="user-1")

        table.eq.assert_any_call("user_id", "user-1")

    @patch("config.get_database_client")
    def test_fetch_content_success(self, mock_client_fn):
        from publisher import fetch_content

        expected = {
            "id": "content-1",
            "post_type": "text",
            "generated_text": "Body",
            "hook": "Hook",
            "call_to_action": "CTA",
            "status": "scheduled",
        }
        table = _table_chain(expected)
        client = MagicMock()
        client.table.return_value = table
        mock_client_fn.return_value = client

        content = fetch_content("content-1")

        assert content["id"] == "content-1"
        assert content["status"] == "scheduled"

    @patch("config.get_database_client")
    def test_mark_published_inserts_new_row_and_updates_content(self, mock_client_fn):
        from publisher import mark_published

        published_table = _table_chain([])
        content_table = _table_chain([{}])
        client = MagicMock()

        def table_for(name):
            return {
                "published_posts": published_table,
                "processed_content": content_table,
            }[name]

        client.table.side_effect = table_for
        mock_client_fn.return_value = client

        mark_published("content-1", "fb-post-123", user_id="user-1")

        published_table.insert.assert_called_once()
        content_table.update.assert_called_once_with(
            {"fb_post_id": "fb-post-123", "status": "published"}
        )

    @patch("config.get_database_client")
    def test_mark_published_updates_existing_row_when_post_id_exists(self, mock_client_fn):
        from publisher import mark_published

        published_table = _table_chain([{"id": "pub-1"}])
        content_table = _table_chain([{}])
        client = MagicMock()

        def table_for(name):
            return {
                "published_posts": published_table,
                "processed_content": content_table,
            }[name]

        client.table.side_effect = table_for
        mock_client_fn.return_value = client

        mark_published("content-1", "fb-post-123")

        published_table.update.assert_called_once()
        published_table.insert.assert_not_called()

    @patch("config.get_database_client")
    def test_update_schedule_status(self, mock_client_fn):
        from publisher import update_schedule_status

        table = _table_chain([{}])
        client = MagicMock()
        client.table.return_value = table
        mock_client_fn.return_value = client

        update_schedule_status("schedule-1", "published", user_id="user-1")

        table.update.assert_called_once_with({"status": "published"})
        table.eq.assert_any_call("user_id", "user-1")


class TestPublishDuePosts:
    @patch("publisher.time.sleep")
    @patch("publisher.record_publication")
    @patch("publisher.update_schedule_status")
    @patch("publisher.mark_published")
    @patch("publisher.publish_text_post")
    @patch("publisher.cas_update_content_status", return_value=True)
    @patch("publisher.fetch_content")
    @patch("publisher.fetch_due_posts")
    @patch("publisher.can_publish_content")
    @patch("publisher.error_handler.is_in_cooldown", return_value=False)
    @patch("publisher.can_post_now", return_value=(True, "OK"))
    @patch("publisher.should_pause_automation", return_value=False)
    @patch("scheduler.process_retries")
    def test_publish_due_posts_success(
        self,
        mock_retries,
        mock_pause,
        mock_can_post,
        mock_cooldown,
        mock_can_publish,
        mock_fetch_due,
        mock_fetch_content,
        mock_cas,
        mock_publish,
        mock_mark,
        mock_update,
        mock_record,
        mock_sleep,
    ):
        from publisher import publish_due_posts

        mock_fetch_due.return_value = [{"id": "s1", "content_id": "c1"}]
        mock_can_publish.return_value = (True, None)
        mock_fetch_content.return_value = {
            "id": "c1",
            "post_type": "text",
            "generated_text": "Body",
            "hook": "Hook",
            "call_to_action": "CTA",
            "hashtags": [],
            "status": "scheduled",
        }
        mock_publish.return_value = "fb-post-123"

        assert publish_due_posts(limit=1) == 1
        mock_publish.assert_called_once()
        mock_mark.assert_called_once()
        mock_update.assert_called_with("s1", "published", user_id=None)

    @patch("publisher.update_schedule_status")
    @patch("publisher.fetch_due_posts")
    @patch("publisher.can_publish_content")
    @patch("publisher.error_handler.is_in_cooldown", return_value=False)
    @patch("publisher.can_post_now", return_value=(True, "OK"))
    @patch("publisher.should_pause_automation", return_value=False)
    @patch("scheduler.process_retries")
    def test_publish_due_posts_skips_duplicate_content(
        self,
        mock_retries,
        mock_pause,
        mock_can_post,
        mock_cooldown,
        mock_can_publish,
        mock_fetch_due,
        mock_update,
    ):
        from publisher import publish_due_posts

        mock_fetch_due.return_value = [{"id": "s1", "content_id": "c1"}]
        mock_can_publish.return_value = (False, "Already published")

        assert publish_due_posts(limit=1) == 0
        mock_update.assert_called_once_with("s1", "failed", user_id=None)

    @patch("publisher.update_schedule_status")
    @patch("publisher.fetch_content", return_value=None)
    @patch("publisher.fetch_due_posts")
    @patch("publisher.can_publish_content", return_value=(True, None))
    @patch("publisher.error_handler.is_in_cooldown", return_value=False)
    @patch("publisher.can_post_now", return_value=(True, "OK"))
    @patch("publisher.should_pause_automation", return_value=False)
    @patch("scheduler.process_retries")
    def test_publish_due_posts_handles_missing_content(
        self,
        mock_retries,
        mock_pause,
        mock_can_post,
        mock_cooldown,
        mock_can_publish,
        mock_fetch_due,
        mock_fetch_content,
        mock_update,
    ):
        from publisher import publish_due_posts

        mock_fetch_due.return_value = [{"id": "s1", "content_id": "c1"}]

        assert publish_due_posts(limit=1) == 0
        mock_update.assert_called_once_with("s1", "failed", user_id=None)

    @patch("publisher.time.sleep")
    @patch("publisher.record_publication")
    @patch("publisher.update_schedule_status")
    @patch("publisher.mark_published")
    @patch("publisher.publish_photo_post")
    @patch("publisher.cas_update_content_status", return_value=True)
    @patch("publisher.fetch_content")
    @patch("publisher.fetch_due_posts")
    @patch("publisher.can_publish_content", return_value=(True, None))
    @patch("publisher.error_handler.is_in_cooldown", return_value=False)
    @patch("publisher.can_post_now", return_value=(True, "OK"))
    @patch("publisher.should_pause_automation", return_value=False)
    @patch("scheduler.process_retries")
    @patch("publisher.os.path.exists", return_value=True)
    def test_publish_due_posts_uses_photo_publish_when_image_exists(
        self,
        mock_exists,
        mock_retries,
        mock_pause,
        mock_can_post,
        mock_cooldown,
        mock_can_publish,
        mock_fetch_due,
        mock_fetch_content,
        mock_cas,
        mock_publish_photo,
        mock_mark,
        mock_update,
        mock_record,
        mock_sleep,
    ):
        from publisher import publish_due_posts

        mock_fetch_due.return_value = [{"id": "s1", "content_id": "c1"}]
        mock_fetch_content.return_value = {
            "id": "c1",
            "post_type": "text",
            "generated_text": "Body",
            "hook": "Hook",
            "call_to_action": "CTA",
            "hashtags": [],
            "status": "scheduled",
            "image_path": "image.jpg",
        }
        mock_publish_photo.return_value = "photo-123"

        assert publish_due_posts(limit=1) == 1
        mock_publish_photo.assert_called_once()

    @patch("publisher.publish_due_posts")
    def test_publish_for_user_skips_without_credentials(self, mock_publish_due):
        from publisher import publish_for_user

        user_config = MagicMock(
            user_id="user-1",
            facebook_access_token="",
            facebook_page_id="",
        )

        assert publish_for_user(user_config) == 0
        mock_publish_due.assert_not_called()

    @patch("publisher.publish_due_posts", return_value=3)
    def test_publish_for_user_passes_user_id(self, mock_publish_due):
        from publisher import publish_for_user

        user_config = MagicMock(
            user_id="user-1",
            facebook_access_token="token",
            facebook_page_id="page",
        )

        assert publish_for_user(user_config) == 3
        mock_publish_due.assert_called_once_with(limit=5, user_id="user-1")

    @patch("publisher.time.sleep")
    @patch("publisher.record_publication")
    @patch("publisher.update_schedule_status")
    @patch("publisher.mark_published")
    @patch("publisher.publish_carousel_post")
    @patch("publisher.cas_update_content_status", return_value=True)
    @patch("publisher.fetch_content")
    @patch("publisher.fetch_due_posts")
    @patch("publisher.can_publish_content", return_value=(True, None))
    @patch("publisher.error_handler.is_in_cooldown", return_value=False)
    @patch("publisher.can_post_now", return_value=(True, "OK"))
    @patch("publisher.should_pause_automation", return_value=False)
    @patch("scheduler.process_retries")
    def test_publish_due_posts_uses_carousel_publish(
        self,
        _mock_retries,
        _mock_pause,
        _mock_can_post,
        _mock_cooldown,
        _mock_can_publish,
        mock_fetch_due,
        mock_fetch_content,
        _mock_cas,
        mock_publish_carousel,
        mock_mark,
        mock_update,
        mock_record,
        _mock_sleep,
    ):
        from publisher import publish_due_posts

        mock_fetch_due.return_value = [{"id": "s1", "content_id": "c1"}]
        mock_fetch_content.return_value = {
            "id": "c1",
            "post_type": "carousel",
            "generated_text": '{"format":"carousel","slides":[{"slide_number":1,"headline":"Headline","body":"Body","visual_suggestion":"Visual"}],"caption":"Caption","hashtags":["#one"]}',
            "hashtags": [],
            "status": "scheduled",
        }
        mock_publish_carousel.return_value = "carousel-123"

        assert publish_due_posts(limit=1) == 1
        mock_publish_carousel.assert_called_once()
        mock_mark.assert_called_once()
        mock_update.assert_called_with("s1", "published", user_id=None)

    @patch("publisher._notify_draft_ready")
    @patch("publisher._mark_content_draft_ready")
    @patch("publisher.fetch_content")
    @patch("publisher.fetch_due_posts")
    @patch("publisher.can_publish_content", return_value=(True, None))
    @patch("publisher.error_handler.is_in_cooldown", return_value=False)
    @patch("publisher.can_post_now", return_value=(True, "OK"))
    @patch("publisher.should_pause_automation", return_value=False)
    @patch("scheduler.process_retries")
    def test_publish_due_posts_marks_draft_only_content_ready(
        self,
        _mock_retries,
        _mock_pause,
        _mock_can_post,
        _mock_cooldown,
        _mock_can_publish,
        mock_fetch_due,
        mock_fetch_content,
        mock_mark_ready,
        mock_notify_ready,
    ):
        from publisher import publish_due_posts

        mock_fetch_due.return_value = [{"id": "s1", "content_id": "c1"}]
        mock_fetch_content.return_value = {
            "id": "c1",
            "post_type": "story_sequence",
            "generated_text": '{"format":"story_sequence","frames":[{"frame_number":1,"text":"Frame"}]}',
            "status": "scheduled",
        }

        assert publish_due_posts(limit=1) == 0
        mock_mark_ready.assert_called_once_with("c1", "s1", None)
        mock_notify_ready.assert_called_once_with(None, "story_sequence")
