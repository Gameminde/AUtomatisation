"""Authentication routes — login, register (via Gumroad code), logout.

Auth ALWAYS uses Supabase directly (service key) rather than config.get_database_client()
which may return a SQLite client in single-tenant mode.  The `users` and
`activation_codes` tables only exist in Supabase.
"""

import os
from datetime import datetime, timezone

import bcrypt
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

import config
from app.utils import seed_session_ui_language

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

logger = config.get_logger("auth")


def _get_supabase():
    """Always return the cached Supabase REST client (never SQLite).

    Auth tables (users, activation_codes) only exist in Supabase.
    Delegates to config.get_supabase_service_client() which maintains
    a process-level singleton so the client is created only once.
    """
    return config.get_supabase_service_client()


def _validate_license_payload(data: dict):
    """Shared public license-validation helper for pre-registration flows."""
    from license_validator import validate_license

    key = (data.get("license_key") or "").strip()
    platform = (data.get("platform") or "").strip() or None
    if not key:
        return {"valid": False, "reason": "No key provided"}, 400
    return validate_license(key, platform=platform), 200


# ── Login ──────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.page_landing"))

    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        try:
            client = _get_supabase()
            result = (
                client.table("users")
                .select("id, email, password_hash, is_active")
                .eq("email", email)
                .execute()
            )
            rows = result.data or []
            if rows:
                user_data = rows[0]
                if user_data.get("is_active") and bcrypt.checkpw(
                    password.encode("utf-8"),
                    user_data["password_hash"].encode("utf-8"),
                ):
                    from models import User
                    user = User(user_data["id"], user_data["email"])
                    login_user(user, remember=True)
                    seed_session_ui_language(user.id)
                    return redirect(url_for("web.page_dashboard"))
        except Exception as exc:
            logger.error("Login error: %s", exc)

        error = "invalid_credentials"

    return render_template("auth/login.html", error=error)


# ── Register ───────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("web.page_landing"))

    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        code = (request.form.get("code") or "").strip()

        if not email or not password or not code:
            error = "fields_required"
            return render_template("auth/register.html", error=error)

        if len(password) < 8:
            error = "password_too_short"
            return render_template("auth/register.html", error=error)

        try:
            client = _get_supabase()

            # Check email uniqueness before touching the activation code
            existing = client.table("users").select("id").eq("email", email).execute()
            if existing.data:
                error = "email_exists"
                return render_template("auth/register.html", error=error)

            # Atomically claim the activation code (test-and-set pattern).
            # A single UPDATE with WHERE used=false ensures no two concurrent requests
            # can both claim the same code.  If 0 rows are updated the code is invalid
            # or was already consumed by another request.
            claim_result = (
                client.table("activation_codes")
                .update({
                    "used": True,
                    "used_at": datetime.now(timezone.utc).isoformat(),
                })
                .eq("code", code)
                .eq("used", False)
                .execute()
            )
            if not claim_result.data:
                error = "invalid_code"
                return render_template("auth/register.html", error=error)

            claimed_code_id = claim_result.data[0]["id"]

            # Create user — if this fails we release the code so it can be retried
            password_hash = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            try:
                user_result = client.table("users").insert({
                    "email": email,
                    "password_hash": password_hash,
                    "is_active": True,
                }).execute()
            except Exception as insert_exc:
                # Release the activation code so the user can retry
                client.table("activation_codes").update({
                    "used": False,
                    "used_at": None,
                }).eq("id", claimed_code_id).execute()
                raise insert_exc

            if not user_result.data:
                client.table("activation_codes").update({
                    "used": False,
                    "used_at": None,
                }).eq("id", claimed_code_id).execute()
                error = "registration_failed"
                return render_template("auth/register.html", error=error)

            new_user = user_result.data[0]

            # Record which user consumed the code
            client.table("activation_codes").update({
                "used_by": new_user["id"],
            }).eq("id", claimed_code_id).execute()

            from models import User
            user = User(new_user["id"], new_user["email"])
            login_user(user, remember=True)
            seed_session_ui_language(user.id)
            return redirect(url_for("web.page_dashboard"))

        except RuntimeError as exc:
            logger.error("Registration config error: %s", exc)
            error = "supabase_not_configured"
        except Exception as exc:
            logger.error("Registration error: %s", exc)
            error = "server_error"

    return render_template("auth/register.html", error=error)


@auth_bp.route("/activate-license", methods=["POST"])
def activate_license():
    """
    Public auth-scoped license validation endpoint.

    This keeps the pre-registration activation flow available after /setup
    removal and gives future auth pages a stable, non-/setup endpoint.
    """
    try:
        payload, status = _validate_license_payload(request.get_json(force=True))
        return jsonify(payload), status
    except ImportError:
        return jsonify({"valid": False, "reason": "License module not available"}), 500
    except Exception as exc:
        logger.error("Auth license activation error: %s", exc)
        return jsonify({"valid": False, "reason": str(exc)}), 500


# ── Logout ─────────────────────────────────────────────────────────────────

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    from flask import session
    _ob_key = f"ob_done:{current_user.id}"
    session.pop(_ob_key, None)
    logout_user()
    return redirect(url_for("auth.login"))
