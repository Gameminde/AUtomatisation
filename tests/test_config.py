"""Unit tests for config module."""

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRequireEnv:
    """Tests for require_env function."""

    def test_require_env_exists(self, monkeypatch):
        from config import require_env

        monkeypatch.setenv("TEST_VAR", "test_value")
        assert require_env("TEST_VAR") == "test_value"

    def test_require_env_missing(self, monkeypatch):
        from config import require_env

        monkeypatch.delenv("MISSING_VAR", raising=False)
        with pytest.raises(RuntimeError, match="Missing required env var"):
            require_env("MISSING_VAR")

    def test_require_env_empty(self, monkeypatch):
        from config import require_env

        monkeypatch.setenv("EMPTY_VAR", "")
        with pytest.raises(RuntimeError):
            require_env("EMPTY_VAR")


class TestGetEnv:
    """Tests for get_env function."""

    def test_get_env_exists(self, monkeypatch):
        from config import get_env

        monkeypatch.setenv("TEST_VAR", "test_value")
        assert get_env("TEST_VAR") == "test_value"

    def test_get_env_default(self, monkeypatch):
        from config import get_env

        monkeypatch.delenv("MISSING_VAR", raising=False)
        assert get_env("MISSING_VAR", "default_value") == "default_value"

    def test_get_env_none(self, monkeypatch):
        from config import get_env

        monkeypatch.delenv("MISSING_VAR", raising=False)
        assert get_env("MISSING_VAR") is None


class TestDatabaseClientContract:
    """Tests for the split database/Supabase helpers."""

    @patch("database.get_db")
    def test_get_database_client_delegates_to_database_layer(self, mock_get_db):
        from config import get_database_client

        marker = object()
        mock_get_db.return_value = marker

        assert get_database_client() is marker

    @patch("config.get_database_client")
    def test_get_supabase_client_is_compat_alias(self, mock_get_database_client):
        from config import get_supabase_client

        marker = object()
        mock_get_database_client.return_value = marker

        assert get_supabase_client() is marker
        mock_get_database_client.assert_called_once_with()

    @patch("supabase.create_client")
    def test_get_supabase_service_client_success(self, mock_create, monkeypatch):
        from config import get_supabase_service_client
        from supabase.lib.client_options import SyncClientOptions

        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "test-key")

        marker = object()
        mock_create.return_value = marker

        assert get_supabase_service_client() is marker
        mock_create.assert_called_once()
        args, kwargs = mock_create.call_args
        assert args == ("https://test.supabase.co", "test-key")
        assert isinstance(kwargs.get("options"), SyncClientOptions)

    def test_get_supabase_service_client_missing_url(self, monkeypatch):
        from config import get_supabase_service_client

        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.setenv("SUPABASE_KEY", "test-key")

        with pytest.raises(RuntimeError, match="Missing required env var: SUPABASE_URL"):
            get_supabase_service_client()

    def test_get_supabase_service_client_missing_key(self, monkeypatch):
        from config import get_supabase_service_client

        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.delenv("SUPABASE_KEY", raising=False)

        with pytest.raises(RuntimeError, match="Missing required env var: SUPABASE_KEY"):
            get_supabase_service_client()

    @patch("database.get_db")
    def test_get_database_client_can_return_sqlite_adapter(self, mock_get_db):
        from config import get_database_client

        sqlite_db = MagicMock()
        sqlite_db.__class__.__name__ = "SQLiteDB"
        mock_get_db.return_value = sqlite_db

        result = get_database_client()

        assert result.__class__.__name__ == "SQLiteDB"

    @patch("database.get_db")
    def test_get_database_client_can_return_supabase_wrapper(self, mock_get_db):
        from config import get_database_client

        wrapper = MagicMock()
        wrapper.__class__.__name__ = "SupabaseWrapper"
        mock_get_db.return_value = wrapper

        result = get_database_client()

        assert result.__class__.__name__ == "SupabaseWrapper"


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        from config import get_logger
        import logging

        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_same_instance(self):
        from config import get_logger

        logger1 = get_logger("same_module")
        logger2 = get_logger("same_module")

        assert logger1 is logger2

    def test_get_logger_has_handlers(self):
        from config import get_logger

        logger = get_logger("handler_test")
        assert len(logger.handlers) > 0


