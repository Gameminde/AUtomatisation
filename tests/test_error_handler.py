"""
Unit tests for error_handler module.

Tests cover:
- Error classification (rate limit, server, auth, unknown)
- Action execution (cooldown, retry, needs_action)
- Cooldown status checks
- Recent error rate calculation
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone


class TestClassifyError:
    """Tests for classify_error function — the core dispatch logic."""

    def test_rate_limit_hash32(self):
        """Test that Facebook #32 error is classified as COOLDOWN."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("Error #32: Rate limit reached"))
        assert action == ErrorAction.COOLDOWN
        assert code == "RATE_LIMIT"

    def test_rate_limit_429(self):
        """Test that HTTP 429 is classified as COOLDOWN."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("HTTP 429 Too Many Requests"))
        assert action == ErrorAction.COOLDOWN
        assert code == "RATE_LIMIT"

    def test_rate_limit_page_limit(self):
        """Test that 'Page request limit reached' is classified as COOLDOWN."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("Page request limit reached"))
        assert action == ErrorAction.COOLDOWN

    def test_auth_error_401(self):
        """Test that HTTP 401 is classified as NEEDS_ACTION."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("HTTP 401 Unauthorized"))
        assert action == ErrorAction.NEEDS_ACTION
        assert code == "AUTH_ERROR"

    def test_auth_error_oauth(self):
        """Test that OAuthException is classified as NEEDS_ACTION."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("OAuthException: token expired"))
        assert action == ErrorAction.NEEDS_ACTION

    def test_auth_error_permission(self):
        """Test that permission error is classified as NEEDS_ACTION."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("Permission denied for this resource"))
        assert action == ErrorAction.NEEDS_ACTION

    def test_server_error_500(self):
        """Test that HTTP 500 is classified as RETRY."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("HTTP 500 Internal Server Error"))
        assert action == ErrorAction.RETRY
        assert code == "SERVER_ERROR"

    def test_server_error_timeout(self):
        """Test that timeout is classified as RETRY."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("Connection timeout after 30s"))
        assert action == ErrorAction.RETRY

    def test_server_error_503(self):
        """Test that Service Unavailable is classified as RETRY."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("Service Unavailable"))
        assert action == ErrorAction.RETRY

    def test_unknown_error_fallback(self):
        """Test that unknown errors fall back to RETRY with UNKNOWN code."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception("Something completely unexpected happened"))
        assert action == ErrorAction.RETRY
        assert code == "UNKNOWN"

    def test_empty_error(self):
        """Test classification of empty error message."""
        from error_handler import classify_error, ErrorAction

        action, code = classify_error(Exception(""))
        assert action == ErrorAction.RETRY
        assert code == "UNKNOWN"

    def test_rate_limit_takes_precedence_over_server_error(self):
        """Rate limit (#32) should take priority over server patterns."""
        from error_handler import classify_error, ErrorAction

        # Contains both rate limit and server error indicators
        action, _ = classify_error(Exception("#32: Rate limit - 500 Internal Server Error"))
        assert action == ErrorAction.COOLDOWN


class TestExecuteAction:
    """Tests for execute_action — DB side-effects."""

    @patch("error_handler.database")
    def test_cooldown_action_returns_false(self, mock_db_module):
        """Cooldown should return False (don't retry immediately)."""
        from error_handler import execute_action, ErrorAction

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
        mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)
        mock_db.table.return_value = mock_table

        result = execute_action(ErrorAction.COOLDOWN, "test-id", "RATE_LIMIT")
        assert result is False

    @patch("error_handler.database")
    def test_retry_action_under_max(self, mock_db_module):
        """Retry under max should return True."""
        from error_handler import execute_action, ErrorAction

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value = mock_table

        result = execute_action(ErrorAction.RETRY, "test-id", "SERVER_ERROR", retry_count=0)
        assert result is True

    @patch("error_handler.database")
    def test_retry_action_at_max(self, mock_db_module):
        """Retry at max attempts should return False (give up)."""
        from error_handler import execute_action, ErrorAction

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value = mock_table

        result = execute_action(ErrorAction.RETRY, "test-id", "SERVER_ERROR", retry_count=3)
        assert result is False

    @patch("error_handler.database")
    def test_needs_action_returns_false(self, mock_db_module):
        """NEEDS_ACTION should return False (no auto-retry)."""
        from error_handler import execute_action, ErrorAction

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db
        mock_table = MagicMock()
        mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value = mock_table

        result = execute_action(ErrorAction.NEEDS_ACTION, "test-id", "AUTH_ERROR")
        assert result is False


class TestIsInCooldown:
    """Tests for is_in_cooldown — system cooldown check."""

    @patch("error_handler.database")
    def test_active_cooldown(self, mock_db_module):
        """Should return True when cooldown is in the future."""
        from error_handler import is_in_cooldown

        future = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data={"value": future})
        )
        mock_db.table.return_value = mock_table

        assert is_in_cooldown() is True

    @patch("error_handler.database")
    def test_expired_cooldown(self, mock_db_module):
        """Should return False when cooldown is in the past."""
        from error_handler import is_in_cooldown

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data={"value": past})
        )
        mock_db.table.return_value = mock_table

        assert is_in_cooldown() is False

    @patch("error_handler.database")
    def test_no_cooldown_record(self, mock_db_module):
        """Should return False when no cooldown record exists."""
        from error_handler import is_in_cooldown

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            MagicMock(data=None)
        )
        mock_db.table.return_value = mock_table

        assert is_in_cooldown() is False


class TestGetRecentErrorRate:
    """Tests for get_recent_error_rate — error rate calculation."""

    @patch("error_handler.database")
    def test_zero_posts_returns_zero(self, mock_db_module):
        """No posts at all → 0% error rate."""
        from error_handler import get_recent_error_rate

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db
        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.gte.return_value.execute.return_value = (
            MagicMock(count=0)
        )
        mock_db.table.return_value = mock_table

        assert get_recent_error_rate() == 0.0

    @patch("error_handler.database")
    def test_all_failures_returns_one(self, mock_db_module):
        """All failed, none published → 100% error rate."""
        from error_handler import get_recent_error_rate

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db

        # First call = failed count, second call = success count
        failed_result = MagicMock(count=5)
        success_result = MagicMock(count=0)

        mock_table = MagicMock()
        mock_table.select.return_value.eq.return_value.gte.return_value.execute.side_effect = [
            failed_result,
            success_result,
        ]
        mock_db.table.return_value = mock_table

        assert get_recent_error_rate() == 1.0

    @patch("error_handler.database")
    def test_db_exception_returns_zero(self, mock_db_module):
        """Database error should return 0.0 (safe default)."""
        from error_handler import get_recent_error_rate

        mock_db = MagicMock()
        mock_db_module.get_db.return_value = mock_db
        mock_db.table.side_effect = Exception("DB connection lost")

        assert get_recent_error_rate() == 0.0
