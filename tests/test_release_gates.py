import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class FakeTable:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]
        self.filters = []
        self.gte_filters = []
        self.order_key = None
        self.order_desc = False
        self.limit_value = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def gte(self, key, value):
        self.gte_filters.append((key, value))
        return self

    def order(self, key, desc=False):
        self.order_key = key
        self.order_desc = desc
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        rows = [
            dict(row)
            for row in self.rows
            if all(row.get(key) == value for key, value in self.filters)
            and all((row.get(key) or "") >= value for key, value in self.gte_filters)
        ]
        if self.order_key:
            rows.sort(key=lambda row: row.get(self.order_key) or "", reverse=self.order_desc)
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return SimpleNamespace(data=rows)


class FakeClient:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeTable(self.tables.get(name, []))


def test_layout_only_references_existing_static_assets():
    repo_root = Path(__file__).resolve().parents[1]
    layout_path = repo_root / "templates" / "layout.html"
    layout_text = layout_path.read_text(encoding="utf-8")
    asset_paths = re.findall(r"url_for\('static', filename='([^']+)'\)", layout_text)

    assert "js/cf.js" in asset_paths
    for relative_path in asset_paths:
        assert (repo_root / "static" / relative_path).exists(), relative_path


def test_rate_limiter_scopes_published_posts_by_user(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [
        {"id": "a-1", "user_id": "user-a", "page_id": "page-a", "published_at": (now - timedelta(hours=2)).isoformat(), "likes": 10, "comments": 2, "shares": 1, "reach": 100},
        {"id": "a-2", "user_id": "user-a", "page_id": "page-a", "published_at": (now - timedelta(days=2)).isoformat(), "likes": 5, "comments": 1, "shares": 1, "reach": 90},
        {"id": "b-1", "user_id": "user-b", "page_id": "page-b", "published_at": (now - timedelta(hours=1)).isoformat(), "likes": 0, "comments": 0, "shares": 0, "reach": 20},
        {"id": "b-2", "user_id": "user-b", "page_id": "page-b", "published_at": (now - timedelta(minutes=30)).isoformat(), "likes": 0, "comments": 0, "shares": 0, "reach": 20},
    ]
    monkeypatch.setattr("config.get_database_client", lambda: FakeClient({"published_posts": rows}))

    from rate_limiter import AdaptiveRateLimiter

    assert AdaptiveRateLimiter(user_id="user-a").get_today_post_count() == 1
    assert AdaptiveRateLimiter(user_id="user-b").get_today_post_count() == 2


def test_ban_detector_scopes_recent_posts_by_user(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [
        {"id": "a-1", "user_id": "user-a", "page_id": "page-a", "published_at": (now - timedelta(hours=1)).isoformat(), "reach": 1000, "likes": 20, "comments": 5, "shares": 3, "impressions": 2200},
        {"id": "a-2", "user_id": "user-a", "page_id": "page-a", "published_at": (now - timedelta(hours=2)).isoformat(), "reach": 900, "likes": 18, "comments": 4, "shares": 2, "impressions": 1800},
        {"id": "b-1", "user_id": "user-b", "page_id": "page-b", "published_at": (now - timedelta(minutes=20)).isoformat(), "reach": 10, "likes": 0, "comments": 0, "shares": 0, "impressions": 12},
    ]
    monkeypatch.setattr("config.get_database_client", lambda: FakeClient({"published_posts": rows}))

    from ban_detector import BanDetector

    posts = BanDetector(user_id="user-a")._get_recent_posts(lookback=5)
    assert posts
    assert all(post["user_id"] == "user-a" for post in posts)


@patch("publisher.error_handler.is_in_cooldown", return_value=False)
@patch("publisher.fetch_due_posts", return_value=[])
@patch("publisher.can_post_now", return_value=(True, "OK"))
@patch("publisher.should_pause_automation", return_value=False)
@patch("scheduler.process_retries")
def test_publish_due_posts_passes_user_id_to_safety_helpers(
    _mock_retries,
    mock_pause,
    mock_can_post,
    _mock_fetch_due,
    _mock_cooldown,
):
    from publisher import publish_due_posts

    assert publish_due_posts(limit=1, user_id="user-1") == 0
    mock_pause.assert_called_once_with(user_id="user-1")
    mock_can_post.assert_called_once_with(user_id="user-1")


@patch("publisher.fetch_content", return_value=None)
@patch("publisher.can_post_now", return_value=(True, "OK"))
@patch("publisher.should_pause_automation", return_value=False)
def test_publish_content_by_id_passes_user_id_to_safety_helpers(
    mock_pause,
    mock_can_post,
    _mock_fetch_content,
):
    from publisher import publish_content_by_id

    result = publish_content_by_id("content-1", user_id="user-1")

    assert result["success"] is False
    assert result["error"] == "Content not found"
    mock_can_post.assert_called_once_with(user_id="user-1")
    mock_pause.assert_called_once_with(user_id="user-1")
