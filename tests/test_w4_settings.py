"""Tests for W4 settings readiness logic."""

from __future__ import annotations

from flask import Flask

import app.settings.routes as settings_routes
import app.utils as app_utils


class FakeUser:
    """Minimal authenticated user stub for settings route tests."""

    def __init__(self, user_id: str = "user-123"):
        self.id = user_id
        self.is_authenticated = True


def test_get_user_setup_status_uses_db_truth_not_env(monkeypatch):
    monkeypatch.setenv("FACEBOOK_ACCESS_TOKEN", "legacy-global-token")
    monkeypatch.setenv("GEMINI_API_KEY", "legacy-global-gemini")
    monkeypatch.setenv("PEXELS_API_KEY", "legacy-global-pexels")

    monkeypatch.setattr(settings_routes, "_has_connected_facebook_page", lambda _uid: False)
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {})

    payload = settings_routes._get_user_setup_status("user-123")

    assert payload == {
        "complete": False,
        "facebook": False,
        "ai": False,
        "images": False,
        "missing": ["facebook", "ai", "images"],
    }


def test_config_api_keys_get_returns_db_scoped_completion(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()

    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(settings_routes, "_has_connected_facebook_page", lambda _uid: True)
    monkeypatch.setattr(
        app_utils,
        "get_user_settings",
        lambda _uid: {"gemini_api_key": "enc::key", "pexels_api_key": "pexels"},
    )

    with app.test_request_context("/api/config/api-keys", method="GET"):
        response = settings_routes.config_api_keys()

    assert response.get_json() == {
        "facebook": True,
        "gemini": True,
        "openrouter": False,
        "pexels": True,
        "complete": True,
        "missing": [],
    }
