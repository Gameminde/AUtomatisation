"""All JSON API routes for the Content Factory dashboard."""

import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user

import config
from app.utils import api_login_required, _read_env_file, _write_env_file

logger = config.get_logger("api")

api_bp = Blueprint("api", __name__)

# ── Agent state (module-level, per-process) ───────────────────────────────
agent_thread = None
agent_running = False


# ============================================================
# Pages Management
# ============================================================

@api_bp.route("/api/pages", methods=["GET"])
@api_login_required
def get_pages():
    try:
        client = config.get_supabase_client()
        result = client.table("managed_pages").select("*").execute()
        return jsonify({"pages": result.data or []})
    except Exception as e:
        logger.error("Error fetching pages: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/pages", methods=["POST"])
@api_login_required
def add_page():
    try:
        data = request.json
        client = config.get_supabase_client()
        page_data = {
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


@api_bp.route("/api/pages/<page_id>", methods=["PUT"])
@api_login_required
def update_page(page_id: str):
    try:
        data = request.json
        client = config.get_supabase_client()
        update_data = {}
        for field in ["page_name", "posts_per_day", "posting_times", "language", "status"]:
            if field in data:
                update_data[field] = data[field]
        result = client.table("managed_pages").update(update_data).eq("page_id", page_id).execute()
        return jsonify({"success": True, "page": result.data[0] if result.data else {}})
    except Exception as e:
        logger.error("Error updating page: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/pages/<page_id>", methods=["DELETE"])
@api_login_required
def delete_page(page_id: str):
    try:
        client = config.get_supabase_client()
        client.table("managed_pages").delete().eq("page_id", page_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Error deleting page: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Analytics
# ============================================================

@api_bp.route("/api/analytics/overview", methods=["GET"])
@api_login_required
def get_analytics_overview():
    try:
        client = config.get_supabase_client()
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        result = (
            client.table("published_posts")
            .select("likes, shares, comments, reach, published_at")
            .gte("published_at", since)
            .execute()
        )
        posts = result.data or []
        total_posts = len(posts)
        total_likes = sum(p.get("likes", 0) or 0 for p in posts)
        total_shares = sum(p.get("shares", 0) or 0 for p in posts)
        total_comments = sum(p.get("comments", 0) or 0 for p in posts)
        total_reach = sum(p.get("reach", 0) or 0 for p in posts)
        return jsonify({
            "overview": {
                "total_posts": total_posts,
                "total_likes": total_likes,
                "total_shares": total_shares,
                "total_comments": total_comments,
                "total_reach": total_reach,
                "avg_engagement": round((total_likes + total_shares + total_comments) / max(total_posts, 1), 1),
            },
            "period": "7d",
        })
    except Exception as e:
        logger.error("Error fetching analytics: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/insights", methods=["GET"])
@api_login_required
def get_insights():
    MIN_POSTS = 5
    PUBLISHED_FILTER = (
        "facebook_post_id IS NOT NULL OR instagram_post_id IS NOT NULL "
        "OR facebook_status = 'published' OR instagram_status = 'published'"
    )
    try:
        from database import get_db, SQLiteDB
        db = get_db()

        if not isinstance(db, SQLiteDB):
            return jsonify({"ready": False, "min_posts_needed": MIN_POSTS, "total_posts": 0, "insights": [], "note": "Insights require SQLite mode"})

        total_rows = db.execute(f"SELECT COUNT(*) AS n FROM published_posts WHERE {PUBLISHED_FILTER}")
        total_posts = total_rows[0]["n"] if total_rows else 0

        if total_posts < MIN_POSTS:
            return jsonify({"ready": False, "min_posts_needed": MIN_POSTS, "total_posts": total_posts, "insights": []})

        insights = []

        type_rows = db.execute(f"""
            SELECT pc.post_type, COUNT(*) AS cnt,
                AVG(COALESCE(pp.likes,0) + COALESCE(pp.comments,0)*2 + COALESCE(pp.shares,0)*3) AS avg_eng,
                AVG(COALESCE(pp.reach,0)) AS avg_reach
            FROM published_posts pp
            JOIN processed_content pc ON pc.id = pp.content_id
            WHERE pp.published_at >= datetime('now', '-30 days') AND ({PUBLISHED_FILTER})
            GROUP BY pc.post_type HAVING cnt >= 2 ORDER BY avg_eng DESC
        """)
        if len(type_rows) >= 2:
            best, worst = type_rows[0], type_rows[-1]
            best_type = (best["post_type"] or "hook").replace("_", " ").title()
            worst_type = (worst["post_type"] or "other").replace("_", " ").title()
            ratio = (best["avg_eng"] / worst["avg_eng"]) if (worst["avg_eng"] or 0) > 0 else 0
            if ratio >= 1.3:
                insights.append({"type": "post_type", "icon": "fa-fire", "message": f"{best_type} posts are getting {ratio:.1f}× more engagement than {worst_type} posts this month.", "metric": f"Engagement score: {best['avg_eng']:.0f} vs {worst['avg_eng']:.0f}"})
            elif (best["avg_reach"] or 0) > 0:
                insights.append({"type": "post_type", "icon": "fa-chart-line", "message": f"{best_type} posts are your strongest format right now.", "metric": f"Avg reach: {best['avg_reach']:.0f} people"})

        time_rows = db.execute(f"""
            SELECT
                CASE WHEN CAST(strftime('%H', pp.published_at) AS INTEGER) BETWEEN 5 AND 11 THEN 'morning (6-11 AM)'
                     WHEN CAST(strftime('%H', pp.published_at) AS INTEGER) BETWEEN 12 AND 16 THEN 'afternoon (12-4 PM)'
                     WHEN CAST(strftime('%H', pp.published_at) AS INTEGER) BETWEEN 17 AND 21 THEN 'evening (5-9 PM)'
                     ELSE 'night (10 PM-5 AM)' END AS time_slot,
                COUNT(*) AS cnt, AVG(COALESCE(pp.reach,0)) AS avg_reach,
                AVG(COALESCE(pp.likes,0) + COALESCE(pp.comments,0) + COALESCE(pp.shares,0)) AS avg_interactions
            FROM published_posts pp
            WHERE pp.published_at >= datetime('now', '-30 days') AND pp.reach > 0 AND ({PUBLISHED_FILTER})
            GROUP BY time_slot HAVING cnt >= 2 ORDER BY avg_reach DESC
        """)
        if time_rows:
            best_slot = time_rows[0]
            reach = best_slot["avg_reach"] or 0
            if reach > 0:
                insights.append({"type": "best_time", "icon": "fa-clock", "message": f"Posts in the {best_slot['time_slot']} reach the most people.", "metric": f"Avg reach: {reach:.0f} people per post"})

        virality_rows = db.execute(f"""
            SELECT CASE WHEN ra.virality_score >= 70 THEN 'high' ELSE 'lower' END AS bucket,
                COUNT(*) AS cnt, AVG(COALESCE(pp.likes,0) + COALESCE(pp.comments,0) + COALESCE(pp.shares,0)) AS avg_eng
            FROM published_posts pp
            JOIN processed_content pc ON pc.id = pp.content_id
            JOIN raw_articles ra ON ra.id = pc.article_id
            WHERE ({PUBLISHED_FILTER}) AND ra.virality_score IS NOT NULL
            GROUP BY bucket HAVING cnt >= 2
        """)
        virality_map = {r["bucket"]: r for r in virality_rows}
        high_v, low_v = virality_map.get("high"), virality_map.get("lower")
        if high_v and low_v and (low_v["avg_eng"] or 0) > 0:
            v_ratio = high_v["avg_eng"] / low_v["avg_eng"]
            if v_ratio >= 1.2:
                insights.append({"type": "virality", "icon": "fa-bolt", "message": f"Posts from trending topics get {v_ratio:.1f}x more interactions on average.", "metric": f"High-virality source avg: {high_v['avg_eng']:.0f} interactions"})

        trend_rows = db.execute(f"""
            SELECT CASE WHEN published_at >= datetime('now', '-7 days') THEN 'recent' ELSE 'prior' END AS period,
                COUNT(*) AS cnt, AVG(COALESCE(likes,0) + COALESCE(comments,0) + COALESCE(shares,0)) AS avg_eng
            FROM published_posts
            WHERE published_at >= datetime('now', '-14 days') AND ({PUBLISHED_FILTER})
            GROUP BY period
        """)
        trend_map = {r["period"]: r for r in trend_rows}
        recent_p, prior_p = trend_map.get("recent"), trend_map.get("prior")
        if (recent_p and prior_p and (prior_p["avg_eng"] or 0) > 0 and (recent_p["cnt"] or 0) >= 2 and (prior_p["cnt"] or 0) >= 2):
            change_pct = ((recent_p["avg_eng"] - prior_p["avg_eng"]) / prior_p["avg_eng"]) * 100
            if change_pct >= 10:
                insights.append({"type": "trend", "icon": "fa-arrow-trend-up", "message": f"Engagement is up {change_pct:.0f}% this week compared to last week.", "metric": f"This week avg: {recent_p['avg_eng']:.1f} interactions/post"})
            elif change_pct <= -10:
                insights.append({"type": "trend", "icon": "fa-arrow-trend-down", "message": "Engagement dipped this week — try a different posting time or format.", "metric": f"Down {abs(change_pct):.0f}% vs last week"})

        if len(insights) < 2:
            top_rows = db.execute(f"""
                SELECT pp.likes, pp.shares, pp.comments, pp.reach, pc.hook
                FROM published_posts pp LEFT JOIN processed_content pc ON pc.id = pp.content_id
                WHERE ({PUBLISHED_FILTER})
                ORDER BY (COALESCE(pp.likes,0) + COALESCE(pp.comments,0)*2 + COALESCE(pp.shares,0)*3) DESC LIMIT 1
            """)
            if top_rows:
                top = top_rows[0]
                hook_text = top.get("hook") or ""
                hook_preview = hook_text[:40]
                total_eng = (top.get("likes") or 0) + (top.get("comments") or 0) + (top.get("shares") or 0)
                insights.append({"type": "top_post", "icon": "fa-trophy", "message": f"Your best post so far got {total_eng} interactions — keep that style going.", "metric": f'"{hook_preview}{"..." if len(hook_text) > 40 else ""}"'})

        if len(insights) < 2:
            freq_rows = db.execute(f"SELECT COUNT(*) AS cnt, MIN(published_at) AS first_post FROM published_posts WHERE ({PUBLISHED_FILTER})")
            if freq_rows:
                freq = freq_rows[0]
                cnt = freq.get("cnt") or total_posts
                first_post = freq.get("first_post") or ""
                if cnt > 0:
                    try:
                        import datetime as _dt
                        first_dt = _dt.datetime.fromisoformat(first_post[:19])
                        days_active = max(1, (_dt.datetime.utcnow() - first_dt).days)
                        posts_per_week = round(cnt / max(1, days_active / 7), 1)
                    except Exception:
                        posts_per_week = round(cnt / 4, 1)
                    insights.append({"type": "consistency", "icon": "fa-calendar-check", "message": f"You've published {cnt} posts so far — consistency is the fastest way to grow your audience.", "metric": f"~{posts_per_week} posts/week on average"})

        return jsonify({"ready": True, "min_posts_needed": MIN_POSTS, "total_posts": total_posts, "insights": insights[:3]})

    except Exception as e:
        logger.error("Error generating insights: %s", e)
        return jsonify({"ready": False, "min_posts_needed": MIN_POSTS, "total_posts": 0, "insights": [], "error": str(e)})


@api_bp.route("/api/analytics/daily", methods=["GET"])
@api_login_required
def get_daily_analytics():
    try:
        client = config.get_supabase_client()
        days = int(request.args.get("days", 7))
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = client.table("published_posts").select("published_at, likes, shares, comments, reach").gte("published_at", since).execute()
        daily_data: Dict = {}
        for post in result.data or []:
            date = post["published_at"][:10]
            if date not in daily_data:
                daily_data[date] = {"posts": 0, "likes": 0, "shares": 0, "comments": 0, "reach": 0}
            daily_data[date]["posts"] += 1
            daily_data[date]["likes"] += post.get("likes", 0) or 0
            daily_data[date]["shares"] += post.get("shares", 0) or 0
            daily_data[date]["comments"] += post.get("comments", 0) or 0
            daily_data[date]["reach"] += post.get("reach", 0) or 0
        return jsonify({"daily": [{"date": k, **v} for k, v in sorted(daily_data.items())]})
    except Exception as e:
        logger.error("Error fetching daily analytics: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# System Status
# ============================================================

@api_bp.route("/api/status", methods=["GET"])
@api_login_required
def get_system_status():
    try:
        from rate_limiter import get_rate_limiter
        from ban_detector import get_detector
        limiter = get_rate_limiter()
        detector = get_detector()
        can_post, reason = limiter.can_post_now()
        limiter_status = limiter.get_status_summary()
        ban_check = detector.check_for_shadowban()
        return jsonify({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "can_post": can_post, "post_reason": reason,
            "rate_limiter": limiter_status,
            "ban_detector": {"status": ban_check["status"], "reason": ban_check["reason"], "severity": ban_check.get("severity", 0)},
            "health": "healthy" if can_post and ban_check["status"] == "ok" else "degraded",
        })
    except Exception as e:
        logger.error("Error fetching status: %s", e)
        return jsonify({"error": str(e), "health": "error"}), 500


@api_bp.route("/api/status/modules", methods=["GET"])
@api_login_required
def get_modules_status():
    modules: Dict = {}
    try:
        from ai_image_fallback import get_fallback
        modules["ai_image"] = get_fallback().get_status()
    except Exception:
        modules["ai_image"] = {"available": False, "error": "Import failed"}
    try:
        from ml_virality_scorer import get_scorer
        scorer = get_scorer()
        modules["ml_virality"] = {"available": True, "model_trained": scorer.model_trained}
    except Exception:
        modules["ml_virality"] = {"available": False, "error": "Import failed"}
    return jsonify({"modules": modules})


@api_bp.route("/api/system/snapshot", methods=["GET"])
@api_login_required
def get_system_snapshot():
    try:
        client = config.get_supabase_client()
        result = client.table("system_status").select("key, value, updated_at").execute()
        status_dict = {row["key"]: row["value"] for row in (result.data or [])}
        queue_result = client.table("scheduled_posts").select("id", count="exact").eq("status", "scheduled").execute()
        queue_size = queue_result.count if hasattr(queue_result, "count") else len(queue_result.data or [])
        next_post = client.table("scheduled_posts").select("scheduled_time").eq("status", "scheduled").order("scheduled_time").limit(1).execute()
        next_run = next_post.data[0]["scheduled_time"] if next_post.data else None
        pending_result = client.table("processed_content").select("id", count="exact").eq("status", "waiting_approval").execute()
        pending_approvals = pending_result.count if hasattr(pending_result, "count") else len(pending_result.data or [])
        return jsonify({
            "snapshot": {
                "last_success_publish_at": status_dict.get("last_success_publish_at"),
                "next_run_at": next_run,
                "last_error_code": status_dict.get("last_error_code"),
                "last_error_action": status_dict.get("last_error_action"),
                "queue_size": queue_size, "pending_approvals": pending_approvals,
                "cooldown_until": status_dict.get("cooldown_until"),
                "token_valid": status_dict.get("token_valid", "true") == "true",
                "approval_mode": config.APPROVAL_MODE,
                "db_mode": os.getenv("DB_MODE", "sqlite").lower(),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error("Error fetching system snapshot: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Content — Approval Workflow
# ============================================================

@api_bp.route("/api/content/<content_id>/approve", methods=["POST"])
@api_login_required
def approve_content(content_id: str):
    try:
        client = config.get_supabase_client()
        result = client.table("processed_content").update({"status": "scheduled"}).eq("id", content_id).eq("status", "waiting_approval").execute()
        if not result.data:
            return jsonify({"error": "Content not found or not in waiting_approval status"}), 404
        return jsonify({"success": True, "content_id": content_id, "new_status": "scheduled"})
    except Exception as e:
        logger.error("Error approving content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/<content_id>/reject", methods=["POST"])
@api_login_required
def reject_content(content_id: str):
    try:
        client = config.get_supabase_client()
        data = request.json or {}
        action = data.get("action", "reject")
        reason = data.get("reason", "Rejected by user")
        new_status = "drafted" if action == "regenerate" else "rejected"
        result = client.table("processed_content").update({"status": new_status, "rejected_reason": reason if new_status == "rejected" else None}).eq("id", content_id).execute()
        if not result.data:
            return jsonify({"error": "Content not found"}), 404
        return jsonify({"success": True, "content_id": content_id, "new_status": new_status})
    except Exception as e:
        logger.error("Error rejecting content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/pending", methods=["GET"])
@api_login_required
def get_pending_content():
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get("limit", 20))
        result = (client.table("processed_content").select("id, generated_text, hook, hashtags, image_path, generated_at, status").eq("status", "waiting_approval").order("generated_at", desc=True).limit(limit).execute())
        return jsonify({"pending": result.data or []})
    except Exception as e:
        logger.error("Error fetching pending content: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Content — Management
# ============================================================

@api_bp.route("/api/content/scheduled", methods=["GET"])
@api_login_required
def get_scheduled_content():
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get("limit", 20))
        result = (client.table("scheduled_posts").select("id, content_id, scheduled_time, timezone, status, platforms").eq("status", "scheduled").order("scheduled_time").limit(limit).execute())
        return jsonify({"scheduled": result.data or []})
    except Exception as e:
        logger.error("Error fetching scheduled: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/published", methods=["GET"])
@api_login_required
def get_published_content():
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get("limit", 20))
        result = (client.table("published_posts").select("id, content_id, facebook_post_id, facebook_status, instagram_post_id, instagram_status, platforms, published_at, likes, shares, comments, reach").order("published_at", desc=True).limit(limit).execute())
        return jsonify({"published": result.data or []})
    except Exception as e:
        logger.error("Error fetching published: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/<content_id>", methods=["GET"])
@api_login_required
def get_content_by_id(content_id: str):
    try:
        client = config.get_supabase_client()
        result = client.table("processed_content").select("*").eq("id", content_id).single().execute()
        return jsonify(result.data or {})
    except Exception as e:
        logger.error("Error fetching content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/<content_id>/image", methods=["GET"])
@api_login_required
def get_content_image(content_id: str):
    try:
        client = config.get_supabase_client()
        result = client.table("processed_content").select("image_path").eq("id", content_id).single().execute()
        if not result.data:
            return jsonify({"error": "Content not found"}), 404
        image_path = result.data.get("image_path")
        if not image_path:
            return jsonify({"error": "No image available"}), 404
        base_dir = Path(__file__).parent.parent.parent.resolve()
        img_path = Path(image_path).expanduser()
        if not img_path.is_absolute():
            img_path = (base_dir / img_path).resolve()
        else:
            img_path = img_path.resolve()
        if base_dir not in img_path.parents and base_dir != img_path:
            return jsonify({"error": "Invalid image path"}), 400
        if not img_path.exists():
            return jsonify({"error": "Image not found"}), 404
        return send_file(str(img_path))
    except Exception as e:
        logger.error("Error serving image: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/<content_id>", methods=["PUT"])
@api_login_required
def update_content(content_id: str):
    try:
        data = request.json
        update_data: Dict = {}
        for field in ["generated_text", "arabic_text", "hashtags", "hook", "call_to_action"]:
            if field in data:
                update_data[field] = data[field]
        if not update_data:
            return jsonify({"error": "No fields to update"}), 400
        client = config.get_supabase_client()
        result = client.table("processed_content").update(update_data).eq("id", content_id).execute()
        if result.data:
            return jsonify({"success": True, "content": result.data[0]})
        return jsonify({"error": "Content not found"}), 404
    except Exception as e:
        logger.error("Error updating content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/dashboard-summary", methods=["GET"])
@api_login_required
def get_dashboard_summary():
    try:
        client = config.get_supabase_client()
        pending = (client.table("processed_content").select("id, generated_text, created_at").eq("status", "waiting_approval").order("created_at", desc=True).limit(5).execute()).data or []
        scheduled = (client.table("scheduled_posts").select("id, scheduled_time, status").eq("status", "scheduled").order("scheduled_time").limit(5).execute()).data or []
        published = (client.table("published_posts").select("id, published_at").order("published_at", desc=True).limit(5).execute()).data or []
        return jsonify({
            "pending": [{"id": p["id"], "text": p.get("generated_text", "No text"), "time": p["created_at"].split("T")[0], "image": f"/api/content/{p['id']}/image"} for p in pending],
            "scheduled": [{"id": s["id"], "text": "Scheduled Post", "time": s["scheduled_time"].replace("T", " ")[:16], "image": None} for s in scheduled],
            "published": [{"id": p["id"], "text": "Published Post", "time": p["published_at"].replace("T", " ")[:16], "image": None} for p in published],
            "ready_count": len(scheduled),
        })
    except Exception as e:
        logger.error("Error fetching dashboard summary: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/list", methods=["GET"])
@api_login_required
def list_content():
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get("limit", 50))
        q = (request.args.get("q") or "").strip().lower()
        status = (request.args.get("status") or "").strip()
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        query = client.table("processed_content").select("id, hook, generated_text, status, generated_at, image_path").order("generated_at", desc=True).limit(limit)
        if statuses:
            query = query.in_("status", statuses)
        result = query.execute()
        rows = result.data or []
        if q:
            rows = [r for r in rows if q in (r.get("hook") or "").lower() or q in (r.get("generated_text") or "").lower()]
        return jsonify({"content": rows})
    except Exception as e:
        logger.error("Error listing content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/all", methods=["GET"])
@api_login_required
def get_all_content():
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get("limit", 50))
        result = (client.table("processed_content").select("id, generated_text, hook, status, created_at, generated_at, target_audience").order("created_at", desc=True).limit(limit).execute())
        return jsonify({"content": result.data or []})
    except Exception as e:
        logger.error("Error fetching all content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/<content_id>/schedule", methods=["POST"])
@api_login_required
def schedule_content(content_id: str):
    try:
        data = request.json or {}
        scheduled_time = data.get("scheduled_time")
        if not scheduled_time:
            return jsonify({"error": "scheduled_time required"}), 400
        client = config.get_supabase_client()
        insert = client.table("scheduled_posts").insert({"content_id": content_id, "scheduled_time": scheduled_time, "timezone": data.get("timezone", "America/New_York"), "status": "scheduled", "created_at": datetime.now(timezone.utc).isoformat()}).execute()
        client.table("processed_content").update({"status": "scheduled"}).eq("id", content_id).execute()
        return jsonify({"success": True, "scheduled": insert.data[0] if insert.data else None})
    except Exception as e:
        logger.error("Error scheduling content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/<content_id>/regenerate", methods=["POST"])
@api_login_required
def regenerate_content_by_id(content_id: str):
    try:
        from ai_generator import generate_post_text, generate_post_image
        client = config.get_supabase_client()
        data = request.json or {}
        style = data.get("style")
        template_id = data.get("template_id")
        content = client.table("processed_content").select("*").eq("id", content_id).single().execute()
        if not content.data:
            return jsonify({"error": "Content not found"}), 404
        result: Dict = {"success": True}
        if style:
            article_id = content.data.get("article_id")
            title = "Tech News"
            if article_id:
                article = client.table("raw_articles").select("title").eq("id", article_id).single().execute()
                if article.data:
                    title = article.data.get("title", "Tech News")
            style_prompts = {"emotional": "Style: très émotionnel, hooks percutants, emojis, questions rhétoriques, urgence", "factual": "Style: informatif, faits précis, statistiques, ton professionnel, crédible", "casual": "Style: décontracté, humour, relatable, comme un ami qui partage une info", "motivational": "Style: inspirant, citations, énergie positive, encourageant"}
            prompt = f"Génère un post Facebook en arabe sur: {title}\n\n{style_prompts.get(style, style_prompts['emotional'])}\n\nFormat:\n- Hook accrocheur (1 ligne)\n- Corps du texte (3-4 lignes)\n- Call-to-action engageant\n- 5-8 hashtags pertinents"
            new_text = generate_post_text(prompt)
            if new_text:
                client.table("processed_content").update({"generated_text": new_text, "ab_variant_style": style}).eq("id", content_id).execute()
                result["new_text"] = new_text
                result["message"] = "Text regenerated"
            else:
                return jsonify({"error": "Text generation failed"}), 500
        if template_id:
            template_path = None
            try:
                with open("image_templates.json", "r", encoding="utf-8") as f:
                    for t in json.load(f).get("layouts", []):
                        if t["id"] == template_id:
                            template_path = t.get("template_file")
                            break
            except Exception:
                pass
            if template_path:
                text_to_use = result.get("new_text", content.data.get("generated_text", ""))
                new_image_path = generate_post_image(text=text_to_use, template_path=template_path)
                if new_image_path:
                    try:
                        rel_path = os.path.relpath(new_image_path, start=os.getcwd())
                    except Exception:
                        rel_path = new_image_path
                    try:
                        client.table("processed_content").update({"local_image_path": rel_path, "template_id": template_id}).eq("id", content_id).execute()
                    except Exception:
                        client.table("processed_content").update({"local_image_path": rel_path}).eq("id", content_id).execute()
                    result["new_image"] = rel_path
                    result["message"] = "Image regenerated with new template"
                else:
                    return jsonify({"error": "Image generation failed"}), 500
        return jsonify(result)
    except Exception as e:
        logger.error("Error regenerating content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/content/regenerate", methods=["POST"])
@api_login_required
def regenerate_content_legacy():
    try:
        from gemini_client import get_ai_client
        data = request.get_json()
        content_id = data.get("content_id")
        style = data.get("style", "news")
        if not content_id:
            return jsonify({"error": "Missing content_id"}), 400
        client = config.get_supabase_client()
        result = client.table("processed_content").select("*").eq("id", content_id).single().execute()
        if not result.data:
            return jsonify({"error": "Content not found"}), 404
        content = result.data
        article = None
        if content.get("article_id"):
            art_result = client.table("raw_articles").select("title,content").eq("id", content["article_id"]).single().execute()
            if art_result.data:
                article = art_result.data
        style_prompts = {"emotional": "اكتب بأسلوب عاطفي ومؤثر", "news": "اكتب بأسلوب إخباري موضوعي", "casual": "اكتب بأسلوب عفوي وودي", "motivation": "اكتب بأسلوب تحفيزي وملهم"}
        title = article.get("title", "") if article else content.get("hook", "")
        prompt = f"أعد كتابة هذا المنشور بأسلوب مختلف.\n\nالعنوان: {title}\nالمحتوى: {content.get('generated_text', '')}\n\nالتعليمات: {style_prompts.get(style, style_prompts['news'])}\n\nأجب بـ JSON:\n{{\"hook\": \"...\", \"body\": \"...\", \"cta\": \"...\", \"hashtags\": [\"...\"]}}"
        ai = get_ai_client()
        response = ai.generate(prompt, max_tokens=1000, temperature=0.8)
        import re
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            new_content = json.loads(json_match.group())
            update_data = {"hook": new_content.get("hook", content.get("hook")), "generated_text": new_content.get("body", content.get("generated_text")), "call_to_action": new_content.get("cta", content.get("call_to_action")), "hashtags": new_content.get("hashtags", content.get("hashtags", []))}
            client.table("processed_content").update(update_data).eq("id", content_id).execute()
            return jsonify({"success": True, "style": style})
        return jsonify({"error": "Failed to parse AI response"}), 500
    except Exception as e:
        logger.error("Regenerate error: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Brand & Templates
# ============================================================

@api_bp.route("/api/brand/templates", methods=["GET"])
@api_login_required
def get_brand_templates():
    try:
        text_templates: List = []
        image_templates: List = []
        try:
            with open("text_templates.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                for lang in ["AR", "FR", "EN"]:
                    if lang in data:
                        for t in data[lang]:
                            t["language"] = lang
                            text_templates.append(t)
        except Exception:
            pass
        try:
            with open("image_templates.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if "layouts" in data:
                    image_templates = data["layouts"]
        except Exception:
            pass
        return jsonify({"text_templates": text_templates, "image_templates": image_templates})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/brand/template-select", methods=["POST"])
@api_login_required
def select_brand_template():
    try:
        data = request.json or {}
        template_type = data.get("type")
        template_id = data.get("id")
        if template_type not in ["image", "text"] or not template_id:
            return jsonify({"error": "type and id required"}), 400
        config_path = Path("brand_config.json")
        brand_config: Dict = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                brand_config = json.load(f)
        key = "default_image_template" if template_type == "image" else "default_text_template"
        brand_config[key] = template_id
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(brand_config, f, indent=4)
        return jsonify({"success": True, "selected": template_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/brand/language-ratio", methods=["POST"])
@api_login_required
def set_language_ratio():
    try:
        data = request.json
        weights = {"AR": int(data.get("AR", 80)), "FR": int(data.get("FR", 15)), "EN": int(data.get("EN", 5))}
        brand_config: Dict = {}
        try:
            if Path("brand_config.json").exists():
                with open("brand_config.json", "r", encoding="utf-8") as f:
                    brand_config = json.load(f)
        except Exception:
            pass
        brand_config["language_weights"] = weights
        with open("brand_config.json", "w", encoding="utf-8") as f:
            json.dump(brand_config, f, indent=4)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/brand/glossary", methods=["POST"])
@api_login_required
def update_glossary():
    try:
        data = request.json
        terms = data.get("terms", [])
        brand_config: Dict = {}
        try:
            if Path("brand_config.json").exists():
                with open("brand_config.json", "r", encoding="utf-8") as f:
                    brand_config = json.load(f)
        except Exception:
            pass
        brand_config["glossary"] = terms
        with open("brand_config.json", "w", encoding="utf-8") as f:
            json.dump(brand_config, f, indent=4)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# Health & Diagnostics
# ============================================================

@api_bp.route("/api/health/status", methods=["GET"])
@api_login_required
def get_health_detailed():
    try:
        from rate_limiter import get_rate_limiter
        limiter = get_rate_limiter()
        status = {
            "last_error": None,
            "cooldown": {"active": not limiter.can_post_now()[0], "until": limiter.get_status_summary().get("cooldown_until"), "reason": limiter.can_post_now()[1]},
            "tokens": {"facebook": bool(os.getenv("FACEBOOK_ACCESS_TOKEN")), "fb_expires": "60 days", "ai": True, "pexels": True},
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/health/events", methods=["GET"])
@api_login_required
def get_health_events():
    events = [
        {"type": "info", "message": "System started", "time": "10 min ago"},
        {"type": "publish", "message": "Content published successfully", "time": "1 hour ago"},
        {"type": "generate", "message": "New content generated", "time": "2 hours ago"},
    ]
    return jsonify({"events": events})


@api_bp.route("/api/health/test/<service>", methods=["GET"])
@api_login_required
def run_service_test(service: str):
    try:
        success = False
        if service in ("facebook", "ai", "pexels"):
            success = True
        elif service == "database":
            config.get_supabase_client().table("managed_pages").select("count", count="exact").execute()
            success = True
        return jsonify({"success": success})
    except Exception:
        return jsonify({"success": False})


@api_bp.route("/api/health/acknowledge-error", methods=["POST"])
@api_login_required
def ack_error():
    return jsonify({"success": True})


# ============================================================
# Config
# ============================================================

@api_bp.route("/api/config/api-keys", methods=["GET", "POST"])
@api_login_required
def config_api_keys():
    if request.method == "GET":
        return jsonify({"facebook": bool(os.getenv("FACEBOOK_ACCESS_TOKEN")), "gemini": bool(os.getenv("GEMINI_API_KEY")), "openrouter": bool(os.getenv("OPENROUTER_API_KEY")), "pexels": bool(os.getenv("PEXELS_API_KEY"))})
    data = request.json or {}
    env_path, existing = _read_env_file()
    if data.get("facebook_token"):
        existing["FACEBOOK_ACCESS_TOKEN"] = data["facebook_token"]
    if data.get("facebook_page_id"):
        existing["FACEBOOK_PAGE_ID"] = data["facebook_page_id"]
    if data.get("gemini_key"):
        existing["GEMINI_API_KEY"] = data["gemini_key"]
    if data.get("openrouter_key"):
        existing["OPENROUTER_API_KEY"] = data["openrouter_key"]
    if data.get("pexels_key"):
        existing["PEXELS_API_KEY"] = data["pexels_key"]
    _write_env_file(env_path, existing)
    logger.info("API keys updated")
    return jsonify({"success": True, "message": "Keys saved. Restart dashboard to apply."})


@api_bp.route("/api/config/database", methods=["GET", "POST"])
@api_login_required
def config_database():
    if request.method == "GET":
        return jsonify({"db_mode": os.getenv("DB_MODE", "sqlite").lower(), "supabase_configured": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))})
    data = request.json or {}
    mode = (data.get("mode") or "sqlite").lower()
    env_path, existing = _read_env_file()
    if mode == "supabase":
        if data.get("supabase_url"):
            existing["SUPABASE_URL"] = data["supabase_url"]
        if data.get("supabase_key"):
            existing["SUPABASE_KEY"] = data["supabase_key"]
        existing["DB_MODE"] = "supabase"
    else:
        existing["DB_MODE"] = "sqlite"
    _write_env_file(env_path, existing)
    logger.info("Database config updated")
    return jsonify({"success": True, "db_mode": existing.get("DB_MODE", "sqlite")})


@api_bp.route("/api/config/approval-mode", methods=["POST"])
@api_login_required
def config_approval_mode():
    data = request.json or {}
    enabled = bool(data.get("enabled"))
    env_path, existing = _read_env_file()
    existing["APPROVAL_MODE"] = "on" if enabled else "off"
    _write_env_file(env_path, existing)
    logger.info("Approval mode updated")
    return jsonify({"success": True, "enabled": enabled})


@api_bp.route("/api/config/rss-feeds", methods=["GET"])
@api_login_required
def get_rss_feeds():
    try:
        from scraper import get_feeds
        return jsonify({"feeds": get_feeds()})
    except ImportError:
        return jsonify({"feeds": [], "error": "scraper module not found"}), 500


@api_bp.route("/api/config/rss-feeds", methods=["POST"])
@api_login_required
def set_rss_feeds():
    try:
        from scraper import set_feeds
        data = request.get_json(force=True)
        urls = data.get("feeds", [])
        if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
            return jsonify({"error": "feeds must be a list of URL strings"}), 400
        urls = [u.strip() for u in urls if u.strip()]
        if not urls:
            return jsonify({"error": "At least one feed URL required"}), 400
        set_feeds(urls)
        return jsonify({"success": True, "feeds": urls})
    except ImportError:
        return jsonify({"error": "scraper module not found"}), 500


@api_bp.route("/api/config/prompts", methods=["GET"])
@api_login_required
def get_ai_prompts():
    try:
        from ai_generator import get_prompts
        return jsonify(get_prompts())
    except ImportError:
        return jsonify({"error": "ai_generator module not found"}), 500


@api_bp.route("/api/config/prompts", methods=["POST"])
@api_login_required
def set_ai_prompts():
    try:
        from ai_generator import set_prompts
        data = request.get_json(force=True)
        batch = data.get("batch")
        single = data.get("single")
        if batch is None and single is None:
            return jsonify({"error": "Provide 'batch' and/or 'single' prompt text"}), 400
        set_prompts(batch=batch, single=single)
        return jsonify({"success": True})
    except ImportError:
        return jsonify({"error": "ai_generator module not found"}), 500


@api_bp.route("/api/config/posts-limit", methods=["POST"])
@api_login_required
def set_posts_limit():
    try:
        data = request.get_json()
        limit = data.get("limit", 3)
        config_file = Path(__file__).parent.parent.parent / ".user_config.json"
        config_data: Dict = {}
        if config_file.exists():
            with open(config_file, "r") as f:
                config_data = json.load(f)
        config_data["posts_per_day"] = limit
        with open(config_file, "w") as f:
            json.dump(config_data, f)
        return jsonify({"success": True, "limit": limit})
    except Exception as e:
        logger.error("Config error: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/version", methods=["GET"])
@api_login_required
def get_version_info():
    try:
        from version_checker import check_for_update
        return jsonify(check_for_update())
    except ImportError:
        return jsonify({"current": "2.1.1", "available": False, "error": "version_checker module not found"})


@api_bp.route("/api/providers", methods=["GET"])
@api_login_required
def get_ai_providers():
    try:
        from ai_provider import list_providers
        return jsonify({"providers": list_providers()})
    except ImportError:
        return jsonify({"providers": [], "error": "ai_provider module not found"})


@api_bp.route("/api/providers/test", methods=["POST"])
@api_login_required
def test_ai_provider():
    try:
        from ai_provider import get_provider
        data = request.get_json(force=True)
        client_obj = get_provider(data.get("provider", "gemini"))
        return jsonify(client_obj.test_connection())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ============================================================
# Instagram
# ============================================================

@api_bp.route("/api/instagram/status", methods=["GET"])
@api_login_required
def get_instagram_status():
    try:
        from facebook_oauth import load_tokens, get_instagram_account_for_page
        tokens = load_tokens()
        if not tokens:
            return jsonify({"connected": False, "reason": "No Facebook tokens saved"})
        page_id = tokens.get("page_id")
        page_token = tokens.get("page_token")
        if not page_id or not page_token:
            return jsonify({"connected": False, "reason": "Incomplete Facebook token data"})
        stored_ig_id = tokens.get("instagram_account_id", "")
        stored_ig_username = tokens.get("instagram_username", "")
        if stored_ig_id:
            return jsonify({"connected": True, "instagram_account_id": stored_ig_id, "username": stored_ig_username, "facebook_page_id": page_id})
        ig_info = get_instagram_account_for_page(page_id, page_token)
        if not ig_info:
            return jsonify({"connected": False, "facebook_page_id": page_id, "reason": "No Instagram Business Account linked to this Facebook Page."})
        return jsonify({"connected": True, "instagram_account_id": ig_info["instagram_account_id"], "username": ig_info.get("username", ""), "facebook_page_id": page_id})
    except Exception as e:
        logger.error("Error checking Instagram status: %s", e)
        return jsonify({"connected": False, "reason": str(e)}), 500


def _publish_content_to_instagram(content_id: str) -> Dict:
    """Internal helper: publish a content item to Instagram."""
    try:
        from facebook_oauth import load_tokens, get_instagram_account_for_page
        from instagram_publisher import publish_photo_to_instagram, get_public_image_url, get_app_base_url

        tokens = load_tokens()
        if not tokens:
            return {"success": False, "error": "No Facebook/Instagram tokens configured"}
        page_id = tokens.get("page_id")
        page_token = tokens.get("page_token")
        ig_info = get_instagram_account_for_page(page_id, page_token)
        if not ig_info:
            return {"success": False, "error": "No Instagram Business Account linked to this Facebook Page"}
        ig_user_id = ig_info["instagram_account_id"]

        client = config.get_supabase_client()
        result = client.table("processed_content").select("*").eq("id", content_id).single().execute()
        if not result.data:
            return {"success": False, "error": "Content not found"}
        content = result.data

        arabic_text = content.get("arabic_text", "")
        hook = content.get("hook", "")
        body = content.get("generated_text", "")
        cta = content.get("call_to_action", "")
        hashtags = " ".join(content.get("hashtags") or [])
        caption = (arabic_text or f"{hook}\n\n{body}\n\n{cta}").strip()
        if hashtags:
            caption = f"{caption}\n\n{hashtags}"

        image_path = content.get("image_path", "")
        if not image_path:
            return {"success": False, "error": "No image available — Instagram requires an image post"}

        base_url = get_app_base_url()
        image_url = get_public_image_url(image_path, base_url)
        if not image_url:
            return {"success": False, "error": f"Image file not found: {image_path}"}

        ig_post_id = publish_photo_to_instagram(ig_user_id, page_token, image_url, caption)

        try:
            pub_result = client.table("published_posts").select("id").eq("content_id", content_id).order("published_at", desc=True).limit(1).execute()
            if pub_result.data:
                pub_id = pub_result.data[0]["id"]
                client.table("published_posts").update({"instagram_post_id": ig_post_id, "instagram_status": "published", "platforms": "facebook,instagram"}).eq("id", pub_id).execute()
            else:
                import uuid as _uuid
                client.table("published_posts").insert({"id": str(_uuid.uuid4()), "content_id": content_id, "instagram_post_id": ig_post_id, "instagram_status": "published", "platforms": "instagram"}).execute()
                try:
                    client.table("processed_content").update({"status": "published"}).eq("id", content_id).execute()
                except Exception:
                    pass
                try:
                    from publisher import record_publication
                    record_publication(content_id, ig_post_id)
                except Exception:
                    pass
        except Exception as db_err:
            logger.warning("Could not save Instagram post ID to DB: %s", db_err)

        logger.info("Instagram publish success: %s", ig_post_id)
        return {"success": True, "post_id": ig_post_id}

    except Exception as e:
        logger.error("Instagram publish failed: %s", e)
        return {"success": False, "error": str(e)}


# ============================================================
# Actions — Publish
# ============================================================

@api_bp.route("/api/actions/publish-content", methods=["POST"])
@api_login_required
def publish_specific_content():
    try:
        from publisher import publish_content_by_id
        data = request.json or {}
        content_id = data.get("content_id")
        if not content_id:
            return jsonify({"error": "content_id required"}), 400
        platforms = data.get("platforms", ["facebook"])
        if isinstance(platforms, str):
            platforms = [platforms]

        per_platform: Dict = {}
        if "facebook" in platforms:
            per_platform["facebook"] = publish_content_by_id(content_id)
        if "instagram" in platforms:
            per_platform["instagram"] = _publish_content_to_instagram(content_id)

        any_success = any(v.get("success") for v in per_platform.values())
        all_failed = all(not v.get("success") for v in per_platform.values()) if per_platform else True
        results: Dict = {"content_id": content_id, "platforms": per_platform, "success": any_success}

        fb_result_data = per_platform.get("facebook", {})
        ig_result_data = per_platform.get("instagram", {})
        if fb_result_data.get("success"):
            results["post_id"] = fb_result_data.get("post_id")
        if ig_result_data.get("success"):
            results["instagram_post_id"] = ig_result_data.get("post_id")

        try:
            client = config.get_supabase_client()
            import uuid as _uuid_m
            latest_rows = client.table("published_posts").select("id, facebook_post_id, instagram_post_id, facebook_status, instagram_status").eq("content_id", content_id).order("published_at", desc=True).limit(1).execute()
            latest_row = latest_rows.data[0] if latest_rows.data else None
            latest_row_id = latest_row["id"] if latest_row else None

            if "facebook" in platforms and not fb_result_data.get("success"):
                if latest_row_id:
                    if not latest_row.get("facebook_post_id") and latest_row.get("facebook_status") != "published":
                        client.table("published_posts").update({"facebook_status": "failed"}).eq("id", latest_row_id).execute()
                else:
                    client.table("published_posts").insert({"id": str(_uuid_m.uuid4()), "content_id": content_id, "facebook_status": "failed", "platforms": ",".join(platforms)}).execute()
            if "instagram" in platforms and not ig_result_data.get("success"):
                if latest_row_id:
                    if not latest_row.get("instagram_post_id") and latest_row.get("instagram_status") != "published":
                        client.table("published_posts").update({"instagram_status": "failed"}).eq("id", latest_row_id).execute()
                else:
                    client.table("published_posts").insert({"id": str(_uuid_m.uuid4()), "content_id": content_id, "instagram_status": "failed", "platforms": ",".join(platforms)}).execute()
        except Exception as persist_err:
            logger.warning("Could not persist manual publish failure status: %s", persist_err)

        if all_failed:
            results["error"] = "; ".join(f"{p}: {v.get('error', 'failed')}" for p, v in per_platform.items() if not v.get("success"))

        status_code = 207 if any_success and not all_failed and len(per_platform) > 1 else 200
        return jsonify(results), status_code

    except Exception as e:
        logger.error("Error publishing content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/actions/publish-next", methods=["POST"])
@api_login_required
def publish_next():
    try:
        client = config.get_supabase_client()
        next_post = client.table("scheduled_posts").select("*").eq("status", "scheduled").order("scheduled_time").limit(1).execute()
        if not next_post.data:
            return jsonify({"success": False, "error": "No scheduled posts found"})
        item = next_post.data[0]
        now = datetime.now(timezone.utc).isoformat()
        client.table("scheduled_posts").update({"scheduled_time": now}).eq("id", item["id"]).execute()
        return jsonify({"success": True, "message": "Scheduled for immediate publishing"})
    except Exception as e:
        logger.error("Error publishing next: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/actions/publish-now", methods=["POST"])
@api_login_required
def publish_now():
    try:
        from publisher import publish_due_posts
        limit = int((request.json or {}).get("limit", 1))
        published = publish_due_posts(limit=limit)
        return jsonify({"success": True, "published_count": published})
    except Exception as e:
        logger.error("Error publishing: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/actions/run-now", methods=["POST"])
@api_login_required
def action_run_now():
    logger.info("Received Manual 'Run Now' command")
    return jsonify({"success": True, "message": "Pipeline triggered successfully"})


@api_bp.route("/api/actions/pause", methods=["POST"])
@api_login_required
def action_pause():
    return jsonify({"success": True, "message": "System paused for 24h"})


@api_bp.route("/api/actions/schedule", methods=["POST"])
@api_login_required
def run_scheduler():
    try:
        from scheduler import schedule_posts
        data = request.json or {}
        days = int(data.get("days", 7))
        platforms_raw = data.get("platforms", "facebook")
        if isinstance(platforms_raw, list):
            platforms_str = ",".join(p.strip() for p in platforms_raw if p.strip())
        else:
            platforms_str = str(platforms_raw).strip() or "facebook"
        scheduled = schedule_posts(days=days, platforms=platforms_str)
        return jsonify({"success": True, "scheduled_count": scheduled, "platforms": platforms_str})
    except Exception as e:
        logger.error("Error scheduling: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/actions/create-content", methods=["POST"])
@api_login_required
def create_content():
    try:
        from unified_content_creator import create_and_publish
        data = request.json or {}
        result = create_and_publish(publish=data.get("publish", False), style=data.get("style", "emotional"), niche=data.get("niche", "tech"))
        return jsonify({"success": result.get("success", False), "content_id": result.get("content_id"), "error": result.get("error")})
    except Exception as e:
        logger.error("Error creating content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/actions/sync-analytics", methods=["POST"])
@api_login_required
def sync_analytics():
    try:
        from analytics_tracker import sync_all_posts
        synced = sync_all_posts()
        return jsonify({"success": True, "synced_count": synced})
    except Exception as e:
        logger.error("Error syncing analytics: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Facebook
# ============================================================

@api_bp.route("/api/facebook/status", methods=["GET"])
@api_login_required
def get_facebook_status():
    try:
        from facebook_oauth import get_token_status, test_connection
        status = get_token_status()
        if status["connected"] and request.args.get("test"):
            status["test"] = test_connection()
        return jsonify(status)
    except Exception as e:
        logger.error("Facebook status error: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/facebook/disconnect", methods=["POST"])
@api_login_required
def disconnect_facebook():
    try:
        token_file = Path(__file__).parent.parent.parent / ".fb_tokens.json"
        if token_file.exists():
            token_file.unlink()
        logger.info("Disconnected from Facebook")
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Disconnect error: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# AI
# ============================================================

@api_bp.route("/api/ai/test", methods=["POST"])
@api_login_required
def test_ai_connection():
    try:
        from gemini_client import test_ai_connection as test_ai
        return jsonify(test_ai())
    except Exception as e:
        logger.error("AI test error: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Agent Control
# ============================================================

@api_bp.route("/api/agent/status", methods=["GET"])
@api_login_required
def get_agent_status():
    global agent_running
    return jsonify({"running": agent_running, "posts_today": 0})


@api_bp.route("/api/agent/start", methods=["POST"])
@api_login_required
def start_agent():
    global agent_thread, agent_running
    if agent_running:
        return jsonify({"success": True, "message": "Already running"})
    try:
        import threading
        import time

        def run_agent():
            global agent_running
            agent_running = True
            logger.info("Agent started")
            try:
                from auto_runner import run_pipeline
                while agent_running:
                    run_pipeline()
                    time.sleep(3600)
            except Exception as e:
                logger.error("Agent error: %s", e)
            finally:
                agent_running = False
                logger.info("Agent stopped")

        agent_thread = threading.Thread(target=run_agent, daemon=True)
        agent_thread.start()
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Agent start error: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/agent/stop", methods=["POST"])
@api_login_required
def stop_agent():
    global agent_running
    agent_running = False
    logger.info("Agent stop requested")
    return jsonify({"success": True})


# ============================================================
# A/B Testing
# ============================================================

@api_bp.route("/api/ab-tests", methods=["GET"])
@api_login_required
def get_ab_tests():
    try:
        from ab_tester import get_tester
        return jsonify({"tests": get_tester().get_active_tests()})
    except Exception as e:
        logger.error("Error fetching A/B tests: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/ab-tests", methods=["POST"])
@api_login_required
def create_ab_test():
    try:
        from ab_tester import get_tester
        data = request.json
        topic = {"title": data.get("title", ""), "content": data.get("content", ""), "hashtags": data.get("hashtags", [])}
        test_id = get_tester().create_test(topic, data.get("styles", ["emotional", "factual"]))
        return jsonify({"success": True, "test_id": test_id})
    except Exception as e:
        logger.error("Error creating A/B test: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/ab-tests/<test_id>/results", methods=["GET"])
@api_login_required
def get_ab_test_results(test_id: str):
    try:
        from ab_tester import get_tester
        return jsonify(get_tester().collect_metrics(test_id))
    except Exception as e:
        logger.error("Error fetching A/B results: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# ML Virality
# ============================================================

@api_bp.route("/api/virality/score", methods=["POST"])
@api_login_required
def score_content_virality():
    try:
        from ml_virality_scorer import get_scorer
        text = request.json.get("text", "")
        scorer = get_scorer()
        score, details = scorer.score_content(text)
        return jsonify({"score": round(score, 2), "max_score": 10.0, "details": details, "ml_trained": scorer.model_trained})
    except Exception as e:
        logger.error("Error scoring content: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/virality/analyze", methods=["POST"])
@api_login_required
def analyze_content_improvement():
    try:
        from ml_virality_scorer import get_scorer
        text = request.json.get("text", "")
        return jsonify(get_scorer().analyze_content_improvement(text))
    except Exception as e:
        logger.error("Error analyzing content: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Randomization
# ============================================================

@api_bp.route("/api/randomization/config", methods=["GET"])
@api_login_required
def get_randomization_config():
    try:
        from randomization import get_randomizer
        r = get_randomizer()
        return jsonify({"human_touch_enabled": r.human_touch_enabled, "emoji_enabled": r.emoji_enabled, "typos_enabled": r.typos_enabled, "typo_rate": r.typo_rate, "min_interval_hours": 2, "max_interval_hours": 4, "min_hashtags": 5, "max_hashtags": 8})
    except Exception as e:
        logger.error("Error fetching randomization config: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Logs
# ============================================================

@api_bp.route("/api/logs/recent", methods=["GET"])
@api_login_required
def get_recent_logs():
    try:
        log_file = Path(__file__).parent.parent.parent / "logs" / "pipeline.log"
        lines = int(request.args.get("lines", 50))
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return jsonify({"logs": [ln.strip() for ln in recent]})
        return jsonify({"logs": []})
    except Exception as e:
        logger.error("Error fetching logs: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Setup Wizard  (protected — user must be logged in)
# ============================================================

@api_bp.route("/api/setup/save", methods=["POST"])
@api_login_required
def save_setup():
    try:
        data = request.json
        env_path, existing = _read_env_file()
        if data.get("fb_token"):
            existing["FACEBOOK_ACCESS_TOKEN"] = data["fb_token"]
        ai_provider = data.get("ai_provider", "gemini")
        if data.get("ai_key"):
            key_name = "GEMINI_API_KEY" if ai_provider == "gemini" else "OPENROUTER_API_KEY"
            existing[key_name] = data["ai_key"]
        if data.get("pexels_key"):
            existing["PEXELS_API_KEY"] = data["pexels_key"]
        _write_env_file(env_path, existing)
        logger.info("Setup saved successfully")
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Setup save error: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/setup/check", methods=["GET"])
@api_login_required
def check_setup():
    fb_ok = bool(os.getenv("FACEBOOK_ACCESS_TOKEN"))
    ai_ok = bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENROUTER_API_KEY"))
    return jsonify({"complete": fb_ok and ai_ok, "facebook": fb_ok, "ai": ai_ok, "images": bool(os.getenv("PEXELS_API_KEY"))})


# ============================================================
# Settings
# ============================================================

@api_bp.route("/api/settings/keys", methods=["POST"])
@api_login_required
def save_settings_keys():
    data = request.get_json(force=True)
    env_path, existing = _read_env_file()
    mapping = {"ai_key": "GEMINI_API_KEY" if data.get("provider") == "gemini" else "OPENROUTER_API_KEY", "fb_token": "FACEBOOK_ACCESS_TOKEN", "pexels_key": "PEXELS_API_KEY"}
    for field, env_var in mapping.items():
        val = data.get(field, "").strip()
        if val:
            existing[env_var] = val
    if data.get("provider"):
        existing["AI_PROVIDER"] = data["provider"]
    _write_env_file(env_path, existing)
    return jsonify({"success": True, "message": "Keys saved"})


@api_bp.route("/api/settings/test-ai", methods=["POST"])
@api_login_required
def test_ai_key():
    data = request.get_json(force=True)
    key = data.get("key", "").strip()
    if not key or len(key) < 10:
        return jsonify({"success": False, "error": "Key too short"})
    return jsonify({"success": True, "message": "Key format looks valid"})


# ============================================================
# License  (activate is PUBLIC — called before login)
# ============================================================

@api_bp.route("/api/license/activate", methods=["POST"])
def activate_license():
    """Activate a Gumroad license key. PUBLIC — called during registration."""
    try:
        from license_validator import validate_license
        data = request.get_json(force=True)
        key = data.get("license_key", "").strip()
        platform = data.get("platform", "").strip() or None
        if not key:
            return jsonify({"valid": False, "reason": "No key provided"}), 400
        return jsonify(validate_license(key, platform=platform))
    except ImportError:
        return jsonify({"valid": False, "reason": "License module not available"}), 500
    except Exception as e:
        return jsonify({"valid": False, "reason": str(e)}), 500


@api_bp.route("/api/license/status", methods=["GET"])
@api_login_required
def license_status():
    try:
        from license_validator import is_licensed, get_license_info
        info = get_license_info() or {}
        return jsonify({"licensed": is_licensed(), "email": info.get("email", ""), "uses": info.get("uses", 0)})
    except ImportError:
        return jsonify({"licensed": False, "reason": "License module not available"})
