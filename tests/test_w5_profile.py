"""Tests for W5 locale/profile and AI-provider prep work."""

from __future__ import annotations

from flask import Flask, session

import app.auth.routes as auth_routes
import app.onboarding.routes as onboarding_routes
import app.settings.routes as settings_routes
import app.utils as app_utils
import config


class FakeUser:
    """Minimal authenticated user stub for route unit tests."""

    def __init__(self, user_id: str = "user-123"):
        self.id = user_id
        self.is_authenticated = True


def test_user_config_from_db_loads_locale_and_ai_profile(monkeypatch):
    from user_config import UserConfig

    monkeypatch.setattr(
        app_utils,
        "load_tokens_for_user",
        lambda _uid: {
            "page_id": "page-1",
            "page_token": "fb-token",
            "instagram_account_id": "ig-1",
            "posts_per_day": None,
            "posting_times": None,
            "page_language": "fr",
        },
    )
    monkeypatch.setattr(
        app_utils,
        "get_user_settings",
        lambda _uid: {
            "country_code": "FR",
            "timezone": "Europe/Paris",
            "ui_language": "fr",
            "content_language": "fr",
            "content_languages": "fr,en",
            "content_tone": "educational",
            "content_mode": "mixed",
            "ai_provider": "openrouter",
            "ai_model": "openai/gpt-4o-mini",
            "language_ratio": 0.4,
            "telegram_chat_id": "tg-1",
            "niche_keywords": "saas,creator",
        },
    )
    monkeypatch.setattr(app_utils, "get_ai_key_for_user", lambda _uid: "provider-key")
    monkeypatch.setattr(app_utils, "get_gemini_key_for_user", lambda _uid: "")

    user_config = UserConfig.from_db("user-123")

    assert user_config.ai_provider == "openrouter"
    assert user_config.ai_model == "openai/gpt-4o-mini"
    assert user_config.ai_api_key == "provider-key"
    assert user_config.country_code == "FR"
    assert user_config.timezone == "Europe/Paris"
    assert user_config.ui_language == "fr"
    assert user_config.content_language == "fr"
    assert user_config.content_languages == ["fr", "en"]
    assert user_config.content_tone == "educational"
    assert user_config.content_mode == "mixed"
    assert user_config.posting_times == config.TARGET_POSTING_PRESETS["FR"]["posting_times"]


def test_user_config_from_db_falls_back_to_country_preset(monkeypatch):
    from user_config import UserConfig

    monkeypatch.setattr(app_utils, "load_tokens_for_user", lambda _uid: {})
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {})
    monkeypatch.setattr(app_utils, "get_ai_key_for_user", lambda _uid: "")
    monkeypatch.setattr(app_utils, "get_gemini_key_for_user", lambda _uid: "")

    user_config = UserConfig.from_db("user-123")
    preset = config.TARGET_POSTING_PRESETS[config.DEFAULT_COUNTRY_CODE]

    assert user_config.country_code == config.DEFAULT_COUNTRY_CODE
    assert user_config.timezone == preset["timezone"]
    assert user_config.posting_times == preset["posting_times"]
    assert user_config.posts_per_day == 3


