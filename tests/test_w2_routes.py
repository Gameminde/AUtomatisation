"""Regression tests for W2 route cleanup and tenant settings behavior."""

from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

import app.api.routes as api_routes
import app.auth.routes as auth_routes
import app.dashboard.routes as dashboard_routes
import app.settings.routes as settings_routes
import app.utils as app_utils


class FakeUser:
    """Minimal authenticated user stub for route unit tests."""

    def __init__(self, user_id: str = "user-123"):
        self.id = user_id
        self.is_authenticated = True


def test_setup_redirect_endpoint_prefers_dashboard_for_incomplete_user(monkeypatch):
    monkeypatch.setattr(dashboard_routes, "current_user", FakeUser())
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _user_id: {"onboarding_complete": False})

    assert dashboard_routes._setup_redirect_endpoint() == "web.page_dashboard"


def test_setup_redirect_endpoint_prefers_dashboard_for_completed_user(monkeypatch):
    monkeypatch.setattr(dashboard_routes, "current_user", FakeUser())
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _user_id: {"onboarding_complete": True})

    assert dashboard_routes._setup_redirect_endpoint() == "web.page_dashboard"


def test_config_api_keys_saves_supported_values_to_user_settings_only(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    upsert_calls = []

    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "encrypt_value", lambda value: f"enc::{value}")
    monkeypatch.setattr(app_utils, "upsert_user_settings", lambda user_id, updates: upsert_calls.append((user_id, updates)) or True)

    with app.test_request_context(
        "/api/config/api-keys",
        method="POST",
        json={
            "gemini_key": "AIza-test",
            "pexels_key": "pexels-test",
            "facebook_token": "legacy-fb",
            "openrouter_key": "legacy-openrouter",
        },
    ):
        response = settings_routes.config_api_keys()

    payload = response.get_json()
    assert payload["success"] is True
    assert "Facebook page connection is managed via the OAuth flow" in payload["warnings"][0]
    assert upsert_calls == [
        (
            "user-123",
            {
                "ai_provider": "gemini",
                "ai_api_key": "enc::AIza-test",
                "gemini_api_key": "enc::AIza-test",
                "pexels_api_key": "pexels-test",
            },
        )
    ]


def test_config_approval_mode_only_persists_to_user_settings(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    persisted = []

    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "upsert_user_settings", lambda user_id, updates: persisted.append((user_id, updates)) or True)

    with app.test_request_context(
        "/api/config/approval-mode",
        method="POST",
        json={"enabled": True},
    ):
        response = settings_routes.config_approval_mode()

    assert response.get_json() == {"success": True, "enabled": True, "approval_mode": True}
    assert persisted == [("user-123", {"approval_mode": True})]


def test_config_approval_mode_accepts_legacy_approval_mode_key(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    persisted = []

    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "upsert_user_settings", lambda user_id, updates: persisted.append((user_id, updates)) or True)

    with app.test_request_context(
        "/api/config/approval-mode",
        method="POST",
        json={"approval_mode": True},
    ):
        response = settings_routes.config_approval_mode()

    assert response.get_json()["success"] is True
    assert response.get_json()["approval_mode"] is True
    assert persisted == [("user-123", {"approval_mode": True})]


def test_check_setup_uses_user_scoped_db_truth(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()

    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(settings_routes, "current_user", fake_user)
    monkeypatch.setattr(settings_routes, "_has_connected_facebook_page", lambda _user_id: True)
    monkeypatch.setattr(
        app_utils,
        "get_user_settings",
        lambda _user_id: {"gemini_api_key": "enc::AIza", "pexels_api_key": "pexels"},
    )

    with app.test_request_context("/api/setup/check", method="GET"):
        response = settings_routes.check_setup()

    assert response.get_json() == {
        "success": True,
        "complete": True,
        "facebook": True,
        "ai": True,
        "images": True,
        "missing": [],
    }


def test_auth_activate_license_is_public_and_returns_validator_result(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(
        auth_routes,
        "_validate_license_payload",
        lambda data: ({"valid": True, "reason": "ok", "code_id": "code-1"}, 200),
    )

    with app.test_request_context(
        "/auth/activate-license",
        method="POST",
        json={"license_key": "LIC-123"},
    ):
        response, status = auth_routes.activate_license()

    assert status == 200
    assert response.get_json() == {"valid": True, "reason": "ok", "code_id": "code-1"}


def test_api_license_validation_helper_rejects_missing_key():
    payload, status = api_routes._validate_license_request({})

    assert status == 400
    assert payload == {"valid": False, "reason": "No key provided"}
