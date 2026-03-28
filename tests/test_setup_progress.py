"""Tests for the dashboard-native setup progress endpoint."""

from __future__ import annotations

from flask import Flask

import app.api.routes as api_routes
import app.utils as app_utils


class FakeUser:
    def __init__(self, user_id: str = "user-123"):
        self.id = user_id
        self.is_authenticated = True


class FakeResult:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def execute(self):
        matched = [
            row for row in self._rows
            if all(row.get(key) == value for key, value in self._filters)
        ]
        return FakeResult(data=matched, count=len(matched))


class FakeDBClient:
    def __init__(self, table_rows):
        self._table_rows = table_rows

    def table(self, name: str):
        return FakeQuery(self._table_rows.get(name, []))


def _patch_auth(monkeypatch, user_id="user-123"):
    fake_user = FakeUser(user_id)
    monkeypatch.setattr(api_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "current_user", fake_user)
    return fake_user


def _call_setup_progress(app):
    with app.test_request_context("/api/setup/progress", method="GET"):
        return api_routes.get_setup_progress().get_json()


def test_setup_progress_for_new_user(monkeypatch):
    app = Flask(__name__)
    _patch_auth(monkeypatch)
    monkeypatch.setattr(api_routes.config, "get_database_client", lambda: FakeDBClient({}))
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {})

    payload = _call_setup_progress(app)

    assert payload["all_required_complete"] is False
    assert payload["next_required_step"] == "facebook"
    assert [step["completed"] for step in payload["steps"]] == [False, False, False]


def test_setup_progress_for_user_with_only_facebook(monkeypatch):
    app = Flask(__name__)
    fake_user = _patch_auth(monkeypatch)
    monkeypatch.setattr(
        api_routes.config,
        "get_database_client",
        lambda: FakeDBClient(
            {
                "managed_pages": [{"id": "page-1", "user_id": fake_user.id, "status": "active"}],
            }
        ),
    )
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {})

    payload = _call_setup_progress(app)

    assert payload["all_required_complete"] is False
    assert payload["next_required_step"] == "ai_key"
    assert payload["steps"][0]["completed"] is True
    assert payload["steps"][1]["completed"] is False
    assert payload["steps"][2]["completed"] is False


def test_setup_progress_for_user_with_facebook_and_ai(monkeypatch):
    app = Flask(__name__)
    fake_user = _patch_auth(monkeypatch)
    monkeypatch.setattr(
        api_routes.config,
        "get_database_client",
        lambda: FakeDBClient(
            {
                "managed_pages": [{"id": "page-1", "user_id": fake_user.id, "status": "active"}],
            }
        ),
    )
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {"ai_api_key": "enc::key"})

    payload = _call_setup_progress(app)

    assert payload["all_required_complete"] is True
    assert payload["next_required_step"] is None
    assert payload["steps"][0]["completed"] is True
    assert payload["steps"][1]["completed"] is True
    assert payload["steps"][2]["completed"] is False


def test_setup_progress_for_fully_configured_user(monkeypatch):
    app = Flask(__name__)
    fake_user = _patch_auth(monkeypatch)
    monkeypatch.setattr(
        api_routes.config,
        "get_database_client",
        lambda: FakeDBClient(
            {
                "managed_pages": [{"id": "page-1", "user_id": fake_user.id, "status": "active"}],
                "telegram_connections": [{"user_id": fake_user.id, "is_active": True}],
            }
        ),
    )
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {"ai_api_key": "enc::key"})

    payload = _call_setup_progress(app)

    assert payload["all_required_complete"] is True
    assert payload["next_required_step"] is None
    assert [step["completed"] for step in payload["steps"]] == [True, True, True]
