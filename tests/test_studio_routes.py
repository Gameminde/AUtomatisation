"""Unit tests for Studio routes backed by real backend logic."""

from types import SimpleNamespace

from flask import Flask

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
        self._insert_payload = None
        self._update_payload = None

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

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    def _match(self, row):
        return all(row.get(key) == value for key, value in self._filters) and all(
            row.get(key) in values for key, values in self._in_filters
        )

    def execute(self):
        rows = self.store.setdefault(self.name, [])
        data = None

        if self._insert_payload is not None:
            payload = dict(self._insert_payload)
            payload.setdefault("id", f"{self.name}-{len(rows) + 1}")
            rows.append(payload)
            data = [dict(payload)]
        elif self._update_payload is not None:
            updated = []
            for row in rows:
                if self._match(row):
                    row.update(self._update_payload)
                    updated.append(dict(row))
            data = updated
        else:
            result_rows = [dict(row) for row in rows if self._match(row)]
            if self._order:
                key, desc = self._order
                result_rows.sort(key=lambda row: row.get(key) or "", reverse=desc)
            if self._limit is not None:
                result_rows = result_rows[: self._limit]
            data = result_rows[0] if self._single else result_rows

        self._reset()
        return SimpleNamespace(data=data)


class FakeClient:
    def __init__(self, store: dict):
        self.store = store

    def table(self, name):
        return FakeTable(name, self.store)


def _patch_user(monkeypatch, fake_user):
    monkeypatch.setattr(app_utils, "current_user", fake_user)
    monkeypatch.setattr(studio_routes, "current_user", fake_user)


