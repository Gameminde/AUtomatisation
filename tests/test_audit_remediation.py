from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, render_template, session
from werkzeug.exceptions import HTTPException

from app import create_app
import app.api.routes as api_routes
import app.dashboard.routes as dashboard_routes
import app.studio.payloads as studio_payloads
import app.studio.routes as studio_routes
import app.utils as app_utils


class FakeUser:
    def __init__(self, user_id: str = "user-123", email: str = "user@example.com"):
        self.id = user_id
        self.email = email
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False

    def get_id(self):
        return self.id


class TrackerTable:
    def __init__(self, name: str, store: dict):
        self.name = name
        self.store = store
        self._filters = []
        self._in_filters = []
        self._gte_filters = []
        self._order = None
        self._limit = None
        self._single = False

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def in_(self, key, values):
        self._in_filters.append((key, set(values)))
        return self

    def gte(self, key, value):
        self._gte_filters.append((key, value))
        return self

    def order(self, key, desc=False):
        self._order = (key, desc)
        return self

    def limit(self, value):
        self._limit = value
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        rows = [dict(row) for row in self.store.get(self.name, [])]
        rows = [
            row
            for row in rows
            if all(row.get(key) == value for key, value in self._filters)
            and all(row.get(key) in values for key, values in self._in_filters)
            and all((row.get(key) or "") >= value for key, value in self._gte_filters)
        ]
        if self._order:
            key, desc = self._order
            rows.sort(key=lambda row: row.get(key) or "", reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        if self._single:
            return SimpleNamespace(data=rows[0] if rows else None, count=1 if rows else 0)
        return SimpleNamespace(data=rows, count=len(rows))


class TrackerClient:
    def __init__(self, store: dict):
        self.store = store

    def table(self, name: str):
        return TrackerTable(name, self.store)


class MutatingTable:
    def __init__(self, name: str, store: dict):
        self.name = name
        self.store = store
        self._filters = []
        self._limit = None
        self._select_fields = None
        self._operation = "select"
        self._payload = None

    def select(self, fields, *_args, **_kwargs):
        self._operation = "select"
        self._select_fields = [field.strip() for field in str(fields or "").split(",") if field.strip()]
        return self

    def insert(self, payload):
        self._operation = "insert"
        self._payload = dict(payload)
        return self

    def update(self, payload):
        self._operation = "update"
        self._payload = dict(payload)
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def limit(self, value):
        self._limit = value
        return self

    def _rows(self):
        return self.store.setdefault(self.name, [])

    def _matches(self, row):
        return all(row.get(key) == value for key, value in self._filters)

    def execute(self):
        rows = self._rows()
        if self._operation == "insert":
            rows.append(dict(self._payload or {}))
            return SimpleNamespace(data=[dict(self._payload or {})], count=1)
        if self._operation == "update":
            updated = []
            for row in rows:
                if self._matches(row):
                    row.update(self._payload or {})
                    updated.append(dict(row))
            return SimpleNamespace(data=updated, count=len(updated))

        matched = [dict(row) for row in rows if self._matches(row)]
        if self._limit is not None:
            matched = matched[: self._limit]
        if self._select_fields:
            matched = [
                {field: row.get(field) for field in self._select_fields}
                for row in matched
            ]
        return SimpleNamespace(data=matched, count=len(matched))


class MutatingClient:
    def __init__(self, store: dict):
        self.store = store

    def table(self, name: str):
        return MutatingTable(name, self.store)


class ManagedPagesCompatQuery:
    def __init__(self, rows):
        self.rows = rows
        self._filters = []
        self._fields = []

    def select(self, fields, *_args, **_kwargs):
        self._fields = [field.strip() for field in str(fields or "").split(",") if field.strip()]
        return self

    def eq(self, key, value):
        self._filters.append((key, value))
        return self

    def execute(self):
        if "last_synced_at" in self._fields:
            raise Exception(
                "{'message': 'column managed_pages.last_synced_at does not exist', 'code': '42703'}"
            )
        matched = [
            {
                field: row.get(field)
                for field in self._fields
            }
            for row in self.rows
            if all(row.get(key) == value for key, value in self._filters)
        ]
        return SimpleNamespace(data=matched, count=len(matched))


class ManagedPagesCompatClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name: str):
        assert name == "managed_pages"
        return ManagedPagesCompatQuery(self.rows)


