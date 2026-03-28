from types import SimpleNamespace

from flask import Flask, session

from app import create_app
import app.api.routes as api_routes
import app.dashboard.routes as dashboard_routes
import app.settings.routes as settings_routes
import app.studio.routes as studio_routes
import app.utils as app_utils


class FakeUser:
    def __init__(self, user_id: str = "user-123"):
        self.id = user_id
        self.is_authenticated = True


class FakeTable:
    def __init__(self, name: str, store: dict):
        self.name = name
        self.store = store
        self._reset()

    def _reset(self):
        self._filters = []
        self._in_filters = []
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

    def order(self, key, desc=False):
        self._order = (key, desc)
        return self

    def limit(self, value):
        self._limit = value
        return self

    def single(self):
        self._single = True
        return self

    def _match(self, row):
        return all(row.get(key) == value for key, value in self._filters) and all(
            row.get(key) in values for key, values in self._in_filters
        )

    def execute(self):
        rows = [dict(row) for row in self.store.get(self.name, []) if self._match(row)]
        if self._order:
            key, desc = self._order
            rows.sort(key=lambda row: row.get(key) or "", reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return SimpleNamespace(data=rows[0] if self._single else rows)


class FakeClient:
    def __init__(self, store: dict):
        self.store = store

    def table(self, name):
        return FakeTable(name, self.store)


def _patch_user(monkeypatch, fake_user):
    monkeypatch.setattr(app_utils, "current_user", fake_user, raising=False)
    monkeypatch.setattr(studio_routes, "current_user", fake_user, raising=False)
    monkeypatch.setattr(api_routes, "current_user", fake_user, raising=False)
    monkeypatch.setattr(settings_routes, "current_user", fake_user, raising=False)


def _registered_rules(app):
    return {rule.rule for rule in app.url_map.iter_rules()}


def test_templates_route_uses_active_template(monkeypatch):
    app = Flask(__name__)
    monkeypatch.setattr(dashboard_routes, "url_for", lambda endpoint: "/channels")

    with app.test_request_context("/templates"):
        response = dashboard_routes.page_templates.__wrapped__()

    assert response.status_code == 302
    assert response.location.endswith("/channels")


def test_oauth_select_page_uses_active_template(monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    captured = {}

    monkeypatch.setattr(
        dashboard_routes,
        "render_template",
        lambda template, **context: captured.update({"template": template, "context": context}) or captured,
    )

    with app.test_request_context("/oauth/facebook/select-page", method="GET"):
        session["fb_oauth_result"] = {"pages": [{"id": "page-1", "name": "Main Page"}]}
        response = dashboard_routes.oauth_select_page.__wrapped__()

    assert response["template"] == "page_select.html"
    assert response["context"]["active_page"] == "channels"


def test_pending_content_includes_page_platform_language_and_context(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    store = {
        "managed_pages": [
            {
                "user_id": fake_user.id,
                "status": "active",
                "page_id": "page-1",
                "page_name": "Main Page",
                "instagram_account_id": "ig-1",
                "language": "fr",
            }
        ],
        "raw_articles": [
            {
                "id": "article-1",
                "user_id": fake_user.id,
                "title": "AI market update",
                "source_name": "News Wire",
                "url": "https://example.com/article",
            }
        ],
        "processed_content": [
            {
                "id": "content-1",
                "user_id": fake_user.id,
                "status": "waiting_approval",
                "post_type": "post",
                "generated_text": "Body copy",
                "hook": "Strong hook",
                "hashtags": ["ai"],
                "image_path": "img.png",
                "generated_at": "2026-03-24T10:00:00+00:00",
                "article_id": "article-1",
                "target_audience": "fr",
            }
        ],
    }

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(studio_routes, "_client", lambda: FakeClient(store))

    with app.test_request_context("/api/content/pending", method="GET"):
        response = studio_routes.get_pending_content()

    payload = response.get_json()
    assert payload["pending"][0]["page_name"] == "Main Page"
    assert payload["pending"][0]["platform_label"] == "Facebook + Instagram"
    assert payload["pending"][0]["language"] == "fr"
    assert payload["pending"][0]["preview_text"] == "Strong hook"
    assert payload["pending"][0]["context"]["article_title"] == "AI market update"


def test_removed_legacy_studio_routes_are_not_registered():
    app = create_app()
    rules = _registered_rules(app)

    assert "/api/actions/create-content" not in rules
    assert "/api/ab-tests" not in rules
    assert "/api/ab-tests/<test_id>/results" not in rules
    assert "/api/virality/score" not in rules
    assert "/api/virality/analyze" not in rules
    assert "/api/brand/templates" not in rules
    assert "/api/brand/template-select" not in rules


def test_removed_legacy_api_routes_are_not_registered():
    app = create_app()
    rules = _registered_rules(app)

    assert "/api/insights" not in rules
    assert "/api/status/modules" not in rules
    assert "/api/randomization/config" not in rules
    assert "/api/logs/recent" not in rules


def test_removed_legacy_settings_routes_are_not_registered():
    app = create_app()
    rules = _registered_rules(app)

    assert "/api/config/database" not in rules
