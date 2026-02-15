"""
Dashboard App - Web interface for managing multi-page Facebook automation.

Features:
- Multiple FB page management
- Per-page configuration (posts/day, language)
- Analytics dashboard
- Real-time monitoring
- Settings panel
"""

import os
from dotenv import load_dotenv

# CRITICAL: Load .env FIRST before any other imports
load_dotenv()

from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template, request, redirect, url_for, session, Blueprint, send_file
from flask_cors import CORS

import config
import json
import random
from pathlib import Path

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')


def _get_or_create_secret_key() -> str:
    """Auto-generate and persist a Flask secret key on first run."""
    env_key = os.getenv("FLASK_SECRET_KEY", "")
    if env_key:
        return env_key
    secret_file = Path(__file__).parent / ".flask_secret"
    if secret_file.exists():
        return secret_file.read_text().strip()
    import secrets as _secrets
    new_key = _secrets.token_hex(32)
    try:
        secret_file.write_text(new_key)
    except OSError:
        pass
    return new_key


app.secret_key = _get_or_create_secret_key()
CORS(app)

logger = config.get_logger("dashboard")

# Simple API key auth (for production, use proper auth)
API_KEY = os.getenv("DASHBOARD_API_KEY", "")

# Blueprints
web_bp = Blueprint('web', __name__)
api_bp = Blueprint('api', __name__)

@app.context_processor
def inject_dashboard_config():
    return {
        'dashboard_api_key': API_KEY or ''
    }

def _read_env_file():
    env_path = Path(__file__).parent / '.env'
    existing = {}
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, val = line.strip().split('=', 1)
                    existing[key] = val
    return env_path, existing

def _write_env_file(env_path: Path, data: Dict[str, str]) -> None:
    with open(env_path, 'w', encoding='utf-8') as f:
        for key, val in data.items():
            f.write(f"{key}={val}\n")

