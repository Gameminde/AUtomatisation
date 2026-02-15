"""
Unit tests for rate_limiter module.

Tests cover:
- Safe daily limit calculation (page age tiers)
- Post count for today
- Can post now (limit + engagement checks)
- Status summary structure
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta, timezone


class TestGetSafeDailyLimit:
    """Tests for get_safe_daily_limit — progressive tier logic."""

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_new_page_gets_2(self, mock_client_fn):
        """Page with 0 days age should get limit of 2."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        # No posts = 0 days age
        mock_table = MagicMock()
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        mock_client.table.return_value = mock_table

        limiter = AdaptiveRateLimiter("test-page")
        assert limiter.get_safe_daily_limit() == 2

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_week_old_page_gets_3(self, mock_client_fn):
        """Page 7-29 days old should get limit of 3."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        # First post 15 days ago
        first_post_date = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        mock_table = MagicMock()
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[{"published_at": first_post_date}])
        )
        mock_client.table.return_value = mock_table

        limiter = AdaptiveRateLimiter("test-page")
        assert limiter.get_safe_daily_limit() == 3

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_month_old_page_gets_5(self, mock_client_fn):
        """Page 30-89 days old should get limit of 5."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        first_post_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        mock_table = MagicMock()
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[{"published_at": first_post_date}])
        )
        mock_client.table.return_value = mock_table

        limiter = AdaptiveRateLimiter("test-page")
        assert limiter.get_safe_daily_limit() == 5

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_mature_page_gets_8(self, mock_client_fn):
        """Page 90+ days old should get limit of 8."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        first_post_date = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
        mock_table = MagicMock()
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[{"published_at": first_post_date}])
        )
        mock_client.table.return_value = mock_table

        limiter = AdaptiveRateLimiter("test-page")
        assert limiter.get_safe_daily_limit() == 8


class TestCanPostNow:
    """Tests for can_post_now — combined limit + engagement check."""

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_under_limit_healthy_engagement(self, mock_client_fn):
        """Under daily limit with healthy engagement → allowed."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        limiter = AdaptiveRateLimiter("test-page")
        limiter.get_safe_daily_limit = MagicMock(return_value=5)
        limiter.get_today_post_count = MagicMock(return_value=2)
        limiter.get_recent_engagement_rate = MagicMock(return_value=3.5)

        can_post, reason = limiter.can_post_now()
        assert can_post is True
        assert reason == "OK"

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_at_limit_blocked(self, mock_client_fn):
        """At daily limit → blocked."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        limiter = AdaptiveRateLimiter("test-page")
        limiter.get_safe_daily_limit = MagicMock(return_value=3)
        limiter.get_today_post_count = MagicMock(return_value=3)

        can_post, reason = limiter.can_post_now()
        assert can_post is False
        assert "Daily limit" in reason

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_low_engagement_blocked(self, mock_client_fn):
        """Under limit but low engagement → blocked."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        limiter = AdaptiveRateLimiter("test-page")
        limiter.get_safe_daily_limit = MagicMock(return_value=5)
        limiter.get_today_post_count = MagicMock(return_value=1)
        limiter.get_recent_engagement_rate = MagicMock(return_value=0.1)  # Below 0.5% threshold

        can_post, reason = limiter.can_post_now()
        assert can_post is False
        assert "engagement" in reason.lower()


class TestGetStatusSummary:
    """Tests for get_status_summary — structure verification."""

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_summary_has_all_fields(self, mock_client_fn):
        """Summary dict should contain all expected keys."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        limiter = AdaptiveRateLimiter("test-page")
        limiter.get_page_age_days = MagicMock(return_value=45)
        limiter.get_safe_daily_limit = MagicMock(return_value=5)
        limiter.get_today_post_count = MagicMock(return_value=2)
        limiter.get_recent_engagement_rate = MagicMock(return_value=3.0)

        summary = limiter.get_status_summary()

        assert "page_age_days" in summary
        assert "daily_limit" in summary
        assert "posts_today" in summary
        assert "engagement_rate" in summary
        assert "can_post" in summary
        assert "reason" in summary
        assert summary["page_age_days"] == 45
        assert summary["daily_limit"] == 5


class TestGetRecentEngagement:
    """Tests for get_recent_engagement_rate — edge cases."""

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_no_posts_returns_100(self, mock_client_fn):
        """New page with no posts → 100% (benefit of doubt)."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        mock_table = MagicMock()
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        mock_client.table.return_value = mock_table

        limiter = AdaptiveRateLimiter("test-page")
        assert limiter.get_recent_engagement_rate() == 100.0

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_zero_reach_returns_default(self, mock_client_fn):
        """Posts with 0 reach → safe default of 5%."""
        from rate_limiter import AdaptiveRateLimiter

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        mock_table = MagicMock()
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[
                {"likes": 0, "comments": 0, "shares": 0, "reach": 0},
                {"likes": 0, "comments": 0, "shares": 0, "reach": 0},
            ])
        )
        mock_client.table.return_value = mock_table

        limiter = AdaptiveRateLimiter("test-page")
        assert limiter.get_recent_engagement_rate() == 5.0
