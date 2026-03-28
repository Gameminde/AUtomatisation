"""Tests for real health status, events, and diagnostics endpoints."""

from __future__ import annotations

from flask import Flask

import app.api.routes as api_routes
import app.utils as app_utils


class FakeUser:
    """Minimal authenticated user stub for API route tests."""

    def __init__(self, user_id: str = "user-123"):
        self.id = user_id
        self.is_authenticated = True


class FakeResult:
    """Minimal Supabase-like result object."""

    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class FakeQuery:
    """Chainable query stub that pops pre-seeded execute() results."""

    def __init__(self, queue):
        self._queue = queue

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def lte(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if not self._queue:
            return FakeResult()
        next_item = self._queue.pop(0)
        return FakeResult(data=next_item.get("data"), count=next_item.get("count"))


class FakeDBClient:
    """Table-dispatching fake DB client with per-table response queues."""

    def __init__(self, responses):
        self.responses = {name: list(items) for name, items in responses.items()}

    def table(self, name: str):
        return FakeQuery(self.responses.setdefault(name, []))


def _patch_authenticated_user(monkeypatch):
    fake_user = FakeUser()
    monkeypatch.setattr(api_routes, "current_user", fake_user)
    monkeypatch.setattr(app_utils, "current_user", fake_user)
    return fake_user


def test_load_health_status_payload_uses_real_tenant_data(monkeypatch):
    fake_db = FakeDBClient({
        "processed_content": [
            {"data": [{
                "status": "retry_scheduled",
                "last_error": "SERVER_ERROR",
                "last_error_at": "2026-03-22T08:00:00+00:00",
                "retry_count": 2,
                "next_retry_at": "2099-01-01T09:00:00+00:00",
            }]},
            {"count": 2},
            {"count": 1},
            {"count": 3},
            {"count": 0},
        ],
        "scheduled_posts": [
            {"data": [{"scheduled_time": "2026-03-22T12:00:00+00:00"}]},
            {"count": 5},
        ],
        "published_posts": [
            {"data": [{"published_at": "2026-03-21T10:00:00+00:00"}]},
            {"count": 4},
        ],
    })
    monkeypatch.setattr(api_routes.config, "get_database_client", lambda: fake_db)
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {"gemini_api_key": "enc", "pexels_api_key": "pexels"})
    monkeypatch.setattr(app_utils, "get_active_page_health", lambda _uid: {
        "connected": True,
        "page_id": "123",
        "page_name": "My Page",
        "status": "active",
        "instagram_connected": True,
        "token_expires_at": "2026-04-01T00:00:00+00:00",
        "token_status": "healthy",
        "token_expired": False,
        "token_days_remaining": 10.0,
        "connected_at": "2026-03-01T00:00:00+00:00",
    })

    payload = api_routes._load_health_status_payload("user-123")

    assert payload["tokens"]["facebook"] is True
    assert payload["tokens"]["ai"] is True
    assert payload["tokens"]["ai_source"] == "user_settings"
    assert payload["ai_source"] == "user_settings"
    assert payload["tokens"]["pexels"] is True
    assert payload["page"]["page_name"] == "My Page"
    assert payload["tokens"]["facebook_page_name"] == "My Page"
    assert payload["cooldown"]["active"] is True
    assert payload["pipeline"]["queue_size"] == 5
    assert payload["pipeline"]["retry_scheduled_count"] == 2
    assert payload["pipeline"]["failed_count"] == 1
    assert payload["pipeline"]["pending_approvals"] == 3
    assert payload["pipeline"]["published_count_7d"] == 4
    assert payload["last_error"]["message"] == "SERVER_ERROR — retry queued"


