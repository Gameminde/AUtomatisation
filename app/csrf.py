"""CSRF helpers with Flask-WTF support and a local fallback."""

from __future__ import annotations

import hmac
import secrets
from typing import Callable

from flask import Blueprint, current_app, request, session
from itsdangerous import BadSignature, URLSafeTimedSerializer

try:
    from flask_wtf.csrf import CSRFError, CSRFProtect as _FlaskWtfCSRFProtect, generate_csrf, validate_csrf
except ImportError:
    _FlaskWtfCSRFProtect = None

    class CSRFError(ValueError):
        """Fallback CSRF error when Flask-WTF is unavailable."""

        def __init__(self, description: str = "CSRF token is missing or invalid."):
            super().__init__(description)
            self.description = description


    def _serializer() -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(current_app.secret_key, salt="content-factory-csrf")


    def generate_csrf() -> str:
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return _serializer().dumps(token)


    def validate_csrf(data: str | None, time_limit: int = 3600) -> None:
        expected = session.get("_csrf_token")
        if not expected:
            raise CSRFError("CSRF session token is missing.")
        if not data:
            raise CSRFError("CSRF token is missing.")
        try:
            candidate = _serializer().loads(str(data), max_age=time_limit)
        except BadSignature as exc:
            raise CSRFError("CSRF token is invalid.") from exc
        if not hmac.compare_digest(str(candidate), str(expected)):
            raise CSRFError("CSRF token is invalid.")


    class CSRFProtect:
        """Small fallback wrapper that mirrors the Flask-WTF interface we need."""

        def __init__(self):
            self._exempt_blueprints: set[str] = set()
            self._exempt_views: set[Callable] = set()

        def init_app(self, app) -> None:
            app.jinja_env.globals.setdefault("csrf_token", generate_csrf)

            @app.before_request
            def _protect_request():
                if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
                    return None
                if request.blueprint in self._exempt_blueprints:
                    return None
                endpoint = request.endpoint or ""
                view = current_app.view_functions.get(endpoint)
                if view in self._exempt_views:
                    return None
                token = (
                    request.form.get("csrf_token")
                    or request.headers.get("X-CSRFToken")
                    or request.headers.get("X-CSRF-Token")
                )
                validate_csrf(token)
                return None

        def exempt(self, obj):
            if isinstance(obj, Blueprint):
                self._exempt_blueprints.add(obj.name)
                return obj
            self._exempt_views.add(obj)
            return obj

else:

    class CSRFProtect(_FlaskWtfCSRFProtect):
        """Flask-WTF CSRFProtect with the token helper exposed to Jinja."""

        def init_app(self, app) -> None:
            super().init_app(app)
            app.jinja_env.globals.setdefault("csrf_token", generate_csrf)