def _frontend_runtime_sources() -> str:
    root = Path("C:/Users/youcefcheriet/fb/fbautomat/static/js")
    sources = [root / "cf.js", *sorted((root / "cf").rglob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in sources)


def test_bootstrap_route_returns_page_scoped_payload(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    monkeypatch.setattr(api_routes, "current_user", fake_user, raising=False)
    monkeypatch.setattr(app_utils, "current_user", fake_user, raising=False)
    monkeypatch.setattr(
        api_routes,
        "_build_bootstrap_payload",
        lambda user_id, page: {
            "shell": {"setup": {"steps": []}, "status": {"can_post": True}},
            "page": page,
            "dashboard": {"summary": {"pending": []}, "health": {}, "events": [], "pages": {"pages": []}},
        },
    )

    with app.test_request_context("/api/bootstrap?page=dashboard", method="GET"):
        response = api_routes.get_bootstrap.__wrapped__()

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["page"] == "dashboard"
    assert "shell" in payload
    assert "dashboard" in payload


def test_bootstrap_route_degrades_gracefully_when_section_fails(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    monkeypatch.setattr(api_routes, "current_user", fake_user, raising=False)
    monkeypatch.setattr(app_utils, "current_user", fake_user, raising=False)
    monkeypatch.setattr(api_routes, "_load_setup_progress_payload", lambda _uid: (_ for _ in ()).throw(RuntimeError("setup timeout")))
    monkeypatch.setattr(
        api_routes,
        "_load_runtime_status_payload",
        lambda _uid: {
            "success": True,
            "can_post": False,
            "post_reason": "Unavailable",
            "rate_limiter": {"can_post": False, "posts_today": 0, "daily_limit": 0, "remaining": 0},
            "ban_detector": {"status": "unknown", "reason": "Unavailable", "severity": 0},
            "health": "degraded",
        },
    )
    monkeypatch.setattr(api_routes, "_load_health_status_payload", lambda _uid: {"page": {"connected": False}, "tokens": {}, "cooldown": {"active": False}, "pipeline": {}, "last_error": None})
    monkeypatch.setattr(api_routes, "_load_health_events_payload", lambda _uid: [])
    monkeypatch.setattr("app.pages.routes.load_pages_payload", lambda _uid: {"success": True, "pages": []})
    monkeypatch.setattr("app.studio.routes._load_dashboard_summary_payload", lambda _uid: {"pending": [], "scheduled": [], "published": [], "ready_count": 0})

    with app.test_request_context("/api/bootstrap?page=dashboard", method="GET"):
        response = api_routes.get_bootstrap.__wrapped__()

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["shell"]["setup"]["steps"] == []
    assert payload["_bootstrap"]["errors"]


def test_server_templates_render_csrf_tokens():
    app = create_app()

    with app.test_request_context("/auth/login"):
        login_html = render_template("auth/login.html", error=None)

    with app.test_request_context("/auth/register"):
        register_html = render_template("auth/register.html", error=None)

    with app.test_request_context("/oauth/facebook/select-page"):
        session["ui_language"] = "EN"
        page_select_html = render_template(
            "page_select.html",
            active_page="channels",
            oauth_pages=[{"id": "page-1", "name": "Main Page"}],
        )

    assert 'name="csrf_token"' in login_html
    assert 'name="csrf_token"' in register_html
    assert 'name="csrf_token"' in page_select_html


def test_layout_uses_module_runtime_and_no_dashboard_api_key():
    app = create_app()

    with app.test_request_context("/channels"):
        html = render_template("channels.html", active_page="channels")

    assert 'meta name="dashboard-api-key"' not in html
    assert 'meta name="csrf-token"' in html
    assert 'type="module" src="/static/js/cf.js"' in html


def test_dashboard_route_serves_react_shell_with_boot_payload(monkeypatch):
    from flask_login import login_user

    app = create_app()
    fake_user = FakeUser(email="react@example.com")
    monkeypatch.setattr(dashboard_routes, "_react_frontend_ready", lambda: True)
    monkeypatch.setattr(dashboard_routes, "_react_dev_server", lambda: "http://127.0.0.1:5173")

    with app.test_request_context("/app/dashboard"):
        session["ui_language"] = "FR"
        login_user(fake_user)
        html = dashboard_routes.page_dashboard.__wrapped__()

    assert 'window.__CF_WEB_BOOT__' in html
    assert '"page": "dashboard"' in html
    assert '"locale": "FR"' in html
    assert '"email": "react@example.com"' in html
    assert "/auth/logout" in html
    assert "http://127.0.0.1:5173/@vite/client" in html


@pytest.mark.parametrize(
    ("path", "page_name", "view_func"),
    [
        ("/channels", "channels", dashboard_routes.page_channels),
        ("/settings", "settings", dashboard_routes.page_settings),
        ("/diagnostics", "diagnostics", dashboard_routes.page_diagnostics),
    ],
)
def test_migrated_routes_serve_react_shell_when_frontend_ready(monkeypatch, path, page_name, view_func):
    from flask_login import login_user

    app = create_app()
    fake_user = FakeUser(email="react@example.com")
    monkeypatch.setattr(dashboard_routes, "_react_frontend_ready", lambda: True)
    monkeypatch.setattr(dashboard_routes, "_react_dev_server", lambda: "http://127.0.0.1:5173")

    with app.test_request_context(path):
        session["ui_language"] = "EN"
        login_user(fake_user)
        html = view_func.__wrapped__()

    assert 'window.__CF_WEB_BOOT__' in html
    assert f'"page": "{page_name}"' in html
    assert "http://127.0.0.1:5173/@vite/client" in html


def test_studio_route_requires_react_frontend_when_react_frontend_is_unavailable(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(dashboard_routes, "_react_frontend_ready", lambda: False)

    with app.test_request_context("/studio"), pytest.raises(HTTPException) as caught:
        dashboard_routes.page_studio.__wrapped__()

    assert caught.value.code == 503
    assert caught.value.description == "The React frontend is required for studio."


def test_channels_route_renders_channels_template(monkeypatch):
    app = Flask(__name__)
    captured = {}
    monkeypatch.setattr(dashboard_routes, "_react_frontend_ready", lambda: False)
    monkeypatch.setattr(
        dashboard_routes,
        "render_template",
        lambda template, **context: captured.update({"template": template, "context": context}) or captured,
    )

    with app.test_request_context("/channels"):
        response = dashboard_routes.page_channels.__wrapped__()

    assert response["template"] == "channels.html"
    assert response["context"]["active_page"] == "channels"


def test_studio_bootstrap_includes_template_defaults(monkeypatch):
    monkeypatch.setattr("app.utils.get_available_presets", lambda: {"niches": []})
    monkeypatch.setattr(
        "user_config.get_user_config",
        lambda _user_id: SimpleNamespace(
            timezone="UTC",
            content_language="en",
            content_tone="professional",
            niche_preset="",
        ),
    )
    monkeypatch.setattr(
        app_utils,
        "get_user_settings",
        lambda _user_id: {
            "studio_template_defaults": json.dumps({
                "titleText": "Legacy headline",
                "titleSize": 54,
                "mediaWidth": 72,
                "backgroundImagePath": "https://example.com/background.png",
                "backgroundZoom": 122,
                "titleScale": 118,
                "titleFontFamily": "display",
                "titleColor": "#fff8ef",
                "showBrandBadge": True,
            })
        },
    )
    monkeypatch.setattr(studio_payloads, "_load_active_page_context", lambda _user_id: {})
    monkeypatch.setattr(studio_payloads, "_load_draft_content_payload", lambda _user_id: {"drafts": []})
    monkeypatch.setattr(studio_payloads, "_load_pending_content_payload", lambda _user_id: {"pending": []})
    monkeypatch.setattr(studio_payloads, "_load_scheduled_content_payload", lambda _user_id: {"scheduled": []})
    monkeypatch.setattr(studio_payloads, "_load_published_content_payload", lambda _user_id: {"published": []})

    payload = studio_payloads._load_studio_bootstrap_payload("user-123")

    assert payload["profile"]["template_defaults"]["mediaWidth"] == 72
    assert payload["profile"]["template_defaults"]["backgroundImagePath"] == "https://example.com/background.png"
    assert payload["profile"]["template_defaults"]["backgroundZoom"] == 122
    assert payload["profile"]["template_defaults"]["showBrandBadge"] is True
    assert payload["profile"]["template_defaults"]["titleScale"] == 118
    assert payload["profile"]["template_defaults"]["titleFontFamily"] == "display"
    assert payload["profile"]["template_defaults"]["titleColor"] == "#fff8ef"
    assert "titleSize" not in payload["profile"]["template_defaults"]
    assert "titleText" not in payload["profile"]["template_defaults"]


def test_studio_template_settings_route_persists_defaults(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    captured = {}
    monkeypatch.setattr(studio_routes, "current_user", fake_user, raising=False)
    monkeypatch.setattr(
        studio_routes,
        "require_user_settings_update",
        lambda user_id, updates: captured.update({"user_id": user_id, "updates": updates}),
    )

    with app.test_request_context(
        "/api/studio/template-settings",
        method="POST",
        json={
            "titleText": "Legacy headline",
            "titleSize": 999,
            "mediaWidth": 12,
            "mediaHeight": 999,
            "mediaClarity": 200,
            "mediaOffsetX": 52,
            "mediaOffsetY": -78,
            "titleAlign": "center",
            "titleScale": 150,
            "titleOffsetY": -55,
            "titleWidth": 140,
            "titleFontFamily": "mono",
            "titleColor": "#ABCDEF",
            "showBrandBadge": True,
            "backgroundImagePath": "https://example.com/background.png",
            "backgroundZoom": 220,
            "backgroundOffsetX": -55,
            "backgroundOffsetY": 18,
        },
    ):
        response = studio_routes.studio_template_settings.__wrapped__()

    payload = response.get_json()
    saved = json.loads(captured["updates"]["studio_template_defaults"])
    assert captured["user_id"] == "user-123"
    assert saved["mediaWidth"] == 30
    assert saved["mediaHeight"] == 260
    assert saved["mediaClarity"] == 140
    assert saved["mediaOffsetX"] == 52
    assert saved["mediaOffsetY"] == -60
    assert saved["backgroundImagePath"] == "https://example.com/background.png"
    assert saved["backgroundZoom"] == 180
    assert saved["backgroundOffsetX"] == -40
    assert saved["backgroundOffsetY"] == 18
    assert saved["titleScale"] == 140
    assert saved["titleOffsetY"] == -24
    assert saved["titleWidth"] == 100
    assert saved["titleFontFamily"] == "mono"
    assert saved["titleColor"] == "#abcdef"
    assert saved["showBrandBadge"] is True
    assert "titleText" not in saved
    assert "titleSize" not in saved
    assert "titleAlign" not in saved
    assert payload["success"] is True


def test_sqlite_query_builder_rejects_unknown_column(tmp_path):
    from database.database import SQLiteDB

    db = SQLiteDB(str(tmp_path / "audit.db"))

    with pytest.raises(ValueError, match="Invalid column name"):
        db.table("raw_articles").select("*").eq("bad_column;drop", "value").execute()


def test_get_unpublished_content_does_not_call_can_publish_per_item(monkeypatch):
    from publication_tracker import PublicationTracker

    store = {
        "processed_content": [
            {
                "id": "content-1",
                "article_id": "article-1",
                "hook": "Hook",
                "post_type": "post",
                "generated_at": "2026-03-26T10:00:00+00:00",
                "generated_text": "Fresh content",
            }
        ],
        "published_posts": [],
        "raw_articles": [{"id": "article-1", "url": "https://example.com/fresh"}],
    }

    monkeypatch.setattr("config.get_supabase_client", lambda: TrackerClient(store))
    monkeypatch.setattr(PublicationTracker, "can_publish", lambda self, content_id: (_ for _ in ()).throw(AssertionError("can_publish should not be called")))

    tracker = PublicationTracker.__new__(PublicationTracker)
    tracker._published_urls = set()
    tracker._published_hashes = set()
    tracker._published_simhashes = []
    tracker._cache = {}

    result = tracker.get_unpublished_content(limit=5)

    assert [row["id"] for row in result] == ["content-1"]


def test_publication_tracker_scopes_similarity_cache_by_user(monkeypatch):
    from publication_tracker import PublicationTracker

    store = {
        "published_posts": [
            {
                "content_id": "content-a",
                "user_id": "user-a",
                "facebook_post_id": "fb-1",
                "instagram_post_id": "",
                "facebook_status": "published",
                "instagram_status": "",
                "published_at": "2026-03-26T10:00:00+00:00",
            }
        ],
        "processed_content": [
            {
                "id": "content-a",
                "user_id": "user-a",
                "article_id": "article-a",
                "hook": "Hook A",
                "generated_text": "Fresh content for one tenant only",
            },
            {
                "id": "content-b",
                "user_id": "user-b",
                "article_id": "article-b",
                "hook": "Hook B",
                "generated_text": "Fresh content for one tenant only",
            },
        ],
        "raw_articles": [
            {"id": "article-a", "user_id": "user-a", "url": "https://example.com/a", "status": "processed"},
            {"id": "article-b", "user_id": "user-b", "url": "https://example.com/b", "status": "processed"},
        ],
    }

    monkeypatch.setattr("config.get_supabase_client", lambda: TrackerClient(store))

    tracker = PublicationTracker(user_id="user-b")
    can_publish, reason = tracker.can_publish("content-b")

    assert can_publish is True, reason
    assert tracker._published_urls == set()


def test_frontend_runtime_uses_bootstrap_and_canonical_ai_route():
    source = _frontend_runtime_sources()

    assert "/api/bootstrap?page=" in source
    assert "/api/settings/test-ai" in source
    assert "/api/ai/test-key" not in source
    assert "window.location.reload" not in source


def test_frontend_runtime_translation_keys_exist_in_catalog():
    source = _frontend_runtime_sources()
    catalog = Path("C:/Users/youcefcheriet/fb/fbautomat/app/i18n.py").read_text(encoding="utf-8")

    keys = set()
    for pattern in [r'tr\("([^"]+)"', r'tt\("([^"]+)"', r'maybeTr\("([^"]+)"']:
        keys.update(re.findall(pattern, source))

    missing = sorted(key for key in keys if catalog.count(f'"{key}"') < 2)
    assert missing == []


def test_add_page_encrypts_token_and_keeps_response_safe(monkeypatch):
    import config
    import app.pages.routes as pages_routes

    app = Flask(__name__)
    app.secret_key = "test-secret"
    fake_user = FakeUser()
    store = {"managed_pages": []}
    client = MutatingClient(store)

    monkeypatch.setattr(pages_routes, "current_user", fake_user, raising=False)
    monkeypatch.setattr(config, "get_database_client", lambda: client)
    monkeypatch.setattr(app_utils, "_get_supabase_client", lambda: client)

    with app.test_request_context(
        "/api/pages",
        method="POST",
        json={
            "page_id": "page-1",
            "page_name": "Main Page",
            "access_token": "plain-token",
            "instagram_account_id": "ig-1",
            "posts_per_day": 4,
            "posting_times": "08:00,16:00",
            "language": "fr",
        },
    ):
        response = pages_routes.add_page.__wrapped__()

    payload = response.get_json()
    stored_row = store["managed_pages"][0]

    assert payload["success"] is True
    assert "access_token" not in payload["page"]
    assert stored_row["access_token"] != "plain-token"
    assert app_utils.decrypt_value(stored_row["access_token"]) == "plain-token"

    tokens = app_utils.load_tokens_for_user(fake_user.id)
    assert tokens["page_id"] == "page-1"
    assert tokens["page_token"] == "plain-token"


def test_pages_payload_and_update_normalize_to_one_active_page(monkeypatch):
    import config
    import app.pages.routes as pages_routes

    app = Flask(__name__)
    app.secret_key = "test-secret"
    fake_user = FakeUser()
    store = {
        "managed_pages": [
            {
                "page_id": "page-1",
                "user_id": fake_user.id,
                "page_name": "First",
                "instagram_account_id": "",
                "posts_per_day": 3,
                "posting_times": "08:00",
                "language": "en",
                "status": "active",
                "created_at": "2026-03-25T09:00:00+00:00",
            },
            {
                "page_id": "page-2",
                "user_id": fake_user.id,
                "page_name": "Second",
                "instagram_account_id": "",
                "posts_per_day": 3,
                "posting_times": "10:00",
                "language": "fr",
                "status": "active",
                "created_at": "2026-03-26T09:00:00+00:00",
            },
        ]
    }
    client = MutatingClient(store)

    monkeypatch.setattr(pages_routes, "current_user", fake_user, raising=False)
    monkeypatch.setattr(config, "get_database_client", lambda: client)

    payload = pages_routes.load_pages_payload(fake_user.id)
    active_pages = [row for row in payload["pages"] if row["status"] == "active"]
    assert [row["page_id"] for row in active_pages] == ["page-2"]

    with app.test_request_context("/api/pages/page-1", method="PUT", json={"status": "active"}):
        response = pages_routes.update_page.__wrapped__("page-1")

    assert response.get_json()["success"] is True
    active_after = [row["page_id"] for row in store["managed_pages"] if row.get("status") == "active"]
    assert active_after == ["page-1"]


def test_managed_pages_loader_tolerates_missing_last_synced_at(monkeypatch):
    import config

    fake_user = FakeUser()
    client = ManagedPagesCompatClient(
        [
            {
                "page_id": "page-1",
                "user_id": fake_user.id,
                "page_name": "Main Page",
                "instagram_account_id": "",
                "posts_per_day": 3,
                "posting_times": "08:00",
                "language": "en",
                "status": "active",
                "created_at": "2026-03-26T09:00:00+00:00",
                "token_expires_at": "2026-04-26T09:00:00+00:00",
            }
        ]
    )

    monkeypatch.setattr(config, "get_database_client", lambda: client)
    monkeypatch.setattr(app_utils, "_managed_pages_missing_optional_columns", set())

    pages = app_utils.get_managed_pages_for_user(fake_user.id)
    health = app_utils.get_active_page_health(fake_user.id)

    assert pages[0]["last_synced_at"] is None
    assert health["connected"] is True
    assert health["page_id"] == "page-1"
    assert "error" not in health


def test_template_render_uses_session_locale_without_settings_lookup(monkeypatch):
    app = create_app()

    def fail_if_called(_user_id):
        raise AssertionError("get_user_settings should not be called when session locale is already set")

    monkeypatch.setattr(app_utils, "get_user_settings", fail_if_called)

    with app.test_request_context("/channels"):
        session["ui_language"] = "FR"
        html = render_template("channels.html", active_page="channels")

    assert "Canaux" in html


def test_logout_route_is_post_only():
    app = create_app()
    auth_logout_rules = [rule for rule in app.url_map.iter_rules() if rule.endpoint == "auth.logout"]

    assert auth_logout_rules
    assert all("POST" in rule.methods for rule in auth_logout_rules)
    assert all("GET" not in rule.methods for rule in auth_logout_rules)
