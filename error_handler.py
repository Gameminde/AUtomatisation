"""
Error Handler - Smart Retry & Error Classification for Content Factory v2.1.

Centralizes error handling logic with automatic classification and actions:
- Rate Limit (429, #32) -> Cooldown 24h + reduce posting frequency
- Server Error (5xx, timeout) -> Exponential backoff retry (3 attempts)
- Auth/Permission (401, 403) -> NEEDS_ACTION alert (no auto-retry)
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import config
import database

logger = config.get_logger("error_handler")


# Error classification patterns
RATE_LIMIT_PATTERNS = [
    r"#32",
    r"Page request limit reached",
    r"Rate limit",
    r"429",
    r"too many requests",
]

SERVER_ERROR_PATTERNS = [
    r"5\d{2}",
    r"Internal Server Error",
    r"timeout",
    r"Connection reset",
    r"Service Unavailable",
]

AUTH_ERROR_PATTERNS = [
    r"401",
    r"403",
    r"OAuthException",
    r"Invalid OAuth",
    r"access token",
    r"permission",
]


class ErrorAction:
    """Enum-like class for error actions."""
    COOLDOWN = "cooldown"
    RETRY = "retry"
    NEEDS_ACTION = "needs_action"
    IGNORE = "ignore"


def classify_error(error: Exception) -> Tuple[str, str]:
    """
    Classify an error and determine the appropriate action.
    
    Args:
        error: The exception that occurred.
    
    Returns:
        Tuple of (action, error_code) where action is one of ErrorAction constants.
    """
    error_str = str(error).lower()
    
    # Check rate limit first (most critical)
    for pattern in RATE_LIMIT_PATTERNS:
        if re.search(pattern, error_str, re.IGNORECASE):
            logger.warning("🚨 Rate limit detected: %s", error)
            return (ErrorAction.COOLDOWN, "RATE_LIMIT")
    
    # Check auth errors (needs human intervention)
    for pattern in AUTH_ERROR_PATTERNS:
        if re.search(pattern, error_str, re.IGNORECASE):
            logger.error("🔐 Auth/Permission error: %s", error)
            return (ErrorAction.NEEDS_ACTION, "AUTH_ERROR")
    
    # Check server errors (can retry)
    for pattern in SERVER_ERROR_PATTERNS:
        if re.search(pattern, error_str, re.IGNORECASE):
            logger.warning("🌐 Server error, will retry: %s", error)
            return (ErrorAction.RETRY, "SERVER_ERROR")
    
    # Unknown error - retry once then give up
    logger.warning("❓ Unknown error: %s", error)
    return (ErrorAction.RETRY, "UNKNOWN")


def execute_action(
    action: str,
    content_id: str,
    error_code: str,
    retry_count: int = 0
) -> bool:
    """
    Execute the appropriate action based on error classification.
    
    Args:
        action: The action to execute (from ErrorAction).
        content_id: The ID of the content that failed.
        error_code: The classified error code.
        retry_count: Current retry count for this content.
    
    Returns:
        True if the post should be retried, False otherwise.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    if action == ErrorAction.COOLDOWN:
        # Set global cooldown and reschedule post for 24h later
        cooldown_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        
        # Update system status
        _update_system_status(db, "cooldown_until", cooldown_until)
        _update_system_status(db, "last_error_code", error_code)
        _update_system_status(db, "last_error_action", "cooldown_24h")
        
        # Reschedule the content
        db.table("processed_content").update({
            "status": "retry_scheduled",
            "last_error": error_code,
            "last_error_at": now,
            "retry_count": retry_count + 1
        }).eq("id", content_id).execute()
        
        logger.warning("⏸️ Cooldown activated until %s", cooldown_until)
        return False
    
    elif action == ErrorAction.RETRY:
        max_retries = 3
        if retry_count >= max_retries:
            # Max retries reached, mark as failed
            db.table("processed_content").update({
                "status": "failed",
                "last_error": f"{error_code} (max retries)",
                "last_error_at": now
            }).eq("id", content_id).execute()
            
            _update_system_status(db, "last_error_code", error_code)
            _update_system_status(db, "last_error_action", "failed_max_retries")
            
            logger.error("❌ Max retries reached for %s", content_id)
            return False
        
        # Calculate exponential backoff delay
        delay_minutes = 2 ** retry_count * 5  # 5, 10, 20 minutes
        next_retry_dt = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        next_retry_at = next_retry_dt.isoformat()
        
        db.table("processed_content").update({
            "status": "retry_scheduled",
            "last_error": error_code,
            "last_error_at": now,
            "retry_count": retry_count + 1,
            "next_retry_at": next_retry_at 
        }).eq("id", content_id).execute()
        
        logger.info("🔄 Retry scheduled for %s (attempt %d/%d)", 
                   next_retry_at, retry_count + 1, max_retries)
        return True
    
    elif action == ErrorAction.NEEDS_ACTION:
        # Mark as failed and alert (no auto-retry)
        db.table("processed_content").update({
            "status": "failed",
            "last_error": f"{error_code} - NEEDS MANUAL ACTION",
            "last_error_at": now
        }).eq("id", content_id).execute()
        
        _update_system_status(db, "last_error_code", error_code)
        _update_system_status(db, "last_error_action", "needs_action")
        
        logger.error("🚨 NEEDS MANUAL ACTION: %s for content %s", error_code, content_id)
        # TODO: Send notification (Discord/Telegram) here
        return False
    
    return False