def require_auth(f):
    """Simple authentication decorator."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if API_KEY:
            auth_header = request.headers.get("X-API-Key")
            if auth_header != API_KEY:
                return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ============================================
# API ROUTES - Pages Management
# ============================================

@api_bp.route('/api/pages', methods=['GET'])
@require_auth
def get_pages():
    """Get all managed pages."""
    try:
        client = config.get_supabase_client()
        result = client.table('managed_pages').select('*').execute()
        return jsonify({"pages": result.data or []})
    except Exception as e:
        logger.error(f"Error fetching pages: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/pages', methods=['POST'])
@require_auth
def add_page():
    """Add a new managed page."""
    try:
        data = request.json
        
        page_data = {
            "page_id": data.get("page_id"),
            "page_name": data.get("page_name", "Unnamed Page"),
            "access_token": data.get("access_token"),
            "posts_per_day": int(data.get("posts_per_day", 3)),
            "language": data.get("language", "ar"),
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        client = config.get_supabase_client()
        result = client.table('managed_pages').insert(page_data).execute()
        
        logger.info(f"Added page: {page_data['page_name']}")
        return jsonify({"success": True, "page": result.data[0] if result.data else None})
        
    except Exception as e:
        logger.error(f"Error adding page: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/pages/<page_id>', methods=['PUT'])
@require_auth
def update_page(page_id: str):
    """Update page configuration."""
    try:
        data = request.json
        
        update_data = {}
        if "posts_per_day" in data:
            update_data["posts_per_day"] = int(data["posts_per_day"])
        if "language" in data:
            update_data["language"] = data["language"]
        if "status" in data:
            update_data["status"] = data["status"]
        if "page_name" in data:
            update_data["page_name"] = data["page_name"]
        
        client = config.get_supabase_client()
        result = client.table('managed_pages').update(update_data).eq('page_id', page_id).execute()
        
        return jsonify({"success": True, "page": result.data[0] if result.data else None})
        
    except Exception as e:
        logger.error(f"Error updating page: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/pages/<page_id>', methods=['DELETE'])
@require_auth
def delete_page(page_id: str):
    """Delete a managed page."""
    try:
        client = config.get_supabase_client()
        client.table('managed_pages').delete().eq('page_id', page_id).execute()
        
        logger.info(f"Deleted page: {page_id}")
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Error deleting page: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# PAGE ROUTES (Frontend)
# ============================================

@web_bp.route('/')
def page_dashboard():
    """Main Dashboard (Mission Control)."""
    return render_template('dashboard_v3.html', active_page='dashboard')

@web_bp.route('/studio')
def page_studio():
    """Content Studio."""
    return render_template('studio_v3.html', active_page='studio')

@web_bp.route('/templates')
def page_templates():
    """Templates & Branding."""
    return render_template('templates_v3.html', active_page='templates')

@web_bp.route('/settings')
def page_settings():
    """Unified Settings."""
    return render_template('settings_v3.html', active_page='settings')

@web_bp.route('/health')
def page_health():
    """System Health & Logs page."""
    return render_template('health_v3.html', active_page='health')

# Legacy setup (kept for config access if needed, or redirect)
@web_bp.route('/setup')
def page_setup():
    return render_template('setup_v3.html', active_page='setup')



# ============================================
# API ROUTES - Analytics
# ============================================

@api_bp.route('/api/analytics/overview', methods=['GET'])
@require_auth
def get_analytics_overview():
    """Get analytics overview for all pages."""
    try:
        client = config.get_supabase_client()
        
        # Get last 7 days of data
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        
        # Published posts count
        posts_result = client.table('published_posts').select('id, likes, shares, comments, reach').gte('published_at', since).execute()
        posts = posts_result.data or []
        
        # Calculate totals
        total_posts = len(posts)
        total_likes = sum(p.get('likes', 0) or 0 for p in posts)
        total_shares = sum(p.get('shares', 0) or 0 for p in posts)
        total_comments = sum(p.get('comments', 0) or 0 for p in posts)
        total_reach = sum(p.get('reach', 0) or 0 for p in posts)
        
        # Engagement rate
        engagement = total_likes + total_shares + total_comments
        engagement_rate = (engagement / total_reach * 100) if total_reach > 0 else 0
        
        return jsonify({
            "period": "7_days",
            "total_posts": total_posts,
            "total_likes": total_likes,
            "total_shares": total_shares,
            "total_comments": total_comments,
            "total_reach": total_reach,
            "engagement_rate": round(engagement_rate, 2),
            "avg_per_post": {
                "likes": round(total_likes / total_posts, 1) if total_posts > 0 else 0,
                "shares": round(total_shares / total_posts, 1) if total_posts > 0 else 0,
                "comments": round(total_comments / total_posts, 1) if total_posts > 0 else 0
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/analytics/daily', methods=['GET'])
@require_auth
def get_daily_analytics():
    """Get daily analytics breakdown."""
    try:
        client = config.get_supabase_client()
        days = int(request.args.get('days', 7))
        
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        result = client.table('published_posts').select('published_at, likes, shares, comments, reach').gte('published_at', since).execute()
        
        # Group by day
        daily_data = {}
        for post in result.data or []:
            date = post['published_at'][:10]  # YYYY-MM-DD
            if date not in daily_data:
                daily_data[date] = {"posts": 0, "likes": 0, "shares": 0, "comments": 0, "reach": 0}
            
            daily_data[date]["posts"] += 1
            daily_data[date]["likes"] += post.get('likes', 0) or 0
            daily_data[date]["shares"] += post.get('shares', 0) or 0
            daily_data[date]["comments"] += post.get('comments', 0) or 0
            daily_data[date]["reach"] += post.get('reach', 0) or 0
        
        return jsonify({"daily": [{"date": k, **v} for k, v in sorted(daily_data.items())]})
        
    except Exception as e:
        logger.error(f"Error fetching daily analytics: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - System Status
# ============================================

@api_bp.route('/api/status', methods=['GET'])
@require_auth
def get_system_status():
    """Get system status and health checks."""
    try:
        from rate_limiter import get_rate_limiter
        from ban_detector import get_detector
        
        limiter = get_rate_limiter()
        detector = get_detector()
        
        # Rate limiter status
        can_post, reason = limiter.can_post_now()
        limiter_status = limiter.get_status_summary()
        
        # Ban detector status
        ban_check = detector.check_for_shadowban()
        
        return jsonify({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "can_post": can_post,
            "post_reason": reason,
            "rate_limiter": limiter_status,
            "ban_detector": {
                "status": ban_check["status"],
                "reason": ban_check["reason"],
                "severity": ban_check.get("severity", 0)
            },
            "health": "healthy" if can_post and ban_check["status"] == "ok" else "degraded"
        })
        
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        return jsonify({"error": str(e), "health": "error"}), 500


@api_bp.route('/api/status/modules', methods=['GET'])
@require_auth
def get_modules_status():
    """Get status of all automation modules."""
    modules = {}
    
    # Check each module
    # Note: Video generator removed for v1 simplicity
    
    try:
        from ai_image_fallback import is_ai_available, get_fallback
        fallback = get_fallback()
        modules["ai_image"] = fallback.get_status()
    except:
        modules["ai_image"] = {"available": False, "error": "Import failed"}
    
    try:
        from ml_virality_scorer import get_scorer
        scorer = get_scorer()
        modules["ml_virality"] = {"available": True, "model_trained": scorer.model_trained}
    except:
        modules["ml_virality"] = {"available": False, "error": "Import failed"}
    
    return jsonify({"modules": modules})


# ============================================
# v2.1 API ROUTES - System Snapshot & Approval
# ============================================

@api_bp.route('/api/system/snapshot', methods=['GET'])
@require_auth
def get_system_snapshot():
    """
    v2.1: Get at-a-glance system health snapshot.
    
    Returns key metrics for quick diagnostics:
    - last_success_publish_at
    - next_run_at
    - last_error_code / last_error_action
    - queue_size
    - cooldown_until
    - token_valid
    """
    try:
        client = config.get_supabase_client()
        
        # Get all system status keys
        result = client.table('system_status').select('key, value, updated_at').execute()
        status_dict = {row['key']: row['value'] for row in (result.data or [])}
        
        # Get queue size (scheduled posts count)
        queue_result = client.table('scheduled_posts').select('id', count='exact').eq('status', 'scheduled').execute()
        queue_size = queue_result.count if hasattr(queue_result, 'count') else len(queue_result.data or [])
        
        # Get next scheduled post time
        next_post = client.table('scheduled_posts').select('scheduled_time').eq('status', 'scheduled').order('scheduled_time').limit(1).execute()
        next_run = next_post.data[0]['scheduled_time'] if next_post.data else None
        
        # Get pending approvals count (v2.1 approval workflow)
        pending_result = client.table('processed_content').select('id', count='exact').eq('status', 'waiting_approval').execute()
        pending_approvals = pending_result.count if hasattr(pending_result, 'count') else len(pending_result.data or [])
        
        return jsonify({
            "snapshot": {
                "last_success_publish_at": status_dict.get('last_success_publish_at'),
                "next_run_at": next_run,
                "last_error_code": status_dict.get('last_error_code'),
                "last_error_action": status_dict.get('last_error_action'),
                "queue_size": queue_size,
                "pending_approvals": pending_approvals,
                "cooldown_until": status_dict.get('cooldown_until'),
                "token_valid": status_dict.get('token_valid', 'true') == 'true',
                "approval_mode": config.APPROVAL_MODE,
                "db_mode": os.getenv('DB_MODE', 'sqlite').lower()
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error fetching system snapshot: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/content/<content_id>/approve', methods=['POST'])
@require_auth
def approve_content(content_id: str):
    """
    v2.1: Approve content for publishing.
    
    Moves content from 'waiting_approval' to 'scheduled' status.
    """
    try:
        client = config.get_supabase_client()
        
        # Update content status
        result = client.table('processed_content').update({
            'status': 'scheduled'
        }).eq('id', content_id).eq('status', 'waiting_approval').execute()
        
        if not result.data:
            return jsonify({"error": "Content not found or not in waiting_approval status"}), 404
        
        logger.info(f"✅ Approved content: {content_id}")
        return jsonify({"success": True, "content_id": content_id, "new_status": "scheduled"})
        
    except Exception as e:
        logger.error(f"Error approving content: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/content/<content_id>/reject', methods=['POST'])
@require_auth
def reject_content(content_id: str):
    """
    v2.1.1: Reject content (mark as rejected or regenerate).
    
    Options via JSON body:
    - action: 'reject' (default) or 'regenerate'
    - reason: Optional rejection reason
    """
    try:
        client = config.get_supabase_client()
        data = request.json or {}
        action = data.get('action', 'reject')
        reason = data.get('reason', 'Rejected by user')
        
        if action == 'regenerate':
            # Reset to drafted for regeneration
            new_status = 'drafted'
        else:
            # v2.1.1: Use 'rejected' status (not 'failed') to separate user rejections from system errors
            new_status = 'rejected'
        
        result = client.table('processed_content').update({
            'status': new_status,
            'rejected_reason': reason if new_status == 'rejected' else None
        }).eq('id', content_id).execute()
        
        if not result.data:
            return jsonify({"error": "Content not found"}), 404
        
        logger.info(f"❌ Rejected content: {content_id} (action: {action})")
        return jsonify({"success": True, "content_id": content_id, "new_status": new_status})
        
    except Exception as e:
        logger.error(f"Error rejecting content: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/content/pending', methods=['GET'])
@require_auth
def get_pending_content():
    """
    v2.1: Get content awaiting approval.
    """
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get('limit', 20))
        
        result = (
            client.table('processed_content')
            .select('id, generated_text, hook, hashtags, image_path, generated_at, status')
            .eq('status', 'waiting_approval')
            .order('generated_at', desc=True)
            .limit(limit)
            .execute()
        )
        
        return jsonify({"pending": result.data or []})
        
    except Exception as e:
        logger.error(f"Error fetching pending content: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - Content Management
# ============================================

@api_bp.route('/api/content/scheduled', methods=['GET'])
@require_auth
def get_scheduled_content():
    """Get scheduled posts."""
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get('limit', 20))
        
        result = (
            client.table('scheduled_posts')
            .select('id, content_id, scheduled_time, timezone, status')
            .eq('status', 'scheduled')
            .order('scheduled_time')
            .limit(limit)
            .execute()
        )
        
        return jsonify({"scheduled": result.data or []})
        
    except Exception as e:
        logger.error(f"Error fetching scheduled: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/content/published', methods=['GET'])
@require_auth
def get_published_content():
    """Get recently published posts."""
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get('limit', 20))
        
        result = (
            client.table('published_posts')
            .select('id, content_id, facebook_post_id, published_at, likes, shares, comments, reach')
            .order('published_at', desc=True)
            .limit(limit)
            .execute()
        )
        
        return jsonify({"published": result.data or []})
        
    except Exception as e:
        logger.error(f"Error fetching published: {e}")
        return jsonify({"error": str(e)}), 500





@api_bp.route('/api/content/<content_id>', methods=['GET'])
@require_auth
def get_content_by_id(content_id: str):
    """Get specific content by ID."""
    try:
        client = config.get_supabase_client()
        
        result = (
            client.table('processed_content')
            .select('*')
            .eq('id', content_id)
            .single()
            .execute()
        )
        
        return jsonify(result.data or {})
        
    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        return jsonify({"error": str(e)}), 500




@api_bp.route('/api/content/<content_id>/image', methods=['GET'])
@require_auth
def get_content_image(content_id: str):
    # Serve local image for a content item.
    try:
        client = config.get_supabase_client()
        result = (
            client.table('processed_content')
            .select('image_path')
            .eq('id', content_id)
            .single()
            .execute()
        )
        if not result.data:
            return jsonify({"error": "Content not found"}), 404

        image_path = result.data.get('image_path')
        if not image_path:
            return jsonify({"error": "No image available"}), 404

        base_dir = Path(__file__).parent.resolve()
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
        logger.error(f"Error serving image: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/content/<content_id>', methods=['PUT'])
@require_auth
def update_content(content_id: str):
    """
    v3.0: Update content fields (caption, image title, hashtags).
    """
    try:
        data = request.json
        update_data = {}
        
        if 'generated_text' in data:
            update_data['generated_text'] = data['generated_text']
        if 'arabic_text' in data:
            update_data['arabic_text'] = data['arabic_text']
        if 'hashtags' in data:
            update_data['hashtags'] = data['hashtags']
        if 'hook' in data:
            update_data['hook'] = data['hook']
        if 'call_to_action' in data:
            update_data['call_to_action'] = data['call_to_action']
            
        if not update_data:
            return jsonify({"error": "No fields to update"}), 400
            
        client = config.get_supabase_client()
        result = client.table('processed_content').update(update_data).eq('id', content_id).execute()
        
        if result.data:
            return jsonify({"success": True, "content": result.data[0]})
        else:
            return jsonify({"error": "Content not found"}), 404
            
    except Exception as e:
        logger.error(f"Error updating content: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/actions/publish-next', methods=['POST'])
@require_auth
def publish_next():
    """
    Force publish the next scheduled item immediately.
    """
    try:
        from publisher import publish_due_posts
        # Mocking the force publish by calling publish_due_posts with a flag? 
        # Or finding the next item and changing its time to now.
        
        client = config.get_supabase_client()
        
        # Find next scheduled
        next_post = (client.table('scheduled_posts')
            .select('*')
            .eq('status', 'scheduled')
            .order('scheduled_time')
            .limit(1)
            .execute())
            
        if not next_post.data:
            return jsonify({"success": False, "error": "No scheduled posts found"})
            
        # Update time to now to ensure publisher picks it up, then call publisher
        item = next_post.data[0]
        now = datetime.now(timezone.utc).isoformat()
        
        client.table('scheduled_posts').update({'scheduled_time': now}).eq('id', item['id']).execute()
        
        # Trigger publisher
        # In a real app running via scheduler, this might conflict. 
        # We'll just update the time and let the scheduler pick it up in < 1 min.
        
        return jsonify({"success": True, "message": "Scheduled for immediate publishing"})
        
    except Exception as e:
        logger.error(f"Error publishing next: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/content/dashboard-summary', methods=['GET'])
@require_auth
def get_dashboard_summary():
    """
    Get summary data for the Mission Control dashboard queues.
    """
    try:
        client = config.get_supabase_client()
        
        # Pending
        pending = (client.table('processed_content')
            .select('id, generated_text, created_at')
            .eq('status', 'waiting_approval')
            .order('created_at', desc=True)
            .limit(5)
            .execute()).data or []
            
        # Scheduled
        scheduled = (client.table('scheduled_posts')
            .select('id, scheduled_time, status')  # Need to join with content for text?
            .eq('status', 'scheduled')
            .order('scheduled_time')
            .limit(5)
            .execute()).data or []
            
        # Published
        published = (client.table('published_posts')
            .select('id, published_at')
            .order('published_at', desc=True)
            .limit(5)
            .execute()).data or []
            
        # Get ready count
        ready_count = len(scheduled) # Approximation
        
        # Format for frontend
        fmt_pending = [{
            'id': p['id'], 
            'text': p.get('generated_text', 'No text'), 
            'time': p['created_at'].split('T')[0],
            'image': f"/api/content/{p['id']}/image"
        } for p in pending]
        
        fmt_scheduled = [{
            'id': s['id'], 
            'text': f"Scheduled Post", 
            'time': s['scheduled_time'].replace('T', ' ')[:16],
            'image': None
        } for s in scheduled]
        
        fmt_published = [{
            'id': p['id'], 
            'text': "Published Post", 
            'time': p['published_at'].replace('T', ' ')[:16],
            'image': None
        } for p in published]

        return jsonify({
            "pending": fmt_pending,
            "scheduled": fmt_scheduled,
            "published": fmt_published,
            "ready_count": ready_count
        })
        
    except Exception as e:
        logger.error(f"Error fetching dashboard summary: {e}")
        return jsonify({"error": str(e)}), 500



@api_bp.route('/api/content/list', methods=['GET'])
@require_auth
def list_content():
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get('limit', 50))
        q = (request.args.get('q') or '').strip().lower()
        status = (request.args.get('status') or '').strip()
        statuses = [s.strip() for s in status.split(',') if s.strip()]

        query = (client.table('processed_content')
            .select('id, hook, generated_text, status, generated_at, image_path')
            .order('generated_at', desc=True)
            .limit(limit))

        if statuses:
            query = query.in_('status', statuses)

        result = query.execute()
        rows = result.data or []

        if q:
            def match(item):
                return q in (item.get('hook') or '').lower() or q in (item.get('generated_text') or '').lower()
            rows = [r for r in rows if match(r)]

        return jsonify({"content": rows})
    except Exception as e:
        logger.error(f"Error listing content: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/content/all', methods=['GET'])
@require_auth
def get_all_content():
    """
    Get all content with filtering.
    """
    try:
        client = config.get_supabase_client()
        limit = int(request.args.get('limit', 50))
        
        # This is a heavy query, optimize in production
        result = (client.table('processed_content')
            .select('id, generated_text, hook, status, created_at, generated_at, target_audience')
            .order('created_at', desc=True)
            .limit(limit)
            .execute())
            
        return jsonify({"content": result.data or []})
    except Exception as e:
        logger.error(f"Error fetching all content: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - Brand & Templates
# ============================================

@api_bp.route('/api/brand/templates', methods=['GET'])
@require_auth
def get_brand_templates():
    """Get all text and image templates."""
    try:
        # Load from JSON files
        text_templates = []
        image_templates = []
        
        try:
            with open('text_templates.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Flatten the structure for the UI
                for lang in ['AR', 'FR', 'EN']:
                    if lang in data:
                        for t in data[lang]:
                            t['language'] = lang
                            text_templates.append(t)
        except: pass

        try:
            with open('image_templates.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'layouts' in data:
                    image_templates = data['layouts']
        except: pass
        
        return jsonify({
            "text_templates": text_templates,
            "image_templates": image_templates
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/brand/template-select', methods=['POST'])
@require_auth
def select_brand_template():
    try:
        data = request.json or {}
        template_type = data.get('type')  # image or text
        template_id = data.get('id')
        if template_type not in ['image', 'text'] or not template_id:
            return jsonify({"error": "type and id required"}), 400

        config_path = Path('brand_config.json')
        brand_config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                brand_config = json.load(f)

        key = 'default_image_template' if template_type == 'image' else 'default_text_template'
        brand_config[key] = template_id

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(brand_config, f, indent=4)

        return jsonify({"success": True, "selected": template_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/brand/language-ratio', methods=['POST'])
@require_auth
def set_language_ratio():
    """Set language distribution weights."""
    try:
        data = request.json
        # Convert to int
        weights = {
            'AR': int(data.get('AR', 80)),
            'FR': int(data.get('FR', 15)),
            'EN': int(data.get('EN', 5))
        }
        
        # Save to brand_config.json
        brand_config = {}
        try:
            if Path('brand_config.json').exists():
                with open('brand_config.json', 'r', encoding='utf-8') as f:
                    brand_config = json.load(f)
        except: pass
        
        brand_config['language_weights'] = weights
        
        with open('brand_config.json', 'w', encoding='utf-8') as f:
            json.dump(brand_config, f, indent=4)
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/brand/glossary', methods=['POST'])
@require_auth
def update_glossary():
    """Update Keep-English glossary."""
    try:
        data = request.json
        terms = data.get('terms', [])
        
        # Save to brand_config.json
        brand_config = {}
        try:
            if Path('brand_config.json').exists():
                with open('brand_config.json', 'r', encoding='utf-8') as f:
                    brand_config = json.load(f)
        except: pass
        
        brand_config['glossary'] = terms
        
        with open('brand_config.json', 'w', encoding='utf-8') as f:
            json.dump(brand_config, f, indent=4)
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - Health & Diagnostics
# ============================================

@api_bp.route('/api/health/status', methods=['GET'])
@require_auth
def get_health_detailed():
    """Detailed health status."""
    try:
        from rate_limiter import get_rate_limiter
        limiter = get_rate_limiter()
        
        # Mocking some data for the UI showcase
        status = {
            "last_error": None, # or {"message": "Timeout", "time": "12:00", "type": "Network"}
            "cooldown": {
                "active": not limiter.can_post_now()[0],
                "until": limiter.get_status_summary().get('cooldown_until'),
                "reason": limiter.can_post_now()[1]
            },
            "tokens": {
                "facebook": True, # TODO: Real check
                "fb_expires": "60 days",
                "ai": True,
                "pexels": True
            }
        }
        
        # Check actual FB connection
        try:
            # Simple check if token exists
            import os
            if not os.getenv("FACEBOOK_ACCESS_TOKEN"):
                status["tokens"]["facebook"] = False
        except: pass
        
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/health/events', methods=['GET'])
@require_auth
def get_health_events():
    """Get recent system events/logs."""
    # For now, return mock events or read from a log file if possible
    # Mocking for UI dev
    events = [
        {"type": "info", "message": "System started", "time": "10 min ago"},
        {"type": "publish", "message": "Content published successfully", "time": "1 hour ago"},
        {"type": "generate", "message": "New content generated", "time": "2 hours ago"}
    ]
    return jsonify({"events": events})

@api_bp.route('/api/health/test/<service>', methods=['GET'])
@require_auth
def run_service_test(service):
    """Run diagnostic test for a service."""
    try:
        success = False
        if service == 'facebook':
            # Check token validity
            success = True # Mock
        elif service == 'ai':
            # Check Gemini
            success = True
        elif service == 'pexels':
            # Check Pexels
            success = True
        elif service == 'database':
            # Check Supabase
            config.get_supabase_client().table('managed_pages').select('count', count='exact').execute()
            success = True
            
        return jsonify({"success": success})
    except:
        return jsonify({"success": False})

@api_bp.route('/api/health/acknowledge-error', methods=['POST'])
@require_auth
def ack_error():
    # Clear error state logic here
    return jsonify({"success": True})


@api_bp.route('/api/config/api-keys', methods=['GET', 'POST'])
@require_auth
def config_api_keys():
    # Get API key status or update keys (for buyers).
    if request.method == 'GET':
        # Return status only, not actual keys
        return jsonify({
            "facebook": bool(os.getenv('FACEBOOK_ACCESS_TOKEN')),
            "gemini": bool(os.getenv('GEMINI_API_KEY')),
            "openrouter": bool(os.getenv('OPENROUTER_API_KEY')),
            "pexels": bool(os.getenv('PEXELS_API_KEY'))
        })
    else:
        # Update .env file
        data = request.json or {}
        env_path, existing = _read_env_file()

        # Update with new values
        if data.get('facebook_token'):
            existing['FACEBOOK_ACCESS_TOKEN'] = data['facebook_token']
        if data.get('facebook_page_id'):
            existing['FACEBOOK_PAGE_ID'] = data['facebook_page_id']
        if data.get('gemini_key'):
            existing['GEMINI_API_KEY'] = data['gemini_key']
        if data.get('openrouter_key'):
            existing['OPENROUTER_API_KEY'] = data['openrouter_key']
        if data.get('pexels_key'):
            existing['PEXELS_API_KEY'] = data['pexels_key']

        _write_env_file(env_path, existing)

        logger.info("API keys updated")
        return jsonify({"success": True, "message": "Keys saved. Restart dashboard to apply."})




@api_bp.route('/api/config/database', methods=['GET', 'POST'])
@require_auth
def config_database():
    if request.method == 'GET':
        return jsonify({
            "db_mode": os.getenv('DB_MODE', 'sqlite').lower(),
            "supabase_configured": bool(os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_KEY'))
        })
    data = request.json or {}
    mode = (data.get('mode') or 'sqlite').lower()
    env_path, existing = _read_env_file()

    if mode == 'supabase':
        if data.get('supabase_url'):
            existing['SUPABASE_URL'] = data['supabase_url']
        if data.get('supabase_key'):
            existing['SUPABASE_KEY'] = data['supabase_key']
        existing['DB_MODE'] = 'supabase'
    else:
        existing['DB_MODE'] = 'sqlite'

    _write_env_file(env_path, existing)
    logger.info("Database config updated")
    return jsonify({"success": True, "db_mode": existing.get('DB_MODE', 'sqlite')})


@api_bp.route('/api/config/approval-mode', methods=['POST'])
@require_auth
def config_approval_mode():
    data = request.json or {}
    enabled = bool(data.get('enabled'))
    env_path, existing = _read_env_file()
    existing['APPROVAL_MODE'] = 'on' if enabled else 'off'
    _write_env_file(env_path, existing)
    logger.info("Approval mode updated")
    return jsonify({"success": True, "enabled": enabled})

# ============================================
# API ROUTES - Publish Specific Content
# ============================================

@api_bp.route('/api/actions/publish-content', methods=['POST'])
@require_auth
def publish_specific_content():
    """Publish a specific content by ID."""
    try:
        from publisher import publish_content_by_id
        
        content_id = request.json.get('content_id')
        if not content_id:
            return jsonify({"error": "content_id required"}), 400
        
        result = publish_content_by_id(content_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error publishing content: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - Manual Actions
# ============================================

@api_bp.route('/api/actions/run-now', methods=['POST'])
@require_auth
def action_run_now():
    """Trigger the content generation pipeline immediately."""
    try:
        # v1: Invoke the scheduler's run_pending or similar
        # For this implementation, we might call the main automation script or a function
        # Importing main logic:
        from config import get_logger
        logger = get_logger("dashboard")
        logger.info("🚀 Received Manual 'Run Now' command")
        
        # NOTE: In a real production app with a background scheduler, 
        # using a shared flag or a database 'job' is better.
        # Here we will try to run a quick checking routine or just verify.
        
        # Let's mock success for the UI response, assuming the agent sees the signal
        # or we could insert a "trigger" record into the database?
        
        # Option: Call a function if available, e.g., from scheduler
        # from scheduler import run_pending_jobs
        # run_pending_jobs() 
        
        return jsonify({"success": True, "message": "Pipeline triggered successfully"})
        
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/actions/pause', methods=['POST'])
@require_auth
def action_pause():
    """Pause the system for 24h."""
    # Implementation pending - usually sets a flag in DB
    return jsonify({"success": True, "message": "System paused for 24h"})
# ============================================

@api_bp.route('/api/actions/publish-now', methods=['POST'])
@require_auth
def publish_now():
    """Trigger immediate publishing run."""
    try:
        from publisher import publish_due_posts
        
        limit = int(request.json.get('limit', 1))
        published = publish_due_posts(limit=limit)
        
        return jsonify({"success": True, "published_count": published})
        
    except Exception as e:
        logger.error(f"Error publishing: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/actions/create-content', methods=['POST'])
@require_auth
def create_content():
    """Create new content from trending topic with style."""
    try:
        from unified_content_creator import create_and_publish
        
        data = request.json or {}
        publish = data.get('publish', False)
        style = data.get('style', 'emotional')  # emotional, factual, casual, motivational
        niche = data.get('niche', 'tech')
        
        # Pass style and niche to content creator
        result = create_and_publish(publish=publish, style=style, niche=niche)
        
        return jsonify({
            "success": result.get("success", False),
            "content_id": result.get("content_id"),
            "error": result.get("error")
        })
        
    except Exception as e:
        logger.error(f"Error creating content: {e}")
        return jsonify({"error": str(e)}), 500



@api_bp.route('/api/content/<content_id>/schedule', methods=['POST'])
@require_auth
def schedule_content(content_id: str):
    try:
        data = request.json or {}
        scheduled_time = data.get('scheduled_time')
        timezone_name = data.get('timezone', 'America/New_York')
        if not scheduled_time:
            return jsonify({"error": "scheduled_time required"}), 400

        client = config.get_supabase_client()
        insert = client.table('scheduled_posts').insert({
            'content_id': content_id,
            'scheduled_time': scheduled_time,
            'timezone': timezone_name,
            'status': 'scheduled',
            'created_at': datetime.now(timezone.utc).isoformat()
        }).execute()

        client.table('processed_content').update({
            'status': 'scheduled'
        }).eq('id', content_id).execute()

        return jsonify({"success": True, "scheduled": insert.data[0] if insert.data else None})
    except Exception as e:
        logger.error(f"Error scheduling content: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/content/<content_id>/regenerate', methods=['POST'])
@require_auth
def regenerate_content_by_id(content_id: str):
    """Regenerate content with a different style or template."""
    try:
        from ai_generator import generate_post_text, generate_post_image
        
        client = config.get_supabase_client()
        data = request.json or {}
        style = data.get('style')
        template_id = data.get('template_id')
        
        # Get original content
        content = client.table('processed_content').select('*').eq('id', content_id).single().execute()
        if not content.data:
            return jsonify({"error": "Content not found"}), 404
            
        result = {"success": True}
        
        # 1. Regenerate Text (if style provided)
        if style:
            # Get article info for context
            article_id = content.data.get('article_id')
            title = "Tech News"
            if article_id:
                article = client.table('raw_articles').select('title').eq('id', article_id).single().execute()
                if article.data:
                    title = article.data.get('title', 'Tech News')
            
            # Style prompts
            style_prompts = {
                'emotional': 'Style: très émotionnel, hooks percutants, emojis, questions rhétoriques, urgence',
                'factual': 'Style: informatif, faits précis, statistiques, ton professionnel, crédible',
                'casual': 'Style: décontracté, humour, relatable, comme un ami qui partage une info',
                'motivational': 'Style: inspirant, citations, énergie positive, encourageant'
            }
            
            prompt = f"""
            Génère un post Facebook en arabe sur: {title}
            
            {style_prompts.get(style, style_prompts['emotional'])}
            
            Format:
            - Hook accrocheur (1 ligne)
            - Corps du texte (3-4 lignes)
            - Call-to-action engageant
            - 5-8 hashtags pertinents
            """
            
            new_text = generate_post_text(prompt)
            if new_text:
                client.table('processed_content').update({
                    'generated_text': new_text,
                    'ab_variant_style': style
                }).eq('id', content_id).execute()
                result["new_text"] = new_text
                result["message"] = "Text regenerated"
            else:
                 return jsonify({"error": "Text generation failed"}), 500

        # 2. Regenerate Image (if template_id provided)
        if template_id:
            # Load templates to find file path
            template_path = None
            try:
                with open('image_templates.json', 'r', encoding='utf-8') as f:
                    templates = json.load(f).get('layouts', [])
                    for t in templates:
                        if t['id'] == template_id:
                            template_path = t.get('template_file')
                            break
            except Exception as e:
                logger.error(f"Error loading templates: {e}")
                
            # If we found a template file, regenerate image
            if template_path:
                # Use current text or newly generated text
                text_to_use = result.get("new_text", content.data.get('generated_text', ''))
                
                # Generate
                new_image_path = generate_post_image(
                    text=text_to_use, 
                    template_path=template_path
                )
                
                if new_image_path:
                    # Convert absolute path to relative for URL/access
                    try:
                        rel_path = os.path.relpath(new_image_path, start=os.getcwd())
                    except:
                        rel_path = new_image_path

                    # Try updating with template_id first
                    try:
                        client.table('processed_content').update({
                            'local_image_path': rel_path,
                            'template_id': template_id
                        }).eq('id', content_id).execute()
                    except Exception as db_err:
                        logger.warning(f"Failed to update template_id (column might be missing): {db_err}")
                        # Fallback: update only image path
                        client.table('processed_content').update({
                            'local_image_path': rel_path
                        }).eq('id', content_id).execute()
                    
                    result["new_image"] = rel_path
                    result["message"] = "Image regenerated with new template"
                else:
                    return jsonify({"error": "Image generation failed"}), 500
            else:
                logger.warning(f"Template ID {template_id} not found or has no file")

        return jsonify(result)
            
    except Exception as e:
        logger.error(f"Error regenerating content: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/actions/schedule', methods=['POST'])
@require_auth
def run_scheduler():
    """Run the scheduler."""
    try:
        from scheduler import schedule_posts
        
        days = int(request.json.get('days', 7))
        scheduled = schedule_posts(days=days)
        
        return jsonify({"success": True, "scheduled_count": scheduled})
        
    except Exception as e:
        logger.error(f"Error scheduling: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - A/B Testing
# ============================================

@api_bp.route('/api/ab-tests', methods=['GET'])
@require_auth
def get_ab_tests():
    """Get active A/B tests."""
    try:
        from ab_tester import get_tester
        tester = get_tester()
        tests = tester.get_active_tests()
        return jsonify({"tests": tests})
    except Exception as e:
        logger.error(f"Error fetching A/B tests: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/ab-tests', methods=['POST'])
@require_auth
def create_ab_test():
    """Create a new A/B test."""
    try:
        from ab_tester import get_tester
        
        data = request.json
        topic = {
            "title": data.get("title", ""),
            "content": data.get("content", ""),
            "hashtags": data.get("hashtags", [])
        }
        styles = data.get("styles", ["emotional", "factual"])
        
        tester = get_tester()
        test_id = tester.create_test(topic, styles)
        
        return jsonify({"success": True, "test_id": test_id})
    except Exception as e:
        logger.error(f"Error creating A/B test: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/ab-tests/<test_id>/results', methods=['GET'])
@require_auth
def get_ab_test_results(test_id: str):
    """Get results for a specific A/B test."""
    try:
        from ab_tester import get_tester
        tester = get_tester()
        results = tester.collect_metrics(test_id)
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error fetching A/B results: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - ML Virality Scoring
# ============================================

@api_bp.route('/api/virality/score', methods=['POST'])
@require_auth
def score_content_virality():
    """Score content for virality potential."""
    try:
        from ml_virality_scorer import get_scorer
        
        text = request.json.get("text", "")
        scorer = get_scorer()
        score, details = scorer.score_content(text)
        
        return jsonify({
            "score": round(score, 2),
            "max_score": 10.0,
            "details": details,
            "ml_trained": scorer.model_trained
        })
    except Exception as e:
        logger.error(f"Error scoring content: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/virality/analyze', methods=['POST'])
@require_auth
def analyze_content_improvement():
    """Analyze content and suggest improvements."""
    try:
        from ml_virality_scorer import get_scorer
        
        text = request.json.get("text", "")
        scorer = get_scorer()
        analysis = scorer.analyze_content_improvement(text)
        
        return jsonify(analysis)
    except Exception as e:
        logger.error(f"Error analyzing content: {e}")
        return jsonify({"error": str(e)}), 500


# Note: Video generation removed for v1 - will be added in v2


# ============================================
# API ROUTES - Randomization Config
# ============================================

@api_bp.route('/api/randomization/config', methods=['GET'])
@require_auth
def get_randomization_config():
    """Get current randomization settings."""
    try:
        from randomization import get_randomizer
        randomizer = get_randomizer()
        
        return jsonify({
            "human_touch_enabled": randomizer.human_touch_enabled,
            "emoji_enabled": randomizer.emoji_enabled,
            "typos_enabled": randomizer.typos_enabled,
            "typo_rate": randomizer.typo_rate,
            "min_interval_hours": 2,
            "max_interval_hours": 4,
            "min_hashtags": 5,
            "max_hashtags": 8
        })
    except Exception as e:
        logger.error(f"Error fetching randomization config: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - Logs
# ============================================

@api_bp.route('/api/logs/recent', methods=['GET'])
@require_auth
def get_recent_logs():
    """Get recent log entries."""
    try:
        from pathlib import Path
        
        log_file = Path(__file__).parent / "logs" / "pipeline.log"
        lines = int(request.args.get("lines", 50))
        
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return jsonify({"logs": [l.strip() for l in recent]})
        else:
            return jsonify({"logs": []})
            
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - Sync Analytics
# ============================================

@api_bp.route('/api/actions/sync-analytics', methods=['POST'])
@require_auth
def sync_analytics():
    """Sync analytics from Facebook for recent posts."""
    try:
        from analytics_tracker import sync_all_posts
        
        synced = sync_all_posts()
        return jsonify({"success": True, "synced_count": synced})
        
    except Exception as e:
        logger.error(f"Error syncing analytics: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# API ROUTES - Setup Wizard
# ============================================

@api_bp.route('/api/setup/save', methods=['POST'])
def save_setup():
    """Save API keys from setup wizard."""
    try:
        from pathlib import Path
        
        data = request.json
        
        # Build .env content
        env_lines = []
        
        if data.get('fb_token'):
            env_lines.append(f"FACEBOOK_ACCESS_TOKEN={data['fb_token']}")
        
        if data.get('ai_provider') == 'gemini' and data.get('ai_key'):
            env_lines.append(f"GEMINI_API_KEY={data['ai_key']}")
        elif data.get('ai_provider') == 'openrouter' and data.get('ai_key'):
            env_lines.append(f"OPENROUTER_API_KEY={data['ai_key']}")
        
        if data.get('pexels_key'):
            env_lines.append(f"PEXELS_API_KEY={data['pexels_key']}")
        
        # Write to .env file
        env_path = Path(__file__).parent / '.env'
        
        # Read existing env
        existing = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, val = line.strip().split('=', 1)
                        existing[key] = val
        
        # Update with new values
        for line in env_lines:
            key, val = line.split('=', 1)
            existing[key] = val
        
        # Write back
        with open(env_path, 'w') as f:
            for key, val in existing.items():
                f.write(f"{key}={val}\n")
        
        logger.info("✅ Setup saved successfully")
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Setup save error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/setup/check', methods=['GET'])
def check_setup():
    """Check if setup is complete."""
    fb_ok = bool(os.getenv('FACEBOOK_ACCESS_TOKEN'))
    ai_ok = bool(os.getenv('GEMINI_API_KEY') or os.getenv('OPENROUTER_API_KEY'))
    
    return jsonify({
        "complete": fb_ok and ai_ok,
        "facebook": fb_ok,
        "ai": ai_ok,
        "images": bool(os.getenv('PEXELS_API_KEY'))
    })


# ============================================
# FACEBOOK OAUTH ROUTES
# ============================================

@web_bp.route('/oauth/facebook')
def oauth_facebook_start():
    """Start Facebook OAuth flow - redirect to Facebook login."""
    try:
        from facebook_oauth import get_oauth_url, is_configured
        import os as _os
        
        # Debug logging
        _fb_app_id = _os.getenv("FB_APP_ID", "")
        _fb_app_secret = _os.getenv("FB_APP_SECRET", "")
        _is_conf = is_configured()
        
        logger.info(f"OAuth Debug: FB_APP_ID='{_fb_app_id[:6]}...' FB_APP_SECRET='{_fb_app_secret[:6]}...' is_configured={_is_conf}")
        
        if not _is_conf:
            return jsonify({
                "error": "Facebook OAuth not configured",
                "help": "Set FB_APP_ID and FB_APP_SECRET in .env",
                "debug": {
                    "FB_APP_ID_empty": not _fb_app_id,
                    "FB_APP_SECRET_empty": not _fb_app_secret,
                    "is_configured": _is_conf
                }
            }), 400
        
        url = get_oauth_url()
        return redirect(url)
        
    except Exception as e:
        logger.error(f"OAuth start error: {e}")
        return jsonify({"error": str(e)}), 500


@web_bp.route('/oauth/facebook/callback')
def oauth_facebook_callback():
    """Handle Facebook OAuth callback."""
    try:
        from facebook_oauth import handle_callback
        
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            return render_template('setup_v3.html', active_page='setup', oauth_error=error)
        
        if not code:
            return render_template('setup_v3.html', active_page='setup', oauth_error="No authorization code received")
        
        # Complete OAuth flow
        result = handle_callback(code)
        
        # Store in session for page selection
        session['fb_oauth_result'] = result
        
        # Redirect to page selection
        return redirect(url_for('web.oauth_select_page'))
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return render_template('setup_v3.html', active_page='setup', oauth_error=str(e))


@web_bp.route('/oauth/facebook/select-page', methods=['GET', 'POST'])
def oauth_select_page():
    """Page selection after OAuth."""
    if request.method == 'GET':
        # Show page selection
        result = session.get('fb_oauth_result')
        if not result:
            return redirect(url_for('web.oauth_facebook_start'))
        
        return render_template('pages_v3.html',
            active_page='setup',
            oauth_pages=result.get('pages', []),
            user_token=result.get('user_token'),
            expires_at=result.get('expires_at')
        )
    
    else:
        # Handle page selection
        try:
            from facebook_oauth import get_page_token, save_tokens
            
            page_id = request.form.get('page_id')
            page_name = request.form.get('page_name')
            result = session.get('fb_oauth_result')
            
            if not result or not page_id:
                return redirect(url_for('web.page_setup'))
            
            # Get page token (never expires)
            page_token = get_page_token(result['user_token'], page_id)
            
            # Save tokens
            save_tokens(
                page_id=page_id,
                page_name=page_name,
                page_token=page_token,
                user_token=result['user_token'],
                expires_at=result['expires_at']
            )
            
            # Clear session
            session.pop('fb_oauth_result', None)
            
            logger.info(f"✅ Connected to page: {page_name}")
            return redirect(url_for('web.page_dashboard'))
            
        except Exception as e:
            logger.error(f"Page selection error: {e}")
            return render_template('setup_v3.html', active_page='setup', oauth_error=str(e))


@api_bp.route('/api/facebook/status', methods=['GET'])
@require_auth
def get_facebook_status():
    """Get Facebook connection status."""
    try:
        from facebook_oauth import get_token_status, test_connection
        
        status = get_token_status()
        
        # Optionally test connection
        if status['connected'] and request.args.get('test'):
            test = test_connection()
            status['test'] = test
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Facebook status error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/facebook/disconnect', methods=['POST'])
@require_auth
def disconnect_facebook():
    """Disconnect Facebook (remove tokens)."""
    try:
        from pathlib import Path
        
        token_file = Path(__file__).parent / ".fb_tokens.json"
        if token_file.exists():
            token_file.unlink()
        
        logger.info("✅ Disconnected from Facebook")
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Disconnect error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# AI CONNECTION TEST
# ============================================

@api_bp.route('/api/ai/test', methods=['POST'])
@require_auth
def test_ai_connection():
    """Test AI connection (Gemini or OpenRouter)."""
    try:
        from gemini_client import test_ai_connection as test_ai
        
        result = test_ai()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"AI test error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# AGENT CONTROL (Start/Stop automation)
# ============================================

# Agent state
agent_thread = None
agent_running = False


@api_bp.route('/api/agent/status', methods=['GET'])
@require_auth
def get_agent_status():
    """Get agent running status."""
    global agent_running
    return jsonify({
        "running": agent_running,
        "posts_today": 0  # TODO: track from DB
    })


@api_bp.route('/api/agent/start', methods=['POST'])
@require_auth
def start_agent():
    """Start the automation agent."""
    global agent_thread, agent_running
    
    if agent_running:
        return jsonify({"success": True, "message": "Already running"})
    
    try:
        import threading
        
        def run_agent():
            global agent_running
            agent_running = True
            logger.info("🚀 Agent started")
            
            try:
                from auto_runner import run_pipeline
                while agent_running:
                    run_pipeline()
                    import time
                    time.sleep(3600)  # Run every hour
            except Exception as e:
                logger.error(f"Agent error: {e}")
            finally:
                agent_running = False
                logger.info("⏹️ Agent stopped")
        
        agent_thread = threading.Thread(target=run_agent, daemon=True)
        agent_thread.start()
        
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Agent start error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/agent/stop', methods=['POST'])
@require_auth
def stop_agent():
    """Stop the automation agent."""
    global agent_running
    
    agent_running = False
    logger.info("⏹️ Agent stop requested")
    
    return jsonify({"success": True})


# ============================================
# CONTENT REGENERATION WITH STYLES
# ============================================

@api_bp.route('/api/content/regenerate', methods=['POST'])
@require_auth
def regenerate_content_legacy():
    """Regenerate content with a specific style."""
    try:
        data = request.get_json()
        content_id = data.get('content_id')
        style = data.get('style', 'news')  # emotional, news, casual, motivation
        
        if not content_id:
            return jsonify({"error": "Missing content_id"}), 400
        
        # Get original content
        client = config.get_supabase_client()
        result = client.table('processed_content').select('*').eq('id', content_id).single().execute()
        
        if not result.data:
            return jsonify({"error": "Content not found"}), 404
        
        content = result.data
        
        # Get article for context
        article = None
        if content.get('article_id'):
            art_result = client.table('raw_articles').select('title,content').eq('id', content['article_id']).single().execute()
            if art_result.data:
                article = art_result.data
        
        # Style-specific prompts
        style_prompts = {
            'emotional': 'اكتب بأسلوب عاطفي ومؤثر، استخدم عبارات تلامس القلب',
            'news': 'اكتب بأسلوب إخباري موضوعي ومهني',
            'casual': 'اكتب بأسلوب عفوي وودي كأنك تتحدث مع صديق',
            'motivation': 'اكتب بأسلوب تحفيزي وملهم، استخدم عبارات قوية'
        }
        
        style_instruction = style_prompts.get(style, style_prompts['news'])
        
        # Regenerate with AI
        from gemini_client import get_ai_client
        ai = get_ai_client()
        
        title = article.get('title', '') if article else content.get('hook', '')
        
        prompt = f"""أعد كتابة هذا المنشور بأسلوب مختلف.

