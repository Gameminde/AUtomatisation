"""
Unit tests for ban_detector module.

Tests cover:
- Reach drop detection (normal, severe, zero baseline)
- Engagement drop detection
- Frequency anomaly detection
- Full shadowban check orchestration
- Auto-pause logic
"""

import pytest
from unittest.mock import MagicMock, patch


def _make_posts(recent_reach, older_reach, count_each=3):
    """Helper: build a list of mock posts with given reach values."""
    recent = [
        {"id": f"r{i}", "reach": recent_reach, "likes": 5, "comments": 2,
         "shares": 1, "impressions": recent_reach * 2, "published_at": f"2026-02-{10+i}"}
        for i in range(count_each)
    ]
    older = [
        {"id": f"o{i}", "reach": older_reach, "likes": 10, "comments": 5,
         "shares": 3, "impressions": older_reach * 2, "published_at": f"2026-02-{i+1}"}
        for i in range(count_each + 1)  # need at least 4 older posts for slicing
    ]
    return recent + older


class TestCheckReachDrop:
    """Tests for _check_reach_drop — the main ban signal."""

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_stable_reach_ok(self, mock_client_fn):
        """No significant drop → status ok."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        # Recent reach = 1000, older reach = 1000 → ratio = 1.0
        posts = _make_posts(1000, 1000)
        result = detector._check_reach_drop(posts)

        assert result["status"] == "ok"

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_severe_reach_drop_warning(self, mock_client_fn):
        """Reach dropped >50% → warning."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        # Recent = 200, older = 1000 → ratio = 0.2, drop = 80%
        posts = _make_posts(200, 1000)
        result = detector._check_reach_drop(posts)

        assert result["status"] == "warning"
        assert result["severity"] == 8  # <0.3 ratio → severity 8

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_moderate_reach_drop_warning(self, mock_client_fn):
        """Reach dropped ~60% → severity 5 warning."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        # Recent = 400, older = 1000 → ratio = 0.4 (< 0.5 threshold)
        posts = _make_posts(400, 1000)
        result = detector._check_reach_drop(posts)

        assert result["status"] == "warning"
        assert result["severity"] == 5

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_zero_baseline_returns_ok(self, mock_client_fn):
        """Zero older reach → can't calculate, return ok."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        posts = _make_posts(500, 0)
        result = detector._check_reach_drop(posts)

        assert result["status"] == "ok"
        assert "baseline" in result["reason"].lower()

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_too_few_posts_returns_ok(self, mock_client_fn):
        """Less than 6 posts → not enough data."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        posts = [{"id": f"p{i}", "reach": 100} for i in range(4)]
        result = detector._check_reach_drop(posts)

        assert result["status"] == "ok"


class TestCheckEngagementDrop:
    """Tests for _check_engagement_drop."""

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_stable_engagement_ok(self, mock_client_fn):
        """Engagement stable → ok."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        posts = _make_posts(1000, 1000)  # same reach, same engagement
        result = detector._check_engagement_drop(posts)

        assert result["status"] == "ok"

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_engagement_dropped_warning(self, mock_client_fn):
        """Engagement dropped >60% → warning."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        # Recent: low engagement, older: high engagement
        recent = [
            {"id": f"r{i}", "reach": 1000, "likes": 0, "comments": 0, "shares": 0}
            for i in range(3)
        ]
        older = [
            {"id": f"o{i}", "reach": 1000, "likes": 50, "comments": 20, "shares": 10}
            for i in range(4)
        ]
        posts = recent + older

        result = detector._check_engagement_drop(posts)
        assert result["status"] == "warning"

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_too_few_posts_ok(self, mock_client_fn):
        """Insufficient posts → ok."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        posts = [{"id": "1", "reach": 100, "likes": 5, "comments": 2, "shares": 1}]
        result = detector._check_engagement_drop(posts)

        assert result["status"] == "ok"


class TestCheckFrequencyAnomaly:
    """Tests for _check_frequency_anomaly."""

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_normal_ratio_ok(self, mock_client_fn):
        """Normal impressions/reach ratio → ok."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        posts = [
            {"id": f"r{i}", "reach": 1000, "impressions": 2000}
            for i in range(3)
        ]

        result = detector._check_frequency_anomaly(posts)
        assert result["status"] == "ok"

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_low_impressions_warning(self, mock_client_fn):
        """Abnormally low impressions → throttled warning."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")

        # impressions/reach ratio < 0.5
        posts = [
            {"id": f"r{i}", "reach": 1000, "impressions": 300}
            for i in range(3)
        ]

        result = detector._check_frequency_anomaly(posts)
        assert result["status"] == "warning"
        assert "throttled" in result["reason"].lower()


class TestAutoPause:
    """Tests for auto_pause_if_needed — severity-based decisions."""

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_high_severity_pauses(self, mock_client_fn):
        """Severity >= 7 → should pause."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")
        detector.send_alert = MagicMock()  # don't actually send email

        result = {"status": "warning", "reason": "Major reach drop", "severity": 8}
        assert detector.auto_pause_if_needed(result) is True
        detector.send_alert.assert_called_once()

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_moderate_severity_continues(self, mock_client_fn):
        """Severity 5-6 → alert but continue."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")
        detector.send_alert = MagicMock()

        result = {"status": "warning", "reason": "Some drop", "severity": 5}
        assert detector.auto_pause_if_needed(result) is False
        detector.send_alert.assert_called_once()

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_low_severity_no_action(self, mock_client_fn):
        """Severity < 5 → no pause, no alert."""
        from ban_detector import BanDetector

        mock_client_fn.return_value = MagicMock()
        detector = BanDetector("test-page")
        detector.send_alert = MagicMock()

        result = {"status": "ok", "reason": "All good", "severity": 0}
        assert detector.auto_pause_if_needed(result) is False
        detector.send_alert.assert_not_called()


class TestCheckForShadowban:
    """Tests for the full orchestration method."""

    @patch("config.get_supabase_client")
    @patch("config.FACEBOOK_PAGE_ID", "test-page")
    def test_insufficient_data(self, mock_client_fn):
        """Too few posts → ok with 'Insufficient data'."""
        from ban_detector import BanDetector

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        mock_table = MagicMock()
        mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[{"id": "1"}])  # only 1 post
        )
        mock_client.table.return_value = mock_table

        detector = BanDetector("test-page")
        result = detector.check_for_shadowban()

        assert result["status"] == "ok"
        assert "Insufficient" in result["reason"]