def test_get_draft_content_returns_draft_only_and_draft_ready(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    store = {
        "processed_content": [
            {
                "id": "d1",
                "post_type": "story_sequence",
                "status": "draft_only",
                "user_id": fake_user.id,
                "generated_text": '{"format":"story_sequence","language":"ar","frames":[{"frame_number":1,"text":"مرحبا","visual_suggestion":"Visual"}]}',
                "hook": "مرحبا",
                "hashtags": ["tag1"],
                "image_path": "",
                "target_audience": "AR",
            },
            {
                "id": "d2",
                "post_type": "reel_script",
                "status": "draft_ready",
                "user_id": fake_user.id,
                "generated_text": '{"format":"reel_script","language":"en","hook":"Hook","points":["One"],"cta":"CTA"}',
                "hook": "Hook",
                "hashtags": ["tag2"],
                "image_path": "",
                "target_audience": "EN",
            },
            {"id": "x1", "post_type": "post", "status": "scheduled", "user_id": fake_user.id},
        ]
    }

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(studio_routes, "_client", lambda: FakeClient(store))

    with app.test_request_context("/api/content/drafts", method="GET"):
        response = studio_routes.get_draft_content()

    payload = response.get_json()
    assert payload["success"] is True
    assert [row["id"] for row in payload["drafts"]] == ["d1", "d2"]
    assert payload["drafts"][0]["content_normalized"]["format"] == "story_sequence"
    assert payload["drafts"][0]["content_normalized"]["frames"][0]["text"] == "مرحبا"
    assert payload["drafts"][1]["content_normalized"]["format"] == "reel_script"
    assert payload["drafts"][1]["content_normalized"]["hook"] == "Hook"


def test_studio_generate_returns_structured_content(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    captured = {}

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(
        studio_routes,
        "_generate_studio_content",
        lambda **kwargs: captured.update(kwargs) or {
            "format": kwargs["content_format"],
            "language": kwargs["language"],
            "hook": "Hook",
            "body": "Body",
            "cta": "CTA",
            "hashtags": ["tag1"],
        },
    )

    with app.test_request_context(
        "/api/studio/generate",
        method="POST",
        json={"format": "post", "language": "en", "tone": "casual", "topic": "AI tools", "user_id": fake_user.id},
    ):
        response = studio_routes.studio_generate()

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["format"] == "post"
    assert payload["content"]["language"] == "en"
    assert captured["tone"] == "casual"


def test_studio_regenerate_updates_specific_item(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    captured = {}
    store = {
        "processed_content": [
            {
                "id": "pc-1",
                "user_id": fake_user.id,
                "post_type": "post",
                "generated_text": "Old body",
                "hook": "Old hook",
                "status": "draft_only",
            }
        ]
    }

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(studio_routes, "_client", lambda: FakeClient(store))
    monkeypatch.setattr(
        studio_routes,
        "_regenerate_existing_content",
        lambda row, instruction="", tone=None: captured.update(
            {"instruction": instruction, "tone": tone}
        ) or {
            "format": row["post_type"],
            "language": "en",
            "hook": "New hook",
            "body": "New body",
            "cta": "New CTA",
            "hashtags": ["new"],
        },
    )

    with app.test_request_context(
        "/api/studio/regenerate",
        method="POST",
        json={"content_id": "pc-1", "instruction": "make it shorter", "tone": "casual", "user_id": fake_user.id},
    ):
        response = studio_routes.studio_regenerate()

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["content_id"] == "pc-1"
    assert payload["content"]["hook"] == "New hook"
    assert captured["tone"] == "casual"


def test_studio_generate_accepts_reel_script(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(
        studio_routes,
        "_generate_studio_content",
        lambda **kwargs: {
            "format": kwargs["content_format"],
            "language": kwargs["language"],
            "hook": "Hook",
            "points": ["Point one", "Point two"],
            "cta": "Follow for more",
        },
    )

    with app.test_request_context(
        "/api/studio/generate",
        method="POST",
        json={"format": "reel_script", "language": "en", "topic": "creator hooks", "user_id": fake_user.id},
    ):
        response = studio_routes.studio_generate()

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["format"] == "reel_script"
    assert payload["content"]["hook"] == "Hook"


def test_studio_save_draft_inserts_processed_content(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    store = {"processed_content": []}

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(studio_routes, "_client", lambda: FakeClient(store))

    with app.test_request_context(
        "/api/studio/save-draft",
        method="POST",
        json={
            "format": "carousel",
            "language": "ar",
            "user_id": fake_user.id,
            "content": {
                "format": "carousel",
                "language": "ar",
                "slides": [
                    {
                        "slide_number": 1,
                        "headline": "Headline",
                        "body": "Body",
                        "visual_suggestion": "Visual",
                    }
                ],
                "caption": "Caption",
                "hashtags": ["tag1"],
            },
        },
    ):
        response = studio_routes.studio_save_draft()

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["status"] == "draft_only"
    assert store["processed_content"][0]["post_type"] == "carousel"
    assert store["processed_content"][0]["status"] == "draft_only"


def test_studio_approve_moves_draft_to_scheduled(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    store = {
        "processed_content": [
            {
                "id": "pc-1",
                "user_id": fake_user.id,
                "post_type": "post",
                "status": "draft_only",
            }
        ],
        "scheduled_posts": [],
    }

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(studio_routes, "_client", lambda: FakeClient(store))
    monkeypatch.setattr(
        studio_routes,
        "_load_runtime_profile",
        lambda user_id, language=None: SimpleNamespace(timezone="Europe/Paris"),
    )

    with app.test_request_context(
        "/api/studio/approve",
        method="POST",
        json={
            "content_id": "pc-1",
            "scheduled_time": "2026-03-22T10:00:00+00:00",
            "user_id": fake_user.id,
        },
    ):
        response = studio_routes.studio_approve()

    payload = response.get_json()
    assert payload["success"] is True
    assert store["processed_content"][0]["status"] == "scheduled"
    assert store["scheduled_posts"][0]["content_id"] == "pc-1"
    assert payload["content_id"] == "pc-1"
    assert payload["new_status"] == "scheduled"


def test_studio_approve_rejects_draft_only_formats(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    store = {
        "processed_content": [
            {
                "id": "pc-story",
                "user_id": fake_user.id,
                "post_type": "story_sequence",
                "status": "draft_only",
            }
        ],
        "scheduled_posts": [],
    }

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(studio_routes, "_client", lambda: FakeClient(store))
    monkeypatch.setattr(
        studio_routes,
        "_load_runtime_profile",
        lambda user_id, language=None: SimpleNamespace(timezone="Europe/Paris"),
    )

    with app.test_request_context(
        "/api/studio/approve",
        method="POST",
        json={
            "content_id": "pc-story",
            "scheduled_time": "2026-03-22T10:00:00+00:00",
            "user_id": fake_user.id,
        },
    ):
        response, status_code = studio_routes.studio_approve()

    payload = response.get_json()
    assert status_code == 400
    assert payload["success"] is False
    assert payload["error"] == "This format cannot be auto-published. Use Save Draft instead."
    assert store["scheduled_posts"] == []


def test_get_content_by_id_returns_wrapped_content_payload(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    store = {
        "processed_content": [
            {
                "id": "pc-1",
                "user_id": fake_user.id,
                "post_type": "post",
                "generated_text": "Body copy",
                "hook": "Hook",
                "hashtags": ["tag"],
                "status": "draft_only",
                "target_audience": "EN",
            }
        ]
    }

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(studio_routes, "_client", lambda: FakeClient(store))

    with app.test_request_context("/api/content/pc-1", method="GET"):
        response = studio_routes.get_content_by_id("pc-1")

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["content"]["id"] == "pc-1"
    assert payload["content"]["content_normalized"]["format"] == "post"


def test_schedule_content_rejects_draft_only_formats(monkeypatch):
    app = Flask(__name__)
    fake_user = FakeUser()
    store = {
        "processed_content": [
            {
                "id": "pc-story",
                "user_id": fake_user.id,
                "post_type": "story_sequence",
                "status": "draft_only",
            }
        ],
        "scheduled_posts": [],
    }

    _patch_user(monkeypatch, fake_user)
    monkeypatch.setattr(studio_routes, "_client", lambda: FakeClient(store))

    with app.test_request_context(
        "/api/content/pc-story/schedule",
        method="POST",
        json={"scheduled_time": "2026-03-22T10:00:00+00:00"},
    ):
        response, status_code = studio_routes.schedule_content("pc-story")

    payload = response.get_json()
    assert status_code == 400
    assert payload["success"] is False
    assert payload["error"] == "This format cannot be auto-published. Use Save Draft instead."
    assert store["scheduled_posts"] == []
