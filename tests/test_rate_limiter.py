"""Unit tests for rate_limiter module aligned with the current runtime."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


def _table_chain(data=None):
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.gte.return_value = table
    table.execute.return_value = MagicMock(data=data or [])
    return table


class TestGetSafeDailyLimit:
    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_new_page_gets_2(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        client = MagicMock()
        client.table.return_value = _table_chain([])
        mock_client_fn.return_value = client

        assert AdaptiveRateLimiter(page_id="test-page").get_safe_daily_limit() == 2

    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_week_old_page_gets_3(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        first_post_date = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        client = MagicMock()
        client.table.return_value = _table_chain([{"published_at": first_post_date}])
        mock_client_fn.return_value = client

        assert AdaptiveRateLimiter(page_id="test-page").get_safe_daily_limit() == 3

    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_month_old_page_gets_5(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        first_post_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        client = MagicMock()
        client.table.return_value = _table_chain([{"published_at": first_post_date}])
        mock_client_fn.return_value = client

        assert AdaptiveRateLimiter(page_id="test-page").get_safe_daily_limit() == 5

    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_mature_page_gets_8(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        first_post_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        client = MagicMock()
        client.table.return_value = _table_chain([{"published_at": first_post_date}])
        mock_client_fn.return_value = client

        assert AdaptiveRateLimiter(page_id="test-page").get_safe_daily_limit() == 8


class TestCanPostNow:
    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_under_limit_healthy_engagement(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        mock_client_fn.return_value = MagicMock()

        limiter = AdaptiveRateLimiter(page_id="test-page")
        limiter.get_safe_daily_limit = MagicMock(return_value=5)
        limiter.get_today_post_count = MagicMock(return_value=2)
        limiter.get_recent_engagement_rate = MagicMock(return_value=3.5)

        can_post, reason = limiter.can_post_now()
        assert can_post is True
        assert reason == "OK"

    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_at_limit_blocked(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        mock_client_fn.return_value = MagicMock()

        limiter = AdaptiveRateLimiter(page_id="test-page")
        limiter.get_safe_daily_limit = MagicMock(return_value=3)
        limiter.get_today_post_count = MagicMock(return_value=3)

        can_post, reason = limiter.can_post_now()
        assert can_post is False
        assert "Daily limit" in reason

    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_low_engagement_blocked(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        mock_client_fn.return_value = MagicMock()

        limiter = AdaptiveRateLimiter(page_id="test-page")
        limiter.get_safe_daily_limit = MagicMock(return_value=5)
        limiter.get_today_post_count = MagicMock(return_value=1)
        limiter.get_recent_engagement_rate = MagicMock(return_value=0.1)

        can_post, reason = limiter.can_post_now()
        assert can_post is False
        assert "engagement" in reason.lower()


class TestGetRecentEngagement:
    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_no_posts_returns_100(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        client = MagicMock()
        client.table.return_value = _table_chain([])
        mock_client_fn.return_value = client

        assert AdaptiveRateLimiter(page_id="test-page").get_recent_engagement_rate() == 100.0

    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_zero_reach_returns_default(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        client = MagicMock()
        client.table.return_value = _table_chain(
            [
                {"likes": 0, "comments": 0, "shares": 0, "reach": 0},
                {"likes": 0, "comments": 0, "shares": 0, "reach": 0},
            ]
        )
        mock_client_fn.return_value = client

        assert AdaptiveRateLimiter(page_id="test-page").get_recent_engagement_rate() == 5.0


class TestStatusSummaryAndWait:
    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_summary_has_all_fields(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        mock_client_fn.return_value = MagicMock()

        limiter = AdaptiveRateLimiter(page_id="test-page")
        limiter.get_page_age_days = MagicMock(return_value=45)
        limiter.get_safe_daily_limit = MagicMock(return_value=5)
        limiter.get_today_post_count = MagicMock(return_value=2)
        limiter.get_recent_engagement_rate = MagicMock(return_value=3.0)
        limiter.can_post_now = MagicMock(return_value=(True, "OK"))

        summary = limiter.get_status_summary()

        assert summary["page_age_days"] == 45
        assert summary["daily_limit"] == 5
        assert summary["can_post"] is True

    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_wait_until_can_post_returns_zero_when_allowed(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        mock_client_fn.return_value = MagicMock()

        limiter = AdaptiveRateLimiter(page_id="test-page")
        limiter.can_post_now = MagicMock(return_value=(True, "OK"))

        assert limiter.wait_until_can_post().total_seconds() == 0

    @patch("config.get_database_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_wait_until_can_post_returns_24h_on_low_engagement(self, mock_client_fn):
        from rate_limiter import AdaptiveRateLimiter

        mock_client_fn.return_value = MagicMock()

        limiter = AdaptiveRateLimiter(page_id="test-page")
        limiter.can_post_now = MagicMock(return_value=(False, "Low engagement detected"))

        assert limiter.wait_until_can_post().total_seconds() == 24 * 3600
