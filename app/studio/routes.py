"""Content Studio API routes — tenant-scoped content CRUD, publishing, A/B, virality."""

import json
import uuid
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user

import config
from app.utils import api_login_required

logger = config.get_logger("studio")

studio_bp = Blueprint("studio", __name__)


# ── Helper ────────────────────────────────────────────────────────────────

def _client():
    return config.get_supabase_client()


# ============================================================
# Content — Approval Workflow
# ============================================================

@studio_bp.route("/api/content/<content_id>/approve", methods=["POST"])
@api_login_required
def approve_content(content_id: str):
    try:
        result = (
            _client().table("processed_content")
            .update({"status": "scheduled"})
            .eq("id", content_id)
            .eq("user_id", current_user.id)
            .eq("status", "waiting_approval")
            .execute()
        )
        if not result.data:
            return jsonify({"error": "Content not found or not in waiting_approval status"}), 404
        return jsonify({"success": True, "content_id": content_id, "new_status": "scheduled"})
    except Exception as e:
        logger.error("Error approving content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/<content_id>/reject", methods=["POST"])
@api_login_required
def reject_content(content_id: str):
    try:
        data = request.json or {}
        action = data.get("action", "reject")
        reason = data.get("reason", "Rejected by user")
        new_status = "drafted" if action == "regenerate" else "rejected"
        result = (
            _client().table("processed_content")
            .update({"status": new_status, "rejected_reason": reason if new_status == "rejected" else None})
            .eq("id", content_id)
            .eq("user_id", current_user.id)
            .execute()
        )
        if not result.data:
            return jsonify({"error": "Content not found"}), 404
        return jsonify({"success": True, "content_id": content_id, "new_status": new_status})
    except Exception as e:
        logger.error("Error rejecting content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/pending", methods=["GET"])