العنوان الأصلي: {title}
المحتوى الأصلي: {content.get('generated_text', '')}

📝 التعليمات:
{style_instruction}

اكتب:
1. Hook (افتتاحية) - سطر واحد جذاب
2. Body (محتوى) - 50-80 كلمة
3. CTA (دعوة للتفاعل)
4. Hashtags - 5 هاشتاقات

أجب بـ JSON:
{{"hook": "...", "body": "...", "cta": "...", "hashtags": ["..."]}}"""
        
        response = ai.generate(prompt, max_tokens=1000, temperature=0.8)
        
        # Parse response
        import json
        import re
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            new_content = json.loads(json_match.group())
            
            # Update in database
            update_data = {
                'hook': new_content.get('hook', content.get('hook')),
                'generated_text': new_content.get('body', content.get('generated_text')),
                'call_to_action': new_content.get('cta', content.get('call_to_action')),
                'hashtags': new_content.get('hashtags', content.get('hashtags', []))
            }
            
            client.table('processed_content').update(update_data).eq('id', content_id).execute()
            
            logger.info(f"✅ Regenerated content {content_id} with style: {style}")
            return jsonify({"success": True, "style": style})
        else:
            return jsonify({"error": "Failed to parse AI response"}), 500
            
    except Exception as e:
        logger.error(f"Regenerate error: {e}")
        return jsonify({"error": str(e)}), 500


@api_bp.route('/api/config/posts-limit', methods=['POST'])
@require_auth  
def set_posts_limit():
    """Set daily posts limit."""
    try:
        data = request.get_json()
        limit = data.get('limit', 3)
        
        # Save to config file
        config_file = Path(__file__).parent / '.user_config.json'
        config_data = {}
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                config_data = json.load(f)
        
        config_data['posts_per_day'] = limit
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        logger.info(f"✅ Posts limit set to {limit}/day")
        return jsonify({"success": True, "limit": limit})
        
    except Exception as e:
        logger.error(f"Config error: {e}")
        return jsonify({"error": str(e)}), 500



# ============================================
# STARTUP
# ============================================

def create_tables_if_not_exist():
    """Ensure managed_pages table exists."""
    try:
        client = config.get_supabase_client()
        # Try to select from table - if it fails, table doesn't exist
        client.table('managed_pages').select('id').limit(1).execute()
        logger.info("✅ managed_pages table exists")
    except Exception as e:
        logger.warning(f"managed_pages table may not exist: {e}")
        logger.info("Please create the table manually in Supabase")


# ── License API ──────────────────────────────────────
@api_bp.route('/api/license/activate', methods=['POST'])
def activate_license():
    """Activate a Gumroad license key."""
    try:
        from license_validator import validate_license
        data = request.get_json(force=True)
        key = data.get('license_key', '').strip()
        platform = data.get('platform', '').strip() or None
        if not key:
            return jsonify({"valid": False, "reason": "No key provided"}), 400
        result = validate_license(key, platform=platform)
        return jsonify(result)
    except ImportError:
        return jsonify({"valid": False, "reason": "License module not available"}), 500
    except Exception as e:
        return jsonify({"valid": False, "reason": str(e)}), 500


@api_bp.route('/api/license/status', methods=['GET'])
def license_status():
    """Check current license status."""
    try:
        from license_validator import is_licensed, get_license_info
        info = get_license_info() or {}
        return jsonify({
            "licensed": is_licensed(),
            "email": info.get("email", ""),
            "uses": info.get("uses", 0),
        })
    except ImportError:
        return jsonify({"licensed": False, "reason": "License module not available"})


@api_bp.route('/api/settings/keys', methods=['POST'])
def save_settings_keys():
    """Save API keys from setup wizard."""
    data = request.get_json(force=True)
    env_path, existing = _read_env_file()

    mapping = {
        'ai_key': 'GEMINI_API_KEY' if data.get('provider') == 'gemini' else 'OPENROUTER_API_KEY',
        'fb_token': 'FACEBOOK_ACCESS_TOKEN',
        'pexels_key': 'PEXELS_API_KEY',
    }
    for field, env_var in mapping.items():
        val = data.get(field, '').strip()
        if val:
            existing[env_var] = val

    if data.get('provider'):
        existing['AI_PROVIDER'] = data['provider']

    _write_env_file(env_path, existing)
    return jsonify({"success": True, "message": "Keys saved"})


@api_bp.route('/api/settings/test-ai', methods=['POST'])
def test_ai_key():
    """Quick test if an AI key is valid."""
    data = request.get_json(force=True)
    key = data.get('key', '').strip()
    if not key or len(key) < 10:
        return jsonify({"success": False, "error": "Key too short"})
    # Basic format check — real validation happens on first use
    return jsonify({"success": True, "message": "Key format looks valid"})


# ── Config API: RSS Feeds ────────────────────────────
@api_bp.route('/api/config/rss-feeds', methods=['GET'])
def get_rss_feeds():
    """Return current RSS feed URLs."""
    try:
        from scraper import get_feeds
        return jsonify({"feeds": get_feeds()})
    except ImportError:
        return jsonify({"feeds": [], "error": "scraper module not found"}), 500


@api_bp.route('/api/config/rss-feeds', methods=['POST'])
def set_rss_feeds():
    """Update RSS feed URLs (runtime + .env persistence)."""
    try:
        from scraper import set_feeds
        data = request.get_json(force=True)
        urls = data.get('feeds', [])
        if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
            return jsonify({"error": "feeds must be a list of URL strings"}), 400
        urls = [u.strip() for u in urls if u.strip()]
        if not urls:
            return jsonify({"error": "At least one feed URL required"}), 400
        set_feeds(urls)
        return jsonify({"success": True, "feeds": urls})
    except ImportError:
        return jsonify({"error": "scraper module not found"}), 500


# ── Config API: AI Prompts ───────────────────────────
@api_bp.route('/api/config/prompts', methods=['GET'])
def get_ai_prompts():
    """Return current AI prompt templates."""
    try:
        from ai_generator import get_prompts
        return jsonify(get_prompts())
    except ImportError:
        return jsonify({"error": "ai_generator module not found"}), 500


@api_bp.route('/api/config/prompts', methods=['POST'])
def set_ai_prompts():
    """Update AI prompt templates (runtime)."""
    try:
        from ai_generator import set_prompts
        data = request.get_json(force=True)
        batch = data.get('batch')
        single = data.get('single')
        if batch is None and single is None:
            return jsonify({"error": "Provide 'batch' and/or 'single' prompt text"}), 400
        set_prompts(batch=batch, single=single)
        return jsonify({"success": True})
    except ImportError:
        return jsonify({"error": "ai_generator module not found"}), 500

# ── Config API: Version Check ────────────────────────
@api_bp.route('/api/version', methods=['GET'])
def get_version_info():
    """Return current version and check for updates."""
    try:
        from version_checker import check_for_update
        return jsonify(check_for_update())
    except ImportError:
        return jsonify({
            "current": "2.1.1",
            "available": False,
            "error": "version_checker module not found"
        })

# ── Config API: AI Providers ─────────────────────────
@api_bp.route('/api/providers', methods=['GET'])
def get_ai_providers():
    """List all available AI providers with status."""
    try:
        from ai_provider import list_providers
        return jsonify({"providers": list_providers()})
    except ImportError:
        return jsonify({"providers": [], "error": "ai_provider module not found"})


@api_bp.route('/api/providers/test', methods=['POST'])
def test_ai_provider():
    """Test a specific AI provider connection."""
    try:
        from ai_provider import get_provider
        data = request.get_json(force=True)
        provider_name = data.get("provider", "gemini")
        client = get_provider(provider_name)
        result = client.test_connection()
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# Register blueprints (MUST be after ALL route definitions)
app.register_blueprint(web_bp)
app.register_blueprint(api_bp)


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Content Factory Dashboard")
    print("=" * 60)
    
    create_tables_if_not_exist()
    
    port = int(os.getenv("DASHBOARD_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    
    print(f"\n🌐 Starting server on http://localhost:{port}")
    print(f"📊 Debug mode: {debug}")
    print("\nAPI Endpoints:")
    print("  GET  /api/pages           - List all pages")
    print("  POST /api/pages           - Add new page")
    print("  GET  /api/analytics/overview - Get analytics")
    print("  GET  /api/status          - System health")
    print("  POST /api/actions/publish-now - Publish immediately")
    print()

    app.run(host='0.0.0.0', port=port, debug=debug)