def test_settings_profile_post_persists_locale_and_ai_fields(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    fake_user = FakeUser()
    persisted = []

    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(
        app_utils,
        "upsert_user_settings",
        lambda user_id, updates: persisted.append((user_id, updates)) or True,
    )
    monkeypatch.setattr(
        settings_routes,
        "_serialize_user_profile",
        lambda _uid: {
            "country_code": "AE",
            "timezone": "Asia/Dubai",
            "ui_language": "fr",
            "content_language": "en",
            "content_languages": ["en", "ar"],
            "content_tone": "professional",
            "content_mode": "mixed",
            "ai_provider": "openrouter",
            "ai_model": "openai/gpt-4o-mini",
            "posts_per_day": 3,
            "posting_times": config.TARGET_POSTING_PRESETS["AE"]["posting_times"],
        },
    )

    with app.test_request_context(
        "/api/settings/profile",
        method="POST",
        json={
            "country_code": "ae",
            "ui_language": "fr",
            "content_language": "en",
            "content_languages": ["en", "ar"],
            "content_tone": "professional",
            "content_mode": "mixed",
            "ai_provider": "openrouter",
            "ai_model": "openai/gpt-4o-mini",
        },
    ):
        response = settings_routes.settings_profile()

    assert response.get_json()["success"] is True
    assert persisted == [
        (
            "user-123",
            {
                "country_code": "AE",
                "timezone": "Asia/Dubai",
                "ui_language": "fr",
                "content_language": "en",
                "content_languages": "en,ar",
                "content_tone": "professional",
                "content_mode": "mixed",
                "ai_provider": "openrouter",
                "ai_model": "openai/gpt-4o-mini",
            },
        )
    ]


def test_settings_profile_post_stores_ui_language_in_session(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    fake_user = FakeUser()

    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "upsert_user_settings", lambda _uid, _updates: True)
    monkeypatch.setattr(
        settings_routes,
        "_serialize_user_profile",
        lambda _uid: {"ui_language": "fr", "country_code": "AE"},
    )

    with app.test_request_context("/api/settings/profile", method="POST", json={"ui_language": "fr"}):
        response = settings_routes.settings_profile()
        assert session["ui_language"] == "FR"

    assert response.get_json()["profile"]["ui_language"] == "fr"


def test_settings_profile_post_returns_500_when_persist_fails(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    fake_user = FakeUser()

    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "upsert_user_settings", lambda _uid, _updates: False)

    with app.test_request_context("/api/settings/profile", method="POST", json={"ui_language": "fr"}):
        response, status = settings_routes.settings_profile()

    assert status == 500
    assert response.get_json()["success"] is False


def test_upsert_user_settings_retries_without_unknown_column(monkeypatch):
    calls = []

    class FakeExecute:
        def execute(self):
            calls.append(dict(self.payload))
            if len(calls) == 1:
                raise Exception("Could not find the 'ui_language' column of 'user_settings' in the schema cache")
            return {"data": [self.payload]}

        def __init__(self, payload):
            self.payload = payload

    class FakeTable:
        def upsert(self, payload, on_conflict="user_id"):
            return FakeExecute(payload)

    class FakeSupabase:
        def table(self, _name):
            return FakeTable()

    monkeypatch.setattr(app_utils, "_get_supabase_client", lambda: FakeSupabase())

    ok = app_utils.upsert_user_settings("user-123", {"ui_language": "fr", "content_language": "en"})

    assert ok is True
    assert calls == [
        {"user_id": "user-123", "ui_language": "fr", "content_language": "en"},
        {"user_id": "user-123", "content_language": "en"},
    ]


def test_onboarding_profile_route_returns_resolved_profile(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    fake_user = FakeUser()

    monkeypatch.setattr(onboarding_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {"ui_language": "en"})
    monkeypatch.setattr(
        onboarding_routes,
        "_serialize_profile",
        lambda _uid: {
            "country_code": "US",
            "timezone": "America/New_York",
            "ui_language": "en",
            "content_language": "en",
            "content_languages": ["en"],
            "content_tone": "casual",
            "content_mode": "mixed",
            "ai_provider": "gemini",
            "ai_model": "gemini-2.5-flash",
        },
    )

    with app.test_request_context("/onboarding/profile", method="GET"):
        response = onboarding_routes.save_profile.__wrapped__()

    assert response.get_json() == {
        "ok": True,
        "profile": {
            "country_code": "US",
            "timezone": "America/New_York",
            "ui_language": "en",
            "content_language": "en",
            "content_languages": ["en"],
            "content_tone": "casual",
            "content_mode": "mixed",
            "ai_provider": "gemini",
            "ai_model": "gemini-2.5-flash",
        },
    }


def test_onboarding_profile_post_returns_500_when_persist_fails(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    fake_user = FakeUser()

    monkeypatch.setattr(onboarding_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "upsert_user_settings", lambda _uid, _updates: False)

    with app.test_request_context("/onboarding/profile", method="POST", json={"ui_language": "fr"}):
        response, status = onboarding_routes.save_profile.__wrapped__()

    assert status == 500
    assert response.get_json()["ok"] is False


def test_login_seeds_session_ui_language(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    fake_guest = type("Guest", (), {"is_authenticated": False})()

    mock_client = type("Supabase", (), {})()
    mock_table = type("Table", (), {})()

    def _select(*_args, **_kwargs):
        return mock_table

    def _eq(*_args, **_kwargs):
        return mock_table

    def _execute():
        return type(
            "Result",
            (),
            {"data": [{"id": "user-123", "email": "test@example.com", "password_hash": "hash", "is_active": True}]},
        )()

    mock_table.select = _select
    mock_table.eq = _eq
    mock_table.execute = _execute
    mock_client.table = lambda _name: mock_table

    monkeypatch.setattr(auth_routes, "current_user", fake_guest, raising=False)
    monkeypatch.setattr(auth_routes, "_get_supabase", lambda: mock_client)
    monkeypatch.setattr(auth_routes, "login_user", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_routes, "url_for", lambda _endpoint: "/dashboard")
    monkeypatch.setattr("bcrypt.checkpw", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {"ui_language": "ar"})

    with app.test_request_context(
        "/auth/login",
        method="POST",
        data={"email": "test@example.com", "password": "secret"},
    ):
        response = auth_routes.login()
        assert session["ui_language"] == "AR"

    assert response.status_code == 302
