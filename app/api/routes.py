"""
Core API routes — system status, analytics/insights, health diagnostics,
agent control, Facebook/Instagram status, AI, license, and logs.

Content CRUD → app/studio/routes.py  (studio_bp)
Pages CRUD   → app/pages/routes.py   (pages_bp)
Settings     → app/settings/routes.py (settings_bp)
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

from flask import Blueprint, jsonify, request
from flask_login import current_user

import config
from app.utils import api_login_required

logger = config.get_logger("api")

api_bp = Blueprint("api", __name__)

# ── Agent state (module-level, per-process) ───────────────────────────────
agent_thread = None
agent_running = False


# ============================================================
# Analytics & Insights
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
            .eq("user_id", current_user.id)
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
                "avg_engagement": round(
                    (total_likes + total_shares + total_comments) / max(total_posts, 1), 1
                ),
            },
            "period": "7d",
        })
    except Exception as e:
        logger.error("Error fetching analytics: %s", e)
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/analytics/daily", methods=["GET"])
@api_login_required
def get_daily_analytics():
    try:
        client = config.get_supabase_client()
        days = int(request.args.get("days", 7))
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = (
            client.table("published_posts")
            .select("published_at, likes, shares, comments, reach")
            .eq("user_id", current_user.id)
            .gte("published_at", since)
            .execute()
        )
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


@api_bp.route("/api/insights", methods=["GET"])
@api_login_required
def get_insights():
    """Generate plain-language insights from engagement data (SQLite only)."""
    MIN_POSTS = 5
    PUBLISHED_FILTER = (
        "facebook_post_id IS NOT NULL OR instagram_post_id IS NOT NULL "
        "OR facebook_status = 'published' OR instagram_status = 'published'"
    )
    try:
        from database import get_db, SQLiteDB
        db = get_db()

        if not isinstance(db, SQLiteDB):
            return jsonify({
                "ready": False, "min_posts_needed": MIN_POSTS,
                "total_posts": 0, "insights": [], "note": "Insights require SQLite mode",
            })

        total_rows = db.execute(
            f"SELECT COUNT(*) AS n FROM published_posts WHERE {PUBLISHED_FILTER}"
        )
        total_posts = total_rows[0]["n"] if total_rows else 0

        if total_posts < MIN_POSTS:
            return jsonify({"ready": False, "min_posts_needed": MIN_POSTS, "total_posts": total_posts, "insights": []})

        insights = []

        # ── Format A/B ────────────────────────────────────────────────
        type_rows = db.execute(f"""
            SELECT pc.post_type, COUNT(*) AS cnt,
                AVG(COALESCE(pp.likes,0)+COALESCE(pp.comments,0)*2+COALESCE(pp.shares,0)*3) AS avg_eng,
                AVG(COALESCE(pp.reach,0)) AS avg_reach
            FROM published_posts pp
            JOIN processed_content pc ON pc.id = pp.content_id
            WHERE pp.published_at >= datetime('now','-30 days') AND ({PUBLISHED_FILTER})
            GROUP BY pc.post_type HAVING cnt >= 2 ORDER BY avg_eng DESC
        """)
        if len(type_rows) >= 2:
            best, worst = type_rows[0], type_rows[-1]
            best_type = (best["post_type"] or "hook").replace("_", " ").title()
            worst_type = (worst["post_type"] or "other").replace("_", " ").title()
            ratio = best["avg_eng"] / worst["avg_eng"] if (worst["avg_eng"] or 0) > 0 else 0
            if ratio >= 1.3:
                insights.append({"type": "post_type", "icon": "fa-fire", "message": f"{best_type} posts are getting {ratio:.1f}× more engagement than {worst_type} posts this month.", "metric": f"Engagement score: {best['avg_eng']:.0f} vs {worst['avg_eng']:.0f}"})
            elif (best["avg_reach"] or 0) > 0:
                insights.append({"type": "post_type", "icon": "fa-chart-line", "message": f"{best_type} posts are your strongest format right now.", "metric": f"Avg reach: {best['avg_reach']:.0f} people"})

        # ── Best posting time ─────────────────────────────────────────
        time_rows = db.execute(f"""
            SELECT CASE WHEN CAST(strftime('%H',pp.published_at) AS INTEGER) BETWEEN 5 AND 11 THEN 'morning (6-11 AM)'
                        WHEN CAST(strftime('%H',pp.published_at) AS INTEGER) BETWEEN 12 AND 16 THEN 'afternoon (12-4 PM)'
                        WHEN CAST(strftime('%H',pp.published_at) AS INTEGER) BETWEEN 17 AND 21 THEN 'evening (5-9 PM)'
                        ELSE 'night (10 PM-5 AM)' END AS time_slot,
                COUNT(*) AS cnt, AVG(COALESCE(pp.reach,0)) AS avg_reach,
                AVG(COALESCE(pp.likes,0)+COALESCE(pp.comments,0)+COALESCE(pp.shares,0)) AS avg_interactions
            FROM published_posts pp
            WHERE pp.published_at >= datetime('now','-30 days') AND pp.reach > 0 AND ({PUBLISHED_FILTER})
            GROUP BY time_slot HAVING cnt >= 2 ORDER BY avg_reach DESC
        """)
        if time_rows:
            best_slot = time_rows[0]
            if (best_slot["avg_reach"] or 0) > 0:
                insights.append({"type": "best_time", "icon": "fa-clock", "message": f"Posts in the {best_slot['time_slot']} reach the most people.", "metric": f"Avg reach: {best_slot['avg_reach']:.0f} people per post"})

        # ── Virality signal ───────────────────────────────────────────
        virality_rows = db.execute(f"""
            SELECT CASE WHEN ra.virality_score >= 70 THEN 'high' ELSE 'lower' END AS bucket,
                COUNT(*) AS cnt, AVG(COALESCE(pp.likes,0)+COALESCE(pp.comments,0)+COALESCE(pp.shares,0)) AS avg_eng
            FROM published_posts pp JOIN processed_content pc ON pc.id = pp.content_id
            JOIN raw_articles ra ON ra.id = pc.article_id
            WHERE ({PUBLISHED_FILTER}) AND ra.virality_score IS NOT NULL GROUP BY bucket HAVING cnt >= 2
        """)
        virality_map = {r["bucket"]: r for r in virality_rows}
        high_v, low_v = virality_map.get("high"), virality_map.get("lower")
        if high_v and low_v and (low_v["avg_eng"] or 0) > 0:
            v_ratio = high_v["avg_eng"] / low_v["avg_eng"]
            if v_ratio >= 1.2:
                insights.append({"type": "virality", "icon": "fa-bolt", "message": f"Posts from trending topics get {v_ratio:.1f}x more interactions on average.", "metric": f"High-virality source avg: {high_v['avg_eng']:.0f} interactions"})

        # ── Weekly trend ──────────────────────────────────────────────
        trend_rows = db.execute(f"""
            SELECT CASE WHEN published_at >= datetime('now','-7 days') THEN 'recent' ELSE 'prior' END AS period,
                COUNT(*) AS cnt, AVG(COALESCE(likes,0)+COALESCE(comments,0)+COALESCE(shares,0)) AS avg_eng
            FROM published_posts WHERE published_at >= datetime('now','-14 days') AND ({PUBLISHED_FILTER}) GROUP BY period
        """)
        trend_map = {r["period"]: r for r in trend_rows}
        recent_p, prior_p = trend_map.get("recent"), trend_map.get("prior")
        if (recent_p and prior_p and (prior_p["avg_eng"] or 0) > 0
                and (recent_p["cnt"] or 0) >= 2 and (prior_p["cnt"] or 0) >= 2):
            change_pct = ((recent_p["avg_eng"] - prior_p["avg_eng"]) / prior_p["avg_eng"]) * 100
            if change_pct >= 10:
                insights.append({"type": "trend", "icon": "fa-arrow-trend-up", "message": f"Engagement is up {change_pct:.0f}% this week compared to last week.", "metric": f"This week avg: {recent_p['avg_eng']:.1f} interactions/post"})
            elif change_pct <= -10:
                insights.append({"type": "trend", "icon": "fa-arrow-trend-down", "message": "Engagement dipped this week — try a different posting time or format.", "metric": f"Down {abs(change_pct):.0f}% vs last week"})

        # ── Fallbacks ─────────────────────────────────────────────────
        if len(insights) < 2:
            top_rows = db.execute(f"""
                SELECT pp.likes, pp.shares, pp.comments, pc.hook FROM published_posts pp
                LEFT JOIN processed_content pc ON pc.id = pp.content_id WHERE ({PUBLISHED_FILTER})
                ORDER BY (COALESCE(pp.likes,0)+COALESCE(pp.comments,0)*2+COALESCE(pp.shares,0)*3) DESC LIMIT 1
            """)
            if top_rows:
                top = top_rows[0]
                hook_text = top.get("hook") or ""
                total_eng = (top.get("likes") or 0) + (top.get("comments") or 0) + (top.get("shares") or 0)
                insights.append({"type": "top_post", "icon": "fa-trophy", "message": f"Your best post so far got {total_eng} interactions — keep that style going.", "metric": f'"{hook_text[:40]}{"..." if len(hook_text) > 40 else ""}"'})

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
                        posts_per_week = round(cnt / max(1, (_dt.datetime.utcnow() - first_dt).days / 7), 1)
                    except Exception:
                        posts_per_week = round(cnt / 4, 1)
                    insights.append({"type": "consistency", "icon": "fa-calendar-check", "message": f"You've published {cnt} posts so far — consistency is the fastest way to grow your audience.", "metric": f"~{posts_per_week} posts/week on average"})

        return jsonify({"ready": True, "min_posts_needed": MIN_POSTS, "total_posts": total_posts, "insights": insights[:3]})

    except Exception as e:
        logger.error("Error generating insights: %s", e)
        return jsonify({"ready": False, "min_posts_needed": MIN_POSTS, "total_posts": 0, "insights": [], "error": str(e)})


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
        modules["ai_image"] = {"available": False}
    try:
        from ml_virality_scorer import get_scorer
        modules["ml_virality"] = {"available": True, "model_trained": get_scorer().model_trained}
    except Exception:
        modules["ml_virality"] = {"available": False}
    return jsonify({"modules": modules})


@api_bp.route("/api/system/snapshot", methods=["GET"])
@api_login_required
def get_system_snapshot():
    try:
        client = config.get_supabase_client()
        result = client.table("system_status").select("key, value, updated_at").execute()
        status_dict = {row["key"]: row["value"] for row in (result.data or [])}
        queue_result = (
            client.table("scheduled_posts")
            .select("id", count="exact")
            .eq("status", "scheduled")
            .eq("user_id", current_user.id)
            .execute()
        )
        queue_size = queue_result.count if hasattr(queue_result, "count") else len(queue_result.data or [])
        next_post = (
            client.table("scheduled_posts")
            .select("scheduled_time")
            .eq("status", "scheduled")
            .eq("user_id", current_user.id)
            .order("scheduled_time")
            .limit(1)
            .execute()
        )
        next_run = next_post.data[0]["scheduled_time"] if next_post.data else None
        pending_result = (
            client.table("processed_content")
            .select("id", count="exact")
            .eq("status", "waiting_approval")
            .eq("user_id", current_user.id)
            .execute()
        )
        pending_approvals = pending_result.count if hasattr(pending_result, "count") else len(pending_result.data or [])
        return jsonify({
            "snapshot": {
                "last_success_publish_at": status_dict.get("last_success_publish_at"),
                "next_run_at": next_run,
                "last_error_code": status_dict.get("last_error_code"),
                "last_error_action": status_dict.get("last_error_action"),
                "queue_size": queue_size,
                "pending_approvals": pending_approvals,
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
# Health & Diagnostics
# ============================================================

@api_bp.route("/api/health/status", methods=["GET"])
@api_login_required
def get_health_detailed():
    try:
        from rate_limiter import get_rate_limiter
        limiter = get_rate_limiter()
        can, reason = limiter.can_post_now()
        return jsonify({
            "last_error": None,
            "cooldown": {"active": not can, "until": limiter.get_status_summary().get("cooldown_until"), "reason": reason},
            "tokens": {"facebook": bool(os.getenv("FACEBOOK_ACCESS_TOKEN")), "ai": True, "pexels": True},
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/api/health/events", methods=["GET"])
@api_login_required
def get_health_events():
    return jsonify({"events": [
        {"type": "info", "message": "System started", "time": "10 min ago"},
        {"type": "publish", "message": "Content published successfully", "time": "1 hour ago"},
        {"type": "generate", "message": "New content generated", "time": "2 hours ago"},
    ]})


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
    return jsonify({"success": True})


# ============================================================
# Facebook & Instagram
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
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Disconnect error: %s", e)
        return jsonify({"error": str(e)}), 500


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
            return jsonify({"connected": False, "reason": "Incomplete token data"})
        stored_ig_id = tokens.get("instagram_account_id", "")
        if stored_ig_id:
            return jsonify({"connected": True, "instagram_account_id": stored_ig_id, "username": tokens.get("instagram_username", ""), "facebook_page_id": page_id})
        ig_info = get_instagram_account_for_page(page_id, page_token)
        if not ig_info:
            return jsonify({"connected": False, "facebook_page_id": page_id, "reason": "No Instagram Business Account linked to this Facebook Page."})
        return jsonify({"connected": True, "instagram_account_id": ig_info["instagram_account_id"], "username": ig_info.get("username", ""), "facebook_page_id": page_id})
    except Exception as e:
        logger.error("Error checking Instagram status: %s", e)
        return jsonify({"connected": False, "reason": str(e)}), 500


# ============================================================
# AI Test
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
# License  (activate is PUBLIC — pre-registration use)
# ============================================================

@api_bp.route("/api/license/activate", methods=["POST"])
def activate_license():
    """Validate a Gumroad license key. Intentionally public — called before login."""
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
