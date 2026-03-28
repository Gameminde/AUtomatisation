"""Pages management API routes — full tenant isolation via user_id scoping."""

from flask import Blueprint, jsonify, request
from flask_login import current_user

import config
from app.utils import api_login_required, get_managed_pages_for_user, save_fb_page_for_user

logger = config.get_logger("pages")

pages_bp = Blueprint("pages", __name__)


def load_pages_payload(user_id: str) -> dict:
    pages = get_managed_pages_for_user(user_id)
    return {
        "success": True,
        "pages": [
            {
                "page_id": row.get("page_id"),
                "page_name": row.get("page_name"),
                "instagram_account_id": row.get("instagram_account_id"),
                "posts_per_day": row.get("posts_per_day"),
                "posting_times": row.get("posting_times"),
                "language": row.get("language"),
                "status": row.get("status"),
                "last_synced_at": row.get("last_synced_at"),
            }
            for row in pages
        ],
    }


@pages_bp.route("/api/pages", methods=["GET"])
@api_login_required
def get_pages():
    try:
        return jsonify(load_pages_payload(current_user.id))
    except Exception as e:
        logger.error("Error fetching pages: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@pages_bp.route("/api/pages", methods=["POST"])
@api_login_required
def add_page():
    try:
        data = request.json or {}
        if not str(data.get("page_id") or "").strip():
            return jsonify({"success": False, "error": "page_id required"}), 400

        token_value = data.get("access_token") if "access_token" in data else None
        if not save_fb_page_for_user(
            user_id=current_user.id,
            page_id=str(data.get("page_id") or "").strip(),
            page_name=str(data.get("page_name") or "My Page").strip() or "My Page",
            page_token=None if token_value is None else str(token_value),
            instagram_account_id=str(data.get("instagram_account_id") or "").strip(),
            posts_per_day=data.get("posts_per_day", 3),
            posting_times=data.get("posting_times"),
            language=data.get("language", "en"),
        ):
            return jsonify({"success": False, "error": "Could not save page"}), 500

        pages = load_pages_payload(current_user.id)["pages"]
        page = next(
            (
                row
                for row in pages
                if str(row.get("page_id") or "").strip() == str(data.get("page_id") or "").strip()
            ),
            {},
        )
        return jsonify({"success": True, "page": page})
    except Exception as e:
        logger.error("Error adding page: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@pages_bp.route("/api/pages/<page_id>", methods=["PUT"])
@api_login_required
def update_page(page_id: str):
    try:
        data = request.json or {}
        client = config.get_database_client()
        update_data = {}
        for field in ["page_name", "posts_per_day", "posting_times", "language", "status"]:
            if field in data:
                update_data[field] = data[field]
        if not update_data:
            return jsonify({"success": False, "error": "No fields to update"}), 400

        existing_pages = get_managed_pages_for_user(current_user.id, client=client)
        current_page = next(
            (row for row in existing_pages if str(row.get("page_id") or "").strip() == str(page_id).strip()),
            None,
        )
        if not current_page:
            return jsonify({"success": False, "error": "Page not found"}), 404

        if any(field in update_data for field in ["page_name", "posts_per_day", "posting_times", "language", "status"]):
            saved = save_fb_page_for_user(
                user_id=current_user.id,
                page_id=page_id,
                page_name=str(update_data.get("page_name") or current_page.get("page_name") or "My Page").strip() or "My Page",
                page_token=None,
                instagram_account_id=str(current_page.get("instagram_account_id") or "").strip(),
                posts_per_day=update_data.get("posts_per_day", current_page.get("posts_per_day")),
                posting_times=update_data.get("posting_times", current_page.get("posting_times")),
                language=update_data.get("language", current_page.get("language")),
                status=update_data.get("status", current_page.get("status", "inactive")),
            )
            if not saved:
                return jsonify({"success": False, "error": "Could not update page"}), 500

        refreshed_page = next(
            (
                row
                for row in load_pages_payload(current_user.id)["pages"]
                if str(row.get("page_id") or "").strip() == str(page_id).strip()
            ),
            None,
        )
        return jsonify({"success": True, "page": refreshed_page or {}})
    except Exception as e:
        logger.error("Error updating page: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@pages_bp.route("/api/pages/<page_id>", methods=["DELETE"])
@api_login_required
def delete_page(page_id: str):
    try:
        client = config.get_database_client()
        client.table("managed_pages").delete().eq("page_id", page_id).eq("user_id", current_user.id).execute()
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Error deleting page: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500
