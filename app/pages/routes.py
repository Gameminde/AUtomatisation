"""Pages management API routes — full tenant isolation via user_id scoping."""

from flask import Blueprint, jsonify, request
from flask_login import current_user

import config
from app.utils import api_login_required

logger = config.get_logger("pages")

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/api/pages", methods=["GET"])
@api_login_required
def get_pages():
    try:
        client = config.get_supabase_client()
        result = (
            client.table("managed_pages")
            .select("*")
            .eq("user_id", current_user.id)
            .execute()
        )
        return jsonify({"pages": result.data or []})
    except Exception as e:
        logger.error("Error fetching pages: %s", e)
        return jsonify({"error": str(e)}), 500


@pages_bp.route("/api/pages", methods=["POST"])
@api_login_required
def add_page():
    try:
        data = request.json or {}
        client = config.get_supabase_client()
        page_data = {
            "user_id": current_user.id,
            "page_id": data.get("page_id"),
            "page_name": data.get("page_name", "My Page"),
            "access_token": data.get("access_token"),
            "posts_per_day": data.get("posts_per_day", 3),
            "language": data.get("language", "ar"),
            "status": "active",
        }
        if data.get("posting_times"):
            page_data["posting_times"] = data["posting_times"]
        result = client.table("managed_pages").upsert(page_data).execute()
        return jsonify({"success": True, "page": result.data[0] if result.data else {}})
    except Exception as e:
        logger.error("Error adding page: %s", e)
        return jsonify({"error": str(e)}), 500


@pages_bp.route("/api/pages/<page_id>", methods=["PUT"])
@api_login_required
def update_page(page_id: str):
    try:
        data = request.json or {}
        client = config.get_supabase_client()
        update_data = {}
        for field in ["page_name", "posts_per_day", "posting_times", "language", "status"]:
            if field in data:
                update_data[field] = data[field]
        result = (
            client.table("managed_pages")
            .update(update_data)
            .eq("page_id", page_id)
            .eq("user_id", current_user.id)
            .execute()
        )
        return jsonify({"success": True, "page": result.data[0] if result.data else {}})
    except Exception as e:
        logger.error("Error updating page: %s", e)
        return jsonify({"error": str(e)}), 500


@pages_bp.route("/api/pages/<page_id>", methods=["DELETE"])
@api_login_required
def delete_page(page_id: str):
    try:
        client = config.get_supabase_client()
        client.table("managed_pages").delete().eq("page_id", page_id).eq("user_id", current_user.id).execute()
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Error deleting page: %s", e)
        return jsonify({"error": str(e)}), 500
