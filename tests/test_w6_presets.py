"""Tests for W6 locale-aware scraping and preset endpoints."""

from __future__ import annotations

from flask import Flask

import app.onboarding.routes as onboarding_routes
import app.settings.routes as settings_routes
import app.utils as app_utils


class FakeUser:
    """Minimal authenticated user stub for route unit tests."""

    def __init__(self, user_id: str = "user-123"):
        self.id = user_id
        self.is_authenticated = True


def test_settings_apply_preset_persists_country_and_niche(monkeypatch):
    app = Flask(__name__)
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
        lambda _uid: {"country_code": "AE", "content_language": "ar"},
    )

    with app.test_request_context(
        "/api/settings/presets/apply",
        method="POST",
        json={"country_code": "ae", "niche_preset": "creator"},
    ):
        response = settings_routes.apply_settings_preset()

    assert response.get_json() == {
        "success": True,
        "profile": {"country_code": "AE", "content_language": "ar"},
    }
    assert persisted[0][0] == "user-123"
    assert persisted[0][1]["country_code"] == "AE"
    assert persisted[0][1]["source_preset"] == "AE"
    assert persisted[0][1]["niche_preset"] == "creator"
    assert "content creator" in persisted[0][1]["niche_keywords"]


def test_onboarding_presets_get_exposes_country_and_niche_catalog(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    monkeypatch.setattr(onboarding_routes, "current_user", fake_user)

    with app.test_request_context("/onboarding/presets", method="GET"):
        response = onboarding_routes.onboarding_presets.__wrapped__()

    payload = response.get_json()
    assert payload["ok"] is True
    assert any(country["country_code"] == "US" for country in payload["countries"])
    assert any(country["country_code"] == "FR" for country in payload["countries"])
    assert any(country["country_code"] == "AE" for country in payload["countries"])
    assert any(country["country_code"] == "OTHER" for country in payload["countries"])
    assert any(niche["id"] == "creator" for niche in payload["niches"])
