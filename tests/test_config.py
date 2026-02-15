"""
Unit tests for config module.

Tests cover:
- Environment variable loading
- Supabase client creation
- Logger configuration
- Log statistics
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestRequireEnv:
    """Tests for require_env function."""

    def test_require_env_exists(self, monkeypatch):
        """Test requiring existing env var."""
        from config import require_env

        monkeypatch.setenv("TEST_VAR", "test_value")

        result = require_env("TEST_VAR")

        assert result == "test_value"

    def test_require_env_missing(self, monkeypatch):
        """Test requiring missing env var."""
        from config import require_env

        monkeypatch.delenv("MISSING_VAR", raising=False)

        with pytest.raises(RuntimeError, match="Missing required env var"):
            require_env("MISSING_VAR")

    def test_require_env_empty(self, monkeypatch):
        """Test requiring empty env var."""
        from config import require_env

        monkeypatch.setenv("EMPTY_VAR", "")

        with pytest.raises(RuntimeError):
            require_env("EMPTY_VAR")


class TestGetEnv:
    """Tests for get_env function."""

    def test_get_env_exists(self, monkeypatch):
        """Test getting existing env var."""
        from config import get_env

        monkeypatch.setenv("TEST_VAR", "test_value")

        result = get_env("TEST_VAR")

        assert result == "test_value"

    def test_get_env_default(self, monkeypatch):
        """Test getting missing env var with default."""
        from config import get_env

        monkeypatch.delenv("MISSING_VAR", raising=False)

        result = get_env("MISSING_VAR", "default_value")

        assert result == "default_value"

    def test_get_env_none(self, monkeypatch):
        """Test getting missing env var without default."""
        from config import get_env

        monkeypatch.delenv("MISSING_VAR", raising=False)

        result = get_env("MISSING_VAR")

        assert result is None


class TestGetSupabaseClient:
    """Tests for get_supabase_client function."""

    @patch("supabase.create_client")
    def test_get_supabase_client_success(self, mock_create, monkeypatch):
        """Test successful client creation."""
        from config import get_supabase_client

        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "test-key")

        mock_client = MagicMock()
        mock_create.return_value = mock_client

        _ = get_supabase_client()  # Result not used, just testing creation

        mock_create.assert_called_once_with("https://test.supabase.co", "test-key")

    def test_get_supabase_client_missing_url(self, monkeypatch):
        """Test client creation with missing URL."""
        # Clear SUPABASE_URL env var - require_env reads from os.getenv directly
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.setenv("SUPABASE_KEY", "test-key")

        from config import get_supabase_client

        with pytest.raises(RuntimeError, match="Missing required env var"):
            get_supabase_client()


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger."""
        from config import get_logger
        import logging

        logger = get_logger("test_module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_same_instance(self):
        """Test that same logger is returned for same name."""
        from config import get_logger

        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")

        assert logger1 is logger2

    def test_get_logger_has_handlers(self):
        """Test that logger has handlers configured."""
        from config import get_logger

        logger = get_logger("handler_test")

        assert len(logger.handlers) > 0


class TestDefaultKeywords:
    """Tests for DEFAULT_KEYWORDS constant."""

    def test_default_keywords_exist(self):
        """Test that default keywords are defined."""
        from config import DEFAULT_KEYWORDS

        assert isinstance(DEFAULT_KEYWORDS, list)
        assert len(DEFAULT_KEYWORDS) > 0

    def test_default_keywords_contain_tech_terms(self):
        """Test that keywords contain tech-related terms."""
        from config import DEFAULT_KEYWORDS

        assert "ai" in DEFAULT_KEYWORDS
        assert "blockchain" in DEFAULT_KEYWORDS


class TestTargetTimezones:
    """Tests for TARGET_TIMEZONES constant."""

    def test_target_timezones_exist(self):
        """Test that target timezones are defined."""
        from config import TARGET_TIMEZONES

        assert isinstance(TARGET_TIMEZONES, dict)

    def test_target_timezones_keys(self):
        """Test that expected timezone keys exist."""
        from config import TARGET_TIMEZONES

        assert "US_EST" in TARGET_TIMEZONES
        assert "US_PST" in TARGET_TIMEZONES
        assert "UK_GMT" in TARGET_TIMEZONES

    def test_target_timezones_values_valid(self):
        """Test that timezone values are valid."""
        from config import TARGET_TIMEZONES
        from zoneinfo import ZoneInfo

        for key, value in TARGET_TIMEZONES.items():
            # This will raise if timezone is invalid
            tz = ZoneInfo(value)
            assert tz is not None


class TestLogStats:
    """Tests for log_stats function."""

    def test_log_stats_returns_dict(self):
        """Test that log_stats returns a dictionary."""
        from config import log_stats

        stats = log_stats()

        assert isinstance(stats, dict)
        assert "total_errors" in stats
        assert "total_warnings" in stats
        assert "total_info" in stats
        assert "modules" in stats

    def test_log_stats_modules_is_dict(self):
        """Test that modules is a dictionary."""
        from config import log_stats

        stats = log_stats()

        assert isinstance(stats["modules"], dict)


class TestConstants:
    """Tests for module constants."""

    def test_http_timeout_is_number(self):
        """Test HTTP timeout is a number."""
        from config import HTTP_TIMEOUT_SECONDS

        assert isinstance(HTTP_TIMEOUT_SECONDS, (int, float))
        assert HTTP_TIMEOUT_SECONDS > 0

    def test_request_sleep_is_number(self):
        """Test request sleep is a number."""
        from config import REQUEST_SLEEP_SECONDS

        assert isinstance(REQUEST_SLEEP_SECONDS, (int, float))
        assert REQUEST_SLEEP_SECONDS >= 0

    def test_log_dir_exists(self):
        """Test that LOG_DIR is defined."""
        from config import LOG_DIR

        assert isinstance(LOG_DIR, Path)
