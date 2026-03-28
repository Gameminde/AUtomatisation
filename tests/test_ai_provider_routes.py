"""Tests for AI provider catalog and key-test settings endpoints."""

from __future__ import annotations

from flask import Flask
from app import create_app

import app.settings.routes as settings_routes
import app.utils as app_utils


class FakeUser:
    def __init__(self, user_id: str = "user-123"):
        self.id = user_id
        self.is_authenticated = True


def test_get_ai_provider_catalog_returns_rich_provider_entries(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()

    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "current_user", fake_user)

    with app.test_request_context("/api/ai/providers", method="GET"):
        response = settings_routes.get_ai_providers_v2()

    payload = response.get_json()
    claude = next(item for item in payload["providers"] if item["id"] == "claude")
    deepseek = next(item for item in payload["providers"] if item["id"] == "deepseek")

    assert claude["default_model"] == "claude-sonnet-4-6"
    assert any(model["recommended"] for model in claude["models"])
    assert deepseek["status"] == "via_openrouter"


def test_ai_test_key_endpoint_returns_plain_result(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()

    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(
        "ai_provider.test_ai_key",
        lambda provider, api_key, model="": {
            "valid": True,
            "provider": provider,
            "model": model or "claude-sonnet-4-6",
            "error": None,
        },
    )

    with app.test_request_context(
        "/api/settings/test-ai",
        method="POST",
        json={
            "provider": "claude",
            "model": "claude-sonnet-4-6",
            "api_key": "sk-ant-test",
        },
    ):
        response = settings_routes.test_ai_key()

    assert response.get_json() == {
        "success": True,
        "valid": True,
        "provider": "claude",
        "model": "claude-sonnet-4-6",
        "error": None,
    }


def test_only_canonical_ai_test_route_is_registered():
    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/api/settings/test-ai" in rules
    assert "/api/ai/test-key" not in rules
    assert "/api/providers/test" not in rules


def test_save_settings_keys_persists_provider_model_and_fallback(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    persisted = []

    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "encrypt_value", lambda value: f"enc::{value}")
    monkeypatch.setattr(
        app_utils,
        "upsert_user_settings",
        lambda user_id, updates: persisted.append((user_id, updates)) or True,
    )

    with app.test_request_context(
        "/api/settings/keys",
        method="POST",
        json={
            "provider": "openrouter",
            "model": "deepseek/deepseek-r1",
            "provider_fallback": "openai",
            "ai_key": "sk-or-test",
        },
    ):
        response = settings_routes.save_settings_keys()

    assert response.get_json()["success"] is True
    assert persisted == [
        (
            "user-123",
            {
                "ai_provider": "openrouter",
                "provider_fallback": "openai",
                "ai_model": "deepseek/deepseek-r1",
                "ai_api_key": "enc::sk-or-test",
                "gemini_api_key": None,
            },
        )
    ]
