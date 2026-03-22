"""Authentication routes — login, register (via Gumroad code), logout.

Auth ALWAYS uses Supabase directly (service key) rather than config.get_supabase_client()
which may return a SQLite client in single-tenant mode.  The `users` and
`activation_codes` tables only exist in Supabase.
"""

import os
from datetime import datetime, timezone

import bcrypt
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

import config

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

logger = config.get_logger("auth")


def _get_supabase():
    """Always return the Supabase REST client (never SQLite)."""
    from supabase import create_client
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set. "
            "Auth requires Supabase — SQLite does not have a users table."
        )
    return create_client(url, key)


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
                    next_page = request.args.get("next")
                    return redirect(next_page or url_for("web.page_landing"))
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
            return redirect(url_for("onboarding.wizard"))

        except RuntimeError as exc:
            logger.error("Registration config error: %s", exc)
            error = "supabase_not_configured"
        except Exception as exc:
            logger.error("Registration error: %s", exc)
            error = "server_error"

    return render_template("auth/register.html", error=error)


# ── Logout ─────────────────────────────────────────────────────────────────

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