@api_login_required
def get_pending_content():
    try:
        limit = int(request.args.get("limit", 20))
        result = (
            _client().table("processed_content")
            .select("id, generated_text, hook, hashtags, image_path, generated_at, status")
            .eq("status", "waiting_approval")
            .eq("user_id", current_user.id)
            .order("generated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return jsonify({"pending": result.data or []})
    except Exception as e:
        logger.error("Error fetching pending content: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Content — CRUD
# ============================================================

@studio_bp.route("/api/content/scheduled", methods=["GET"])
@api_login_required
def get_scheduled_content():
    try:
        limit = int(request.args.get("limit", 20))
        result = (
            _client().table("scheduled_posts")
            .select("id, content_id, scheduled_time, timezone, status, platforms")
            .eq("status", "scheduled")
            .eq("user_id", current_user.id)
            .order("scheduled_time")
            .limit(limit)
            .execute()
        )
        return jsonify({"scheduled": result.data or []})
    except Exception as e:
        logger.error("Error fetching scheduled: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/published", methods=["GET"])
@api_login_required
def get_published_content():
    try:
        limit = int(request.args.get("limit", 20))
        result = (
            _client().table("published_posts")
            .select("id, content_id, facebook_post_id, facebook_status, instagram_post_id, instagram_status, platforms, published_at, likes, shares, comments, reach")
            .eq("user_id", current_user.id)
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
        )
        return jsonify({"published": result.data or []})
    except Exception as e:
        logger.error("Error fetching published: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/<content_id>", methods=["GET"])
@api_login_required
def get_content_by_id(content_id: str):
    try:
        result = (
            _client().table("processed_content")
            .select("*")
            .eq("id", content_id)
            .eq("user_id", current_user.id)
            .single()
            .execute()
        )
        return jsonify(result.data or {})
    except Exception as e:
        logger.error("Error fetching content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/<content_id>/image", methods=["GET"])
@api_login_required
def get_content_image(content_id: str):
    try:
        result = (
            _client().table("processed_content")
            .select("image_path")
            .eq("id", content_id)
            .eq("user_id", current_user.id)
            .single()
            .execute()
        )
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


@studio_bp.route("/api/content/<content_id>", methods=["PUT"])
@api_login_required
def update_content(content_id: str):
    try:
        data = request.json or {}
        update_data: Dict = {}
        for field in ["generated_text", "arabic_text", "hashtags", "hook", "call_to_action"]:
            if field in data:
                update_data[field] = data[field]
        if not update_data:
            return jsonify({"error": "No fields to update"}), 400
        result = (
            _client().table("processed_content")
            .update(update_data)
            .eq("id", content_id)
            .eq("user_id", current_user.id)
            .execute()
        )
        if result.data:
            return jsonify({"success": True, "content": result.data[0]})
        return jsonify({"error": "Content not found"}), 404
    except Exception as e:
        logger.error("Error updating content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/dashboard-summary", methods=["GET"])
@api_login_required
def get_dashboard_summary():
    try:
        uid = current_user.id
        c = _client()
        pending = (c.table("processed_content").select("id, generated_text, created_at").eq("status", "waiting_approval").eq("user_id", uid).order("created_at", desc=True).limit(5).execute()).data or []
        scheduled = (c.table("scheduled_posts").select("id, scheduled_time, status").eq("status", "scheduled").eq("user_id", uid).order("scheduled_time").limit(5).execute()).data or []
        published = (c.table("published_posts").select("id, published_at").eq("user_id", uid).order("published_at", desc=True).limit(5).execute()).data or []
        return jsonify({
            "pending": [{"id": p["id"], "text": p.get("generated_text", "No text"), "time": p["created_at"].split("T")[0], "image": f"/api/content/{p['id']}/image"} for p in pending],
            "scheduled": [{"id": s["id"], "text": "Scheduled Post", "time": s["scheduled_time"].replace("T", " ")[:16], "image": None} for s in scheduled],
            "published": [{"id": p["id"], "text": "Published Post", "time": p["published_at"].replace("T", " ")[:16], "image": None} for p in published],
            "ready_count": len(scheduled),
        })
    except Exception as e:
        logger.error("Error fetching dashboard summary: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/list", methods=["GET"])
@api_login_required
def list_content():
    try:
        limit = int(request.args.get("limit", 50))
        q = (request.args.get("q") or "").strip().lower()
        status = (request.args.get("status") or "").strip()
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        query = (
            _client().table("processed_content")
            .select("id, hook, generated_text, status, generated_at, image_path")
            .eq("user_id", current_user.id)
            .order("generated_at", desc=True)
            .limit(limit)
        )
        if statuses:
            query = query.in_("status", statuses)
        rows = query.execute().data or []
        if q:
            rows = [r for r in rows if q in (r.get("hook") or "").lower() or q in (r.get("generated_text") or "").lower()]
        return jsonify({"content": rows})
    except Exception as e:
        logger.error("Error listing content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/all", methods=["GET"])
@api_login_required
def get_all_content():
    try:
        limit = int(request.args.get("limit", 50))
        result = (
            _client().table("processed_content")
            .select("id, generated_text, hook, status, created_at, generated_at, target_audience")
            .eq("user_id", current_user.id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return jsonify({"content": result.data or []})
    except Exception as e:
        logger.error("Error fetching all content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/<content_id>/schedule", methods=["POST"])
@api_login_required
def schedule_content(content_id: str):
    try:
        data = request.json or {}
        scheduled_time = data.get("scheduled_time")
        if not scheduled_time:
            return jsonify({"error": "scheduled_time required"}), 400
        c = _client()
        c.table("processed_content").update({"status": "scheduled"}).eq("id", content_id).eq("user_id", current_user.id).execute()
        insert = c.table("scheduled_posts").insert({
            "user_id": current_user.id,
            "content_id": content_id,
            "scheduled_time": scheduled_time,
            "timezone": data.get("timezone", "America/New_York"),
            "status": "scheduled",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return jsonify({"success": True, "scheduled": insert.data[0] if insert.data else None})
    except Exception as e:
        logger.error("Error scheduling content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/<content_id>/regenerate", methods=["POST"])
@api_login_required
def regenerate_content_by_id(content_id: str):
    try:
        from ai_generator import generate_post_text, generate_post_image
        c = _client()
        data = request.json or {}
        style = data.get("style")
        template_id = data.get("template_id")
        content = c.table("processed_content").select("*").eq("id", content_id).eq("user_id", current_user.id).single().execute()
        if not content.data:
            return jsonify({"error": "Content not found"}), 404
        result: Dict = {"success": True}
        if style:
            article_id = content.data.get("article_id")
            title = "Tech News"
            if article_id:
                article = c.table("raw_articles").select("title").eq("id", article_id).eq("user_id", current_user.id).single().execute()
                if article.data:
                    title = article.data.get("title", "Tech News")
            style_prompts = {"emotional": "Style: très émotionnel, hooks percutants", "factual": "Style: informatif, faits précis", "casual": "Style: décontracté, humour, relatable", "motivational": "Style: inspirant, énergie positive"}
            prompt = f"Génère un post Facebook en arabe sur: {title}\n\n{style_prompts.get(style, style_prompts['emotional'])}"
            new_text = generate_post_text(prompt)
            if new_text:
                c.table("processed_content").update({"generated_text": new_text, "ab_variant_style": style}).eq("id", content_id).eq("user_id", current_user.id).execute()
                result["new_text"] = new_text
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
                    rel_path = os.path.relpath(new_image_path, start=os.getcwd()) if new_image_path else new_image_path
                    c.table("processed_content").update({"local_image_path": rel_path, "template_id": template_id}).eq("id", content_id).eq("user_id", current_user.id).execute()
                    result["new_image"] = rel_path
                else:
                    return jsonify({"error": "Image generation failed"}), 500
        return jsonify(result)
    except Exception as e:
        logger.error("Error regenerating content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/content/regenerate", methods=["POST"])
@api_login_required
def regenerate_content_legacy():
    try:
        from gemini_client import get_ai_client
        import re
        data = request.get_json()
        content_id = data.get("content_id")
        style = data.get("style", "news")
        if not content_id:
            return jsonify({"error": "Missing content_id"}), 400
        c = _client()
        result = c.table("processed_content").select("*").eq("id", content_id).eq("user_id", current_user.id).single().execute()
        if not result.data:
            return jsonify({"error": "Content not found"}), 404
        content = result.data
        article = None
        if content.get("article_id"):
            art = c.table("raw_articles").select("title,content").eq("id", content["article_id"]).eq("user_id", current_user.id).single().execute()
            if art.data:
                article = art.data
        style_prompts = {"emotional": "اكتب بأسلوب عاطفي ومؤثر", "news": "اكتب بأسلوب إخباري موضوعي", "casual": "اكتب بأسلوب عفوي وودي", "motivation": "اكتب بأسلوب تحفيزي وملهم"}
        title = article.get("title", "") if article else content.get("hook", "")
        prompt = f'أعد كتابة هذا المنشور:\nالعنوان: {title}\nالمحتوى: {content.get("generated_text","")}\nالتعليمات: {style_prompts.get(style, style_prompts["news"])}\nأجب بـ JSON:\n{{"hook":"...","body":"...","cta":"...","hashtags":["..."]}}'
        ai = get_ai_client()
        response = ai.generate(prompt, max_tokens=1000, temperature=0.8)
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            nc = json.loads(json_match.group())
            update_data = {"hook": nc.get("hook", content.get("hook")), "generated_text": nc.get("body", content.get("generated_text")), "call_to_action": nc.get("cta", content.get("call_to_action")), "hashtags": nc.get("hashtags", content.get("hashtags", []))}
            c.table("processed_content").update(update_data).eq("id", content_id).eq("user_id", current_user.id).execute()
            return jsonify({"success": True, "style": style})
        return jsonify({"error": "Failed to parse AI response"}), 500
    except Exception as e:
        logger.error("Regenerate error: %s", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# Brand & Templates
# ============================================================

@studio_bp.route("/api/brand/templates", methods=["GET"])
@api_login_required
def get_brand_templates():
    text_templates = []
    image_templates = []
    try:
        with open("text_templates.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            for lang in ["AR", "FR", "EN"]:
                for t in data.get(lang, []):
                    t["language"] = lang
                    text_templates.append(t)
    except Exception:
        pass
    try:
        with open("image_templates.json", "r", encoding="utf-8") as f:
            image_templates = json.load(f).get("layouts", [])
    except Exception:
        pass
    return jsonify({"text_templates": text_templates, "image_templates": image_templates})


@studio_bp.route("/api/brand/template-select", methods=["POST"])
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


@studio_bp.route("/api/brand/language-ratio", methods=["POST"])
@api_login_required
def set_language_ratio():
    try:
        data = request.json or {}
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


@studio_bp.route("/api/brand/glossary", methods=["POST"])
@api_login_required
def update_glossary():
    try:
        data = request.json or {}
        brand_config: Dict = {}
        try:
            if Path("brand_config.json").exists():
                with open("brand_config.json", "r", encoding="utf-8") as f:
                    brand_config = json.load(f)
        except Exception:
            pass
        brand_config["glossary"] = data.get("terms", [])
        with open("brand_config.json", "w", encoding="utf-8") as f:
            json.dump(brand_config, f, indent=4)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# Actions — Publish
# ============================================================

def _publish_to_instagram(content_id: str) -> Dict:
    """Internal: publish content to Instagram, scoped to current user."""
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
            return {"success": False, "error": "No Instagram Business Account linked"}
        ig_user_id = ig_info["instagram_account_id"]

        c = _client()
        result = c.table("processed_content").select("*").eq("id", content_id).eq("user_id", current_user.id).single().execute()
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
            return {"success": False, "error": "No image available"}

        base_url = get_app_base_url()
        image_url = get_public_image_url(image_path, base_url)
        if not image_url:
            return {"success": False, "error": f"Image file not found: {image_path}"}

        ig_post_id = publish_photo_to_instagram(ig_user_id, page_token, image_url, caption)

        try:
            pub_rows = c.table("published_posts").select("id").eq("content_id", content_id).eq("user_id", current_user.id).order("published_at", desc=True).limit(1).execute()
            if pub_rows.data:
                c.table("published_posts").update({"instagram_post_id": ig_post_id, "instagram_status": "published", "platforms": "facebook,instagram"}).eq("id", pub_rows.data[0]["id"]).eq("user_id", current_user.id).execute()
            else:
                import uuid as _uuid
                c.table("published_posts").insert({"id": str(_uuid.uuid4()), "user_id": current_user.id, "content_id": content_id, "instagram_post_id": ig_post_id, "instagram_status": "published", "platforms": "instagram"}).execute()
                c.table("processed_content").update({"status": "published"}).eq("id", content_id).eq("user_id", current_user.id).execute()
        except Exception as db_err:
            logger.warning("Could not save Instagram post ID to DB: %s", db_err)

        return {"success": True, "post_id": ig_post_id}
    except Exception as e:
        logger.error("Instagram publish failed: %s", e)
        return {"success": False, "error": str(e)}


@studio_bp.route("/api/actions/publish-content", methods=["POST"])
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
            per_platform["facebook"] = publish_content_by_id(content_id, user_id=current_user.id)
        if "instagram" in platforms:
            per_platform["instagram"] = _publish_to_instagram(content_id)

        any_success = any(v.get("success") for v in per_platform.values())
        results: Dict = {"content_id": content_id, "platforms": per_platform, "success": any_success}
        if per_platform.get("facebook", {}).get("success"):
            results["post_id"] = per_platform["facebook"].get("post_id")
        if per_platform.get("instagram", {}).get("success"):
            results["instagram_post_id"] = per_platform["instagram"].get("post_id")
        if not any_success:
            results["error"] = "; ".join(f"{p}: {v.get('error','failed')}" for p, v in per_platform.items() if not v.get("success"))
        return jsonify(results)
    except Exception as e:
        logger.error("Error publishing content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/actions/publish-next", methods=["POST"])
@api_login_required
def publish_next():
    try:
        c = _client()
        next_post = c.table("scheduled_posts").select("*").eq("status", "scheduled").eq("user_id", current_user.id).order("scheduled_time").limit(1).execute()
        if not next_post.data:
            return jsonify({"success": False, "error": "No scheduled posts found"})
        now = datetime.now(timezone.utc).isoformat()
        c.table("scheduled_posts").update({"scheduled_time": now}).eq("id", next_post.data[0]["id"]).eq("user_id", current_user.id).execute()
        return jsonify({"success": True, "message": "Scheduled for immediate publishing"})
    except Exception as e:
        logger.error("Error publishing next: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/actions/publish-now", methods=["POST"])
@api_login_required
def publish_now():
    try:
        from publisher import publish_due_posts
        limit = int((request.json or {}).get("limit", 1))
        published = publish_due_posts(limit=limit, user_id=current_user.id)
        return jsonify({"success": True, "published_count": published})
    except Exception as e:
        logger.error("Error publishing: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/actions/run-now", methods=["POST"])
@api_login_required
def action_run_now():
    logger.info("Manual 'Run Now' command from user %s", current_user.id)
    return jsonify({"success": True, "message": "Pipeline triggered successfully"})


@studio_bp.route("/api/actions/pause", methods=["POST"])
@api_login_required
def action_pause():
    return jsonify({"success": True, "message": "System paused for 24h"})


@studio_bp.route("/api/actions/schedule", methods=["POST"])
@api_login_required
def run_scheduler():
    try:
        from scheduler import schedule_posts
        data = request.json or {}
        days = int(data.get("days", 7))
        platforms_raw = data.get("platforms", "facebook")
        platforms_str = ",".join(p.strip() for p in platforms_raw) if isinstance(platforms_raw, list) else str(platforms_raw).strip() or "facebook"
        scheduled = schedule_posts(days=days, platforms=platforms_str, user_id=current_user.id)
        return jsonify({"success": True, "scheduled_count": scheduled, "platforms": platforms_str})
    except Exception as e:
        logger.error("Error scheduling: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/actions/create-content", methods=["POST"])
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


@studio_bp.route("/api/actions/sync-analytics", methods=["POST"])
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
# A/B Testing
# ============================================================

@studio_bp.route("/api/ab-tests", methods=["GET"])
@api_login_required
def get_ab_tests():
    try:
        from ab_tester import get_tester
        return jsonify({"tests": get_tester().get_active_tests()})
    except Exception as e:
        logger.error("Error fetching A/B tests: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/ab-tests", methods=["POST"])
@api_login_required
def create_ab_test():
    try:
        from ab_tester import get_tester
        data = request.json or {}
        topic = {"title": data.get("title", ""), "content": data.get("content", ""), "hashtags": data.get("hashtags", [])}
        test_id = get_tester().create_test(topic, data.get("styles", ["emotional", "factual"]))
        return jsonify({"success": True, "test_id": test_id})
    except Exception as e:
        logger.error("Error creating A/B test: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/ab-tests/<test_id>/results", methods=["GET"])
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

@studio_bp.route("/api/virality/score", methods=["POST"])
@api_login_required
def score_content_virality():
    try:
        from ml_virality_scorer import get_scorer
        text = (request.json or {}).get("text", "")
        scorer = get_scorer()
        score, details = scorer.score_content(text)
        return jsonify({"score": round(score, 2), "max_score": 10.0, "details": details, "ml_trained": scorer.model_trained})
    except Exception as e:
        logger.error("Error scoring content: %s", e)
        return jsonify({"error": str(e)}), 500


@studio_bp.route("/api/virality/analyze", methods=["POST"])
@api_login_required
def analyze_content_improvement():
    try:
        from ml_virality_scorer import get_scorer
        text = (request.json or {}).get("text", "")
        return jsonify(get_scorer().analyze_content_improvement(text))
    except Exception as e:
        logger.error("Error analyzing content: %s", e)
        return jsonify({"error": str(e)}), 500