def test_build_health_events_sorts_real_activity_and_adds_token_warning():
    events = api_routes._build_health_events(
        page_health={
            "connected": True,
            "token_status": "expiring",
            "token_expires_at": "2026-03-23T09:00:00+00:00",
        },
        recent_rows={
            "published": [{"published_at": "2026-03-22T10:00:00+00:00", "platforms": "facebook,instagram"}],
            "scheduled": [{"created_at": "2026-03-22T09:00:00+00:00", "scheduled_time": "2026-03-22T12:00:00+00:00", "status": "scheduled", "platforms": "facebook"}],
            "drafted": [{"generated_at": "2026-03-22T08:00:00+00:00"}],
            "approval": [],
            "errors": [{"status": "failed", "last_error": "AUTH_ERROR", "last_error_at": "2026-03-22T07:00:00+00:00"}],
        },
    )

    assert any(
        event["type"] == "publish" and event["message"] == "Content published to Facebook, Instagram"
        for event in events
    )
    assert any(event["type"] == "token" for event in events)
    assert any(event["type"] == "error" for event in events)


def test_load_health_events_payload_uses_real_recent_rows(monkeypatch):
    fake_db = FakeDBClient({
        "published_posts": [
            {"data": [{"published_at": "2026-03-22T10:00:00+00:00", "platforms": "facebook"}]}
        ],
        "scheduled_posts": [
            {"data": [{"created_at": "2026-03-22T09:00:00+00:00", "scheduled_time": "2026-03-22T12:00:00+00:00", "status": "scheduled", "platforms": "facebook"}]}
        ],
        "processed_content": [
            {"data": [{"generated_at": "2026-03-22T08:30:00+00:00", "created_at": "2026-03-22T08:00:00+00:00"}]},
            {"data": [{"approval_requested_at": "2026-03-22T08:15:00+00:00", "created_at": "2026-03-22T08:00:00+00:00"}]},
            {"data": [{"status": "retry_scheduled", "last_error": "SERVER_ERROR", "last_error_at": "2026-03-22T08:45:00+00:00", "next_retry_at": "2026-03-22T09:00:00+00:00"}]},
        ],
    })
    monkeypatch.setattr(api_routes.config, "get_database_client", lambda: fake_db)
    monkeypatch.setattr(app_utils, "get_active_page_health", lambda _uid: {"connected": False, "token_status": "missing"})

    events = api_routes._load_health_events_payload("user-123")

    assert events[0]["message"] == "Content published to Facebook"
    assert any("retry scheduled" in event["message"] for event in events)
    assert any(event["type"] == "generate" for event in events)
    assert any(event["type"] == "approval" for event in events)


def test_run_facebook_service_test_reports_success(monkeypatch):
    monkeypatch.setattr(app_utils, "get_active_page_health", lambda _uid: {
        "connected": True,
        "page_id": "123",
        "page_name": "My Page",
        "token_status": "healthy",
    })
    monkeypatch.setattr(app_utils, "load_tokens_for_user", lambda _uid: {"page_token": "fb-token"})

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"id": "123", "name": "My Page"}

    monkeypatch.setattr(api_routes.requests, "get", lambda *args, **kwargs: Response())

    payload = api_routes._run_facebook_service_test("user-123")

    assert payload["success"] is True
    assert payload["details"]["page_name"] == "My Page"


def test_run_ai_service_test_reports_missing_key(monkeypatch):
    import user_config

    class FakeUserConfig:
        ai_provider = "claude"
        ai_model = "claude-sonnet-4-6"
        ai_api_key = ""
        gemini_api_key = ""

    monkeypatch.setattr(user_config.UserConfig, "from_db", classmethod(lambda cls, _uid: FakeUserConfig()))

    payload = api_routes._run_ai_service_test("user-123")

    assert payload["success"] is False
    assert payload["message"] == "No AI provider key is configured for this account."


def test_health_status_does_not_use_env_ai_key_without_explicit_fallback(monkeypatch):
    fake_db = FakeDBClient({
        "processed_content": [
            {"data": []},
            {"count": 0},
            {"count": 0},
            {"count": 0},
            {"count": 0},
        ],
        "scheduled_posts": [
            {"data": []},
            {"count": 0},
        ],
        "published_posts": [
            {"data": []},
            {"count": 0},
        ],
    })
    monkeypatch.setattr(api_routes.config, "get_database_client", lambda: fake_db)
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {})
    monkeypatch.setattr(app_utils, "get_active_page_health", lambda _uid: {"connected": False, "token_status": "missing"})
    monkeypatch.setenv("GEMINI_API_KEY", "env-only-key")
    monkeypatch.delenv("ALLOW_ENV_AI_FALLBACK", raising=False)

    payload = api_routes._load_health_status_payload("user-123")

    assert payload["tokens"]["ai"] is False
    assert payload["ai_source"] == "not_configured"


