from flask import Flask, jsonify

import app.utils as app_utils


class FakeUser:
    def __init__(self, user_id: str = "user-123"):
        self.id = user_id
        self.is_authenticated = True


def _build_guarded_app():
    app = Flask(__name__)

    @app.route("/probe", methods=["GET", "POST"])
    @app_utils.api_login_required
    def probe():
        return jsonify({"success": True})

    return app


def test_same_origin_json_post_is_allowed(monkeypatch):
    app = _build_guarded_app()
    monkeypatch.setattr(app_utils, "current_user", FakeUser(), raising=False)

    with app.test_client() as client:
        response = client.post(
            "/probe",
            json={"hello": "world"},
            headers={
                "Origin": "http://localhost",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_cross_origin_json_post_is_rejected(monkeypatch):
    app = _build_guarded_app()
    monkeypatch.setattr(app_utils, "current_user", FakeUser(), raising=False)

    with app.test_client() as client:
        response = client.post(
            "/probe",
            json={"hello": "world"},
            headers={"Origin": "https://evil.example"},
        )

    payload = response.get_json()
    assert response.status_code == 403
    assert payload["success"] is False
    assert payload["code"] == "csrf_origin_mismatch"


def test_invalid_requested_with_header_is_rejected(monkeypatch):
    app = _build_guarded_app()
    monkeypatch.setattr(app_utils, "current_user", FakeUser(), raising=False)

    with app.test_client() as client:
        response = client.post(
            "/probe",
            json={"hello": "world"},
            headers={"X-Requested-With": "NotAjax"},
        )

    payload = response.get_json()
    assert response.status_code == 403
    assert payload["success"] is False
    assert payload["code"] == "csrf_origin_mismatch"
