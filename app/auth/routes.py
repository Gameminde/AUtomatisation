from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
import bcrypt

import config
from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _get_db():
    return config.get_supabase_client()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.page_dashboard"))

    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        try:
            client = _get_db()
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
                    user = User(user_data["id"], user_data["email"])
                    login_user(user, remember=True)
                    next_page = request.args.get("next")
                    return redirect(next_page or url_for("web.page_dashboard"))
        except Exception as exc:
            config.get_logger("auth").error("Login error: %s", exc)

        error = "invalid_credentials"

    return render_template("auth/login.html", error=error)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("web.page_dashboard"))

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
            client = _get_db()

            code_result = (
                client.table("activation_codes")
                .select("id, code, used")
                .eq("code", code)
                .eq("used", False)
                .execute()
            )
            if not code_result.data:
                error = "invalid_code"
                return render_template("auth/register.html", error=error)

            existing = (
                client.table("users").select("id").eq("email", email).execute()
            )
            if existing.data:
                error = "email_exists"
                return render_template("auth/register.html", error=error)

            password_hash = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            user_result = client.table("users").insert({
                "email": email,
                "password_hash": password_hash,
                "is_active": True,
            }).execute()

            if not user_result.data:
                error = "registration_failed"
                return render_template("auth/register.html", error=error)

            new_user = user_result.data[0]

            client.table("activation_codes").update({
                "used": True,
                "used_by": new_user["id"],
                "used_at": datetime.now(timezone.utc).isoformat(),
            }).eq("code", code).execute()

            user = User(new_user["id"], new_user["email"])
            login_user(user, remember=True)
            return redirect(url_for("web.page_dashboard"))

        except Exception as exc:
            config.get_logger("auth").error("Registration error: %s", exc)
            error = "server_error"

    return render_template("auth/register.html", error=error)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