class TestLoadEnv:
    """Tests for load_env helper."""

    @patch("config.load_dotenv")
    def test_load_env_without_override(self, mock_load_dotenv):
        from config import load_env

        load_env()
        mock_load_dotenv.assert_called_once_with(override=False)

    @patch("config.load_dotenv")
    def test_load_env_with_override(self, mock_load_dotenv):
        from config import load_env

        load_env(override=True)
        mock_load_dotenv.assert_called_once_with(override=True)


class TestDefaultKeywords:
    """Tests for DEFAULT_KEYWORDS constant."""

    def test_default_keywords_exist(self):
        from config import DEFAULT_KEYWORDS

        assert isinstance(DEFAULT_KEYWORDS, list)
        assert len(DEFAULT_KEYWORDS) > 0

    def test_default_keywords_contain_tech_terms(self):
        from config import DEFAULT_KEYWORDS

        assert "ai" in DEFAULT_KEYWORDS
        assert "blockchain" in DEFAULT_KEYWORDS


class TestTargetTimezones:
    """Tests for TARGET_TIMEZONES constant."""

    def test_target_timezones_exist(self):
        from config import TARGET_TIMEZONES

        assert isinstance(TARGET_TIMEZONES, dict)

    def test_target_timezones_keys(self):
        from config import TARGET_TIMEZONES

        assert "US" in TARGET_TIMEZONES
        assert "UK" in TARGET_TIMEZONES
        assert "FR" in TARGET_TIMEZONES
        assert "DE" in TARGET_TIMEZONES
        assert "AE" in TARGET_TIMEZONES
        assert "SA" in TARGET_TIMEZONES
        assert "QA" in TARGET_TIMEZONES
        assert "KW" in TARGET_TIMEZONES
        assert "OTHER" in TARGET_TIMEZONES

    def test_target_timezones_values_valid(self):
        from config import TARGET_TIMEZONES
        from zoneinfo import ZoneInfo

        for value in TARGET_TIMEZONES.values():
            assert ZoneInfo(value) is not None

    def test_static_presets_load_lazily(self):
        config_path = Path(__file__).resolve().parents[1] / "config.py"
        spec = importlib.util.spec_from_file_location("_config_lazy_probe", config_path)
        assert spec and spec.loader

        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)

        assert "TARGET_TIMEZONES" not in config_module.__dict__
        assert "TARGET_POSTING_PRESETS" not in config_module.__dict__
        assert config_module.STATIC_PRESETS_PATH.exists()

        presets = config_module.TARGET_POSTING_PRESETS

        assert "TARGET_POSTING_PRESETS" in config_module.__dict__
        assert presets["OTHER"]["timezone"] == "UTC"


class TestLogStats:
    """Tests for log_stats function."""

    def test_log_stats_returns_dict(self):
        from config import log_stats

        stats = log_stats()
        assert isinstance(stats, dict)
        assert "total_errors" in stats
        assert "total_warnings" in stats
        assert "total_info" in stats
        assert "modules" in stats

    def test_log_stats_modules_is_dict(self):
        from config import log_stats

        assert isinstance(log_stats()["modules"], dict)


class TestConstants:
    """Tests for module constants."""

    def test_http_timeout_is_number(self):
        from config import HTTP_TIMEOUT_SECONDS

        assert isinstance(HTTP_TIMEOUT_SECONDS, (int, float))
        assert HTTP_TIMEOUT_SECONDS > 0

    def test_request_sleep_is_number(self):
        from config import REQUEST_SLEEP_SECONDS

        assert isinstance(REQUEST_SLEEP_SECONDS, (int, float))
        assert REQUEST_SLEEP_SECONDS >= 0

    def test_log_dir_exists(self):
        from config import LOG_DIR

        assert isinstance(LOG_DIR, Path)