def test_health_status_can_use_env_ai_key_when_explicitly_allowed(monkeypatch):
    fake_db = FakeDBClient({
        "processed_content": [
            {"data": []},
            {"count": 0},
            {"count": 0},
            {"count": 0},
            {"count": 0},
        ],
        "scheduled_posts": [
            {"data": []},
            {"count": 0},
        ],
        "published_posts": [
            {"data": []},
            {"count": 0},
        ],
    })
    monkeypatch.setattr(api_routes.config, "get_database_client", lambda: fake_db)
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {"ai_provider": "gemini"})
    monkeypatch.setattr(app_utils, "get_active_page_health", lambda _uid: {"connected": False, "token_status": "missing"})
    monkeypatch.setenv("GEMINI_API_KEY", "env-only-key")
    monkeypatch.setenv("ALLOW_ENV_AI_FALLBACK", "true")

    payload = api_routes._load_health_status_payload("user-123")

    assert payload["tokens"]["ai"] is True
    assert payload["ai_source"] == "env_fallback"


def test_run_pexels_service_test_reports_success(monkeypatch):
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {"pexels_api_key": "pexels-key"})

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"photos": []}

    monkeypatch.setattr(api_routes.requests, "get", lambda *args, **kwargs: Response())

    payload = api_routes._run_pexels_service_test("user-123")

    assert payload["success"] is True
    assert payload["details"]["source"] == "user_settings"


def test_health_route_and_service_test_route_return_real_payloads(monkeypatch):
    app = Flask(__name__)
    _patch_authenticated_user(monkeypatch)
    monkeypatch.setattr(api_routes, "_load_health_status_payload", lambda _uid: {"tokens": {"facebook": False, "ai": False, "ai_source": "not_configured"}, "ai_source": "not_configured", "last_error": None, "cooldown": {"active": False, "until": None, "reason": "Ready"}})
    monkeypatch.setattr(api_routes, "_load_health_events_payload", lambda _uid: [{"type": "publish", "message": "Content published", "time": "1 h ago"}])
    monkeypatch.setattr(api_routes, "_run_health_service_test", lambda _service, _uid: {"success": False, "service": _service, "message": "No active Facebook page connected."})

    with app.test_request_context("/api/health/status", method="GET"):
        status_response = api_routes.get_health_detailed()
    with app.test_request_context("/api/health/events", method="GET"):
        events_response = api_routes.get_health_events()
    with app.test_request_context("/api/health/test/facebook", method="GET"):
        service_response, service_status = api_routes.run_service_test("facebook")

    assert status_response.get_json()["success"] is True
    assert status_response.get_json()["cooldown"]["reason"] == "Ready"
    assert events_response.get_json()["success"] is True
    assert events_response.get_json()["events"][0]["type"] == "publish"
    assert service_status == 400
    assert service_response.get_json()["message"] == "No active Facebook page connected."


def test_runtime_status_payload_is_user_scoped_and_contract_stable(monkeypatch):
    app = Flask(__name__)
    fake_user = _patch_authenticated_user(monkeypatch)
    fake_db = FakeDBClient({
        "published_posts": [{"count": 1}],
    })
    monkeypatch.setattr(api_routes.config, "get_database_client", lambda: fake_db)
    monkeypatch.setattr(
        api_routes,
        "_load_health_status_payload",
        lambda _uid: {
            "page": {"connected": True, "page_name": "My Page"},
            "tokens": {"ai": True, "facebook_status": "healthy"},
            "cooldown": {"active": False, "reason": "Ready"},
        },
    )
    monkeypatch.setattr(app_utils, "get_user_settings", lambda _uid: {"posts_per_day": 3})

    with app.test_request_context("/api/status", method="GET"):
        response = api_routes.get_system_status()

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["can_post"] is True
    assert payload["rate_limiter"]["posts_today"] == 1
    assert payload["rate_limiter"]["daily_limit"] == 3
    assert payload["ban_detector"]["status"] == "ok"