def is_in_cooldown() -> bool:
    """Check if the system is currently in cooldown mode."""
    db = database.get_db()
    
    try:
        result = db.table("system_status").select("value").eq("key", "cooldown_until").single().execute()
        if result.data and result.data.get("value"):
            cooldown_until = datetime.fromisoformat(result.data["value"])
            if datetime.now(timezone.utc) < cooldown_until:
                logger.warning("🛑 System in cooldown until %s", cooldown_until)
                return True
    except Exception:
        pass
    
    return False


def get_recent_error_rate(hours: int = 24) -> float:
    """
    Calculate error rate over the last N hours.
    
    v2.1.1: Excludes 'rejected' status (user rejections are not system errors).
    
    Returns:
        Float between 0.0 and 1.0 representing error rate.
    """
    db = database.get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    
    try:
        # Count failed posts (excluding 'rejected' which is user-initiated)
        failed = db.table("processed_content").select("id", count="exact").eq(
            "status", "failed"
        ).gte("last_error_at", cutoff).execute()
        
        # Count successful posts
        success = db.table("processed_content").select("id", count="exact").eq(
            "status", "published"
        ).gte("generated_at", cutoff).execute()
        
        # v2.1.1: Don't count rejected as failures (they are user-initiated)
        total = (failed.count or 0) + (success.count or 0)
        if total == 0:
            return 0.0
        
        error_rate = (failed.count or 0) / total
        logger.debug("Error rate: %.2f%% (failed=%d, success=%d)", 
                    error_rate * 100, failed.count or 0, success.count or 0)
        return error_rate
    except Exception as e:
        logger.warning("Could not calculate error rate: %s", e)
        return 0.0


def _update_system_status(db, key: str, value: str) -> None:
    """Update a system status value."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        # Try update first
        result = db.table("system_status").update({
            "value": value,
            "updated_at": now
        }).eq("key", key).execute()
        
        # If no rows updated, insert
        if not result.data:
            db.table("system_status").insert({
                "key": key,
                "value": value,
                "updated_at": now
            }).execute()
    except Exception as e:
        logger.warning("Could not update system status %s: %s", key, e)


def update_success_status(content_id: str) -> None:
    """Update system status after a successful publish."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    _update_system_status(db, "last_success_publish_at", now)
    _update_system_status(db, "last_error_code", None)
    _update_system_status(db, "last_error_action", None)
    
    # Update content status
    db.table("processed_content").update({
        "status": "published"
    }).eq("id", content_id).execute()
    
    logger.info("✅ Success status updated for %s", content_id)
