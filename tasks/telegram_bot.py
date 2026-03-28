"""
tasks/telegram_bot.py â€” Telegram bot for Content Factory SaaS.

Responsibilities
----------------
- /start <code>  Connect a user by their unique code stored in telegram_connections
- Publish notifications sent after each successful Facebook/IG post
- Approval-mode: send Approve/Reject inline buttons; auto-approve after 4h
- Daily summary: APScheduler job per connected user at their configured time
- /pause and /resume commands toggle automation for the user
- Facebook token expiry monitor: daily APScheduler job warns before 60-day expiry

The bot runs as a long-polling background thread alongside Flask and the
pipeline runner.  It shares the Supabase client via app.utils helpers.

Usage (called from dashboard_app.py / wsgi.py)
-----------------------------------------------
    from tasks.telegram_bot import start_telegram_bot
    start_telegram_bot()
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

# Ensure engine/ and project root are importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_ENGINE = os.path.join(_ROOT, "engine")
for _p in (_ROOT, _ENGINE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config

logger = logging.getLogger("telegram_bot")

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "ContentFactoryBot")

# â”€â”€ Supabase helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _get_sb():
    from app.utils import _get_supabase_client
    return _get_supabase_client()


# â”€â”€ Telegram connection helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_chat_id_for_user(user_id: str) -> Optional[str]:
    """Look up the Telegram chat_id for a user (returns None if not connected)."""
    try:
        sb = _get_sb()
        res = (
            sb.table("telegram_connections")
            .select("chat_id")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if res.data:
            return str(res.data[0]["chat_id"])
    except Exception as exc:
        logger.warning("get_chat_id_for_user failed (user=%s): %s", user_id[:8], exc)
    return None


def get_user_id_for_chat(chat_id: str) -> Optional[str]:
    """Reverse lookup: chat_id â†’ user_id."""
    try:
        sb = _get_sb()
        res = (
            sb.table("telegram_connections")
            .select("user_id")
            .eq("chat_id", str(chat_id))
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["user_id"]
    except Exception as exc:
        logger.warning("get_user_id_for_chat failed: %s", exc)
    return None


def _mark_connection_active(user_id: str, chat_id: str) -> None:
    """
    Upsert telegram_connections row for user_id â†” chat_id.

    After a successful bind, the unique_code is rotated to a new UUID so that
    the original deep-link / QR code becomes single-use and cannot be replayed.
    """
    try:
        import uuid as _uuid
        sb = _get_sb()
        now_iso = datetime.now(timezone.utc).isoformat()
        # Rotate unique_code on every successful activation to prevent replay
        new_code = str(_uuid.uuid4())
        sb.table("telegram_connections").upsert({
            "user_id": user_id,
            "chat_id": str(chat_id),
            "is_active": True,
            "connected_at": now_iso,
            "unique_code": new_code,  # invalidates old deep-link
        }, on_conflict="user_id").execute()
        logger.info("Telegram connected: user=%s chat=%s (code rotated)", user_id[:8], chat_id)
    except Exception as exc:
        logger.error("_mark_connection_active failed: %s", exc)


def _get_unique_code_for_user(user_id: str) -> Optional[str]:
    """Return existing unique_code for user_id, or None if not found."""
    try:
        sb = _get_sb()
        res = (
            sb.table("telegram_connections")
            .select("unique_code")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0].get("unique_code")
    except Exception as exc:
        logger.warning("_get_unique_code_for_user failed: %s", exc)
    return None


def get_or_create_unique_code(user_id: str) -> str:
    """
    Return an existing unique activation code for user_id, or create one.

    The code is a UUID stored in telegram_connections.unique_code.
    Used during onboarding to generate the /start <code> deep-link.
    """
    existing = _get_unique_code_for_user(user_id)
    if existing:
        return existing
    import uuid
    new_code = str(uuid.uuid4())
    try:
        sb = _get_sb()
        sb.table("telegram_connections").upsert({
            "user_id": user_id,
            "unique_code": new_code,
            "is_active": False,
        }, on_conflict="user_id").execute()
        return new_code
    except Exception as exc:
        logger.error("get_or_create_unique_code failed: %s", exc)
        return new_code


def is_telegram_connected(user_id: str) -> bool:
    """Return True if the user has an active Telegram connection."""
    try:
        sb = _get_sb()
        res = (
            sb.table("telegram_connections")
            .select("chat_id")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return bool(res.data and res.data[0].get("chat_id"))
    except Exception:
        return False


# â”€â”€ Automation pause/resume helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def is_automation_paused(user_id: str) -> bool:
    """Check if automation is paused for user_id via system_status."""
    try:
        sb = _get_sb()
        res = (
            sb.table("system_status")
            .select("value")
            .eq("key", f"automation_paused:{user_id}")
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0].get("value", "false").lower() == "true"
    except Exception as exc:
        logger.warning("is_automation_paused failed: %s", exc)
    return False


def set_automation_paused(user_id: str, paused: bool) -> None:
    """Set automation pause state for user_id in system_status."""
    try:
        sb = _get_sb()
        now_iso = datetime.now(timezone.utc).isoformat()
        sb.table("system_status").upsert({
            "key": f"automation_paused:{user_id}",
            "value": "true" if paused else "false",
            "updated_at": now_iso,
        }, on_conflict="key").execute()
    except Exception as exc:
        logger.error("set_automation_paused failed: %s", exc)


# â”€â”€ Async Telegram send helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_bot_app = None  # Will be set when bot starts


def _send_message_sync(chat_id: str, text: str, reply_markup=None) -> None:
    """
    Send a Telegram message synchronously from a non-async context.

    Runs the coroutine in a new event loop so it's safe to call from
    APScheduler jobs, publisher threads, etc.
    """
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        from telegram import Bot
        loop = asyncio.new_event_loop()
        kwargs = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        loop.run_until_complete(Bot(TELEGRAM_BOT_TOKEN).send_message(**kwargs))
        loop.close()
    except Exception as exc:
        logger.warning("_send_message_sync failed (chat=%s): %s", chat_id, exc)


# â”€â”€ Public notification API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def telegram_notify_published(
    user_id: str,
    platform: str,
    post_text: str,
    post_url: str = "",
) -> None:
    """
    Send a post-published notification to the user's Telegram chat.

    Called from publisher.py after a successful publish.  Fire-and-forget:
    runs in a background thread so it never blocks the publishing pipeline.

    Parameters
    ----------
    user_id  : str
    platform : str   e.g. "facebook", "instagram", "facebook, instagram"
    post_text: str   First ~200 chars of the published post text
    post_url : str   Optional public URL to the post
    """
    chat_id = get_chat_id_for_user(user_id)
    if not chat_id:
        return

    platform_ar = {
        "facebook": "ÙÙŠØ³Ø¨ÙˆÙƒ",
        "instagram": "Ø¥Ù†Ø³ØªØºØ±Ø§Ù…",
    }.get(platform.lower(), platform)

    snippet = post_text[:200].strip()
    if len(post_text) > 200:
        snippet += "â€¦"

    link_line = f'\nðŸ”— <a href="{post_url}">Ø¹Ø±Ø¶ Ø§Ù„Ù…Ù†Ø´ÙˆØ±</a>' if post_url else ""
    msg = (
        f"âœ… <b>ØªÙ… Ø§Ù„Ù†Ø´Ø± Ø¨Ù†Ø¬Ø§Ø­ Ø¹Ù„Ù‰ {platform_ar}</b>\n\n"
        f"<i>{snippet}</i>"
        f"{link_line}"
    )

    threading.Thread(
        target=_send_message_sync,
        args=(chat_id, msg),
        daemon=True,
        name=f"tg-notify-{user_id[:8]}",
    ).start()


def telegram_send_approval_request(
    user_id: str,
    content_id: str,
    post_text: str,
) -> bool:
    """
    Send an approval-mode request to the user with Approve/Reject buttons.

    The content is held at status='pending_approval' until the user responds
    or the 4-hour APScheduler auto-approve job fires.

    Returns True if the message was queued successfully.
    """
    if not TELEGRAM_BOT_TOKEN:
        return False
    chat_id = get_chat_id_for_user(user_id)
    if not chat_id:
        return False

    snippet = post_text[:300].strip()
    if len(post_text) > 300:
        snippet += "â€¦"

    msg = (
        f"ðŸ“‹ <b>Ù…Ø±Ø§Ø¬Ø¹Ø© Ù‚Ø¨Ù„ Ø§Ù„Ù†Ø´Ø±</b>\n\n"
        f"<i>{snippet}</i>\n\n"
        f"Ù‡Ù„ ØªÙˆØ§ÙÙ‚ Ø¹Ù„Ù‰ Ù†Ø´Ø± Ù‡Ø°Ø§ Ø§Ù„Ù…Ø­ØªÙˆÙ‰ØŸ"
    )

    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("âœ… Ù…ÙˆØ§ÙÙ‚", callback_data=f"approve:{content_id}"),
            InlineKeyboardButton("âŒ Ø±ÙØ¶", callback_data=f"reject:{content_id}"),
        ]])
        _send_message_sync(chat_id, msg, reply_markup=keyboard)
        return True
    except Exception as exc:
        logger.warning("telegram_send_approval_request failed: %s", exc)
        return False


def telegram_send_token_expiry_warning(
    user_id: str,
    days_remaining: int,
    reconnect_url: str = "",
) -> None:
    """Send a Facebook token expiry warning to the user."""
    chat_id = get_chat_id_for_user(user_id)
    if not chat_id:
        return

    if days_remaining <= 0:
        msg = (
            "ðŸ”´ <b>Ø§Ù†ØªÙ‡Øª ØµÙ„Ø§Ø­ÙŠØ© Ø§ØªØµØ§Ù„ ÙÙŠØ³Ø¨ÙˆÙƒ</b>\n\n"
            "ØªÙ… Ø¥ÙŠÙ‚Ø§Ù Ø§Ù„Ø£ØªÙ…ØªØ© ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹. ÙŠØ±Ø¬Ù‰ Ø¥Ø¹Ø§Ø¯Ø© Ø±Ø¨Ø· ØµÙØ­ØªÙƒ Ø¹Ù„Ù‰ ÙÙŠØ³Ø¨ÙˆÙƒ "
            "Ù„Ø§Ø³ØªØ¦Ù†Ø§Ù Ø§Ù„Ù†Ø´Ø± Ø§Ù„ØªÙ„Ù‚Ø§Ø¦ÙŠ."
        )
    else:
        msg = (
            f"âš ï¸ <b>ØªÙ†Ø¨ÙŠÙ‡: ØµÙ„Ø§Ø­ÙŠØ© ÙÙŠØ³Ø¨ÙˆÙƒ ØªÙ†ØªÙ‡ÙŠ Ø®Ù„Ø§Ù„ {days_remaining} Ø£ÙŠØ§Ù…</b>\n\n"
            "ÙŠØ±Ø¬Ù‰ Ø¥Ø¹Ø§Ø¯Ø© Ø±Ø¨Ø· ØµÙØ­ØªÙƒ Ø¹Ù„Ù‰ ÙÙŠØ³Ø¨ÙˆÙƒ Ù‚Ø¨Ù„ Ø§Ù†ØªÙ‡Ø§Ø¡ Ø§Ù„ØµÙ„Ø§Ø­ÙŠØ© "
            "Ù„ØªØ¬Ù†Ø¨ ØªÙˆÙ‚Ù Ø§Ù„Ù†Ø´Ø± Ø§Ù„ØªÙ„Ù‚Ø§Ø¦ÙŠ."
        )
    if reconnect_url:
        msg += f'\n\nðŸ”— <a href="{reconnect_url}">Ø¥Ø¹Ø§Ø¯Ø© Ø§Ù„Ø±Ø¨Ø· Ø§Ù„Ø¢Ù†</a>'

    _send_message_sync(chat_id, msg)


# â”€â”€ Daily summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _send_daily_summary_for_user(user_id: str) -> None:
    """Compose and send the daily summary message for one user."""
    chat_id = get_chat_id_for_user(user_id)
    if not chat_id:
        return
    try:
        sb = _get_sb()
        now_utc = datetime.now(timezone.utc)

        # Resolve user timezone from scheduled_posts.timezone (most recent active row)
        user_tz_str = "UTC"
        try:
            tz_res = (
                sb.table("scheduled_posts")
                .select("timezone")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if tz_res.data and tz_res.data[0].get("timezone"):
                user_tz_str = tz_res.data[0]["timezone"]
        except Exception:
            pass

        try:
            import zoneinfo
            user_tz = zoneinfo.ZoneInfo(user_tz_str)
            now_local = now_utc.astimezone(user_tz)
        except Exception:
            now_local = now_utc

        # Compute today boundaries in user's local timezone, converted to UTC for DB queries
        today_local_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_local_start = today_local_start + timedelta(days=1)
        yesterday_local_start = today_local_start - timedelta(days=1)

        # Convert to UTC ISO strings for Supabase queries
        today_utc_iso = today_local_start.astimezone(timezone.utc).isoformat()
        tomorrow_utc_iso = tomorrow_local_start.astimezone(timezone.utc).isoformat()
        yesterday_utc_iso = yesterday_local_start.astimezone(timezone.utc).isoformat()

        # Posts scheduled for today only (bounded range)
        sched_res = (
            sb.table("scheduled_posts")
            .select("id")
            .eq("user_id", user_id)
            .eq("status", "scheduled")
            .gte("scheduled_time", today_utc_iso)
            .lt("scheduled_time", tomorrow_utc_iso)
            .execute()
        )
        scheduled_today = len(sched_res.data or [])

        # Yesterday's best performer (by reach + engagement)
        pub_res = (
            sb.table("published_posts")
            .select("facebook_post_id,likes,shares,comments,reach,published_at")
            .eq("user_id", user_id)
            .gte("published_at", yesterday_utc_iso)
            .lt("published_at", today_utc_iso)
            .execute()
        )
        pub_rows = pub_res.data or []
        best = None
        best_score = -1
        for row in pub_rows:
            score = (row.get("reach") or 0) + (row.get("likes") or 0) + (
                (row.get("shares") or 0) * 3
            ) + (row.get("comments") or 0)
            if score > best_score:
                best_score = score
                best = row

        # Next scheduled post time (display in user's local timezone)
        next_res = (
            sb.table("scheduled_posts")
            .select("scheduled_time")
            .eq("user_id", user_id)
            .eq("status", "scheduled")
            .gte("scheduled_time", now_utc.isoformat())
            .order("scheduled_time")
            .limit(1)
            .execute()
        )
        next_post_time = ""
        if next_res.data:
            raw_time = next_res.data[0].get("scheduled_time", "")
            try:
                from datetime import datetime as _dt
                raw_dt = _dt.fromisoformat(raw_time.replace("Z", "+00:00"))
                local_dt = raw_dt.astimezone(user_tz if "user_tz" in dir() else timezone.utc)
                next_post_time = local_dt.strftime("%Y-%m-%d %H:%M") + f" ({user_tz_str})"
            except Exception:
                next_post_time = raw_time[:16].replace("T", " ") + " UTC"

        # Build message
        lines = ["ðŸ“Š <b>Ù…Ù„Ø®Øµ Ø§Ù„ÙŠÙˆÙ…</b>\n"]
        lines.append(f"ðŸ“… Ù…Ù†Ø´ÙˆØ±Ø§Øª Ø§Ù„ÙŠÙˆÙ… Ø§Ù„Ù…Ø¬Ø¯ÙˆÙ„Ø©: <b>{scheduled_today}</b>")

        if best:
            lines.append(
                f"\nðŸ† Ø£ÙØ¶Ù„ Ù…Ù†Ø´ÙˆØ± Ø£Ù…Ø³:\n"
                f"  ðŸ‘ {best.get('likes',0)}  |  ðŸ” {best.get('shares',0)}"
                f"  |  ðŸ’¬ {best.get('comments',0)}  |  ðŸ‘ {best.get('reach',0)}"
            )
        else:
            lines.append("\nðŸ“­ Ù„Ø§ ØªÙˆØ¬Ø¯ Ù…Ù†Ø´ÙˆØ±Ø§Øª Ù†ÙØ´Ø±Øª Ø£Ù…Ø³.")

        if next_post_time:
            lines.append(f"\nâ° Ø§Ù„Ù…Ù†Ø´ÙˆØ± Ø§Ù„Ù‚Ø§Ø¯Ù…: <b>{next_post_time}</b>")

        _send_message_sync(chat_id, "\n".join(lines))
    except Exception as exc:
        logger.warning("_send_daily_summary_for_user failed (user=%s): %s", user_id[:8], exc)


def run_daily_summaries() -> None:
    """
    Send daily summaries to connected users whose configured summary time matches now.

    Runs every 5 minutes (replacing the old 08:00 UTC hard-coded cron).
    Each connected user row joins `user_settings` to read `daily_summary_time`
    (default "08:00") which is treated as a UTC time-of-day.

    De-duplication: a `system_status` key `tg_summary_sent:<user_id>:<date>`
    prevents a second send if the job fires multiple times within the same
    5-minute window that straddles the target time.
    """
    try:
        sb = _get_sb()
        now_utc = datetime.now(timezone.utc)
        current_hhmm = now_utc.strftime("%H:%M")
        current_date = now_utc.strftime("%Y-%m-%d")

        # Load all active connections with their user's summary time
        res = (
            sb.table("telegram_connections")
            .select("user_id")
            .eq("is_active", True)
            .execute()
        )
        for row in res.data or []:
            uid = row.get("user_id")
            if not uid:
                continue
            try:
                # Read per-user summary time + timezone from settings/pages
                settings_res = (
                    sb.table("user_settings")
                    .select("daily_summary_time")
                    .eq("user_id", uid)
                    .limit(1)
                    .execute()
                )
                if settings_res.data:
                    stored_time = str(settings_res.data[0].get("daily_summary_time") or "").strip()
                else:
                    stored_time = ""
                if not stored_time:
                    continue
                summary_time = stored_time[:5]

                # Look up user timezone from scheduled_posts.timezone (most recent row)
                user_tz_str = "UTC"
                try:
                    tz_res = (
                        sb.table("scheduled_posts")
                        .select("timezone")
                        .eq("user_id", uid)
                        .order("created_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                    if tz_res.data and tz_res.data[0].get("timezone"):
                        user_tz_str = tz_res.data[0]["timezone"]
                except Exception:
                    pass

                # Convert now_utc to the user's local time for comparison
                try:
                    import zoneinfo
                    user_tz = zoneinfo.ZoneInfo(user_tz_str)
                    now_local = now_utc.astimezone(user_tz)
                except Exception:
                    now_local = now_utc  # Fall back to UTC

                # Parse the user's configured summary time (HH:MM in local tz)
                try:
                    target_h, target_m = (int(x) for x in summary_time.split(":")[:2])
                except Exception:
                    target_h, target_m = 8, 0

                target_minutes = target_h * 60 + target_m
                current_minutes = now_local.hour * 60 + now_local.minute

                # Use Â±5-minute window to tolerate scheduler jitter
                if abs(current_minutes - target_minutes) > 5:
                    continue

                # De-duplicate using local date so midnight resets the key
                local_date = now_local.strftime("%Y-%m-%d")
                dedup_key = f"tg_summary_sent:{uid}:{local_date}"
                dedup_res = (
                    sb.table("system_status")
                    .select("value")
                    .eq("key", dedup_key)
                    .limit(1)
                    .execute()
                )
                if dedup_res.data:
                    continue  # Already sent today

                # Mark sent (use today's UTC date as dedup key)
                sb.table("system_status").upsert({
                    "key": dedup_key,
                    "value": now_utc.isoformat(),
                    "updated_at": now_utc.isoformat(),
                }).execute()

                _send_daily_summary_for_user(uid)

            except Exception as exc:
                logger.warning("Daily summary failed (user=%s): %s", uid[:8], exc)
    except Exception as exc:
        logger.error("run_daily_summaries failed: %s", exc)


# â”€â”€ Facebook token expiry monitor â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def run_token_expiry_check() -> None:
    """
    Daily check for Facebook token expiry across all active users.

    - Token within 7 days of expiry â†’ send Telegram warning (once per day)
    - Token already expired â†’ pause automation + send alert
    """
    try:
        sb = _get_sb()
        # Load all active managed_pages rows that have token_expires_at
        pages = (
            sb.table("managed_pages")
            .select("user_id, page_id, token_expires_at")
            .eq("status", "active")
            .not_.is_("token_expires_at", "null")
            .execute()
        )
        now = datetime.now(timezone.utc)
        seen_users: set = set()

        for row in pages.data or []:
            uid = row.get("user_id")
            if not uid or uid in seen_users:
                continue
            seen_users.add(uid)

            expires_at_raw = row.get("token_expires_at", "")
            try:
                expires_at = datetime.fromisoformat(
                    expires_at_raw.replace("Z", "+00:00")
                )
            except Exception:
                continue

            delta = expires_at - now
            # Use total_seconds() to avoid floor-to-days truncation; a token
            # with 23h left would give .days == 0 which is misleading.
            seconds_remaining = delta.total_seconds()
            days_remaining = int(seconds_remaining // 86400)  # for alert message only

            if seconds_remaining <= 0:
                # Truly expired â€” pause automation and alert
                set_automation_paused(uid, True)
                _check_and_send_expiry_alert(sb, uid, 0)

            elif seconds_remaining <= 7 * 86400:
                # Less than 7 days remaining â€” warn once per day
                _check_and_send_expiry_alert(sb, uid, max(1, days_remaining))

    except Exception as exc:
        logger.error("run_token_expiry_check failed: %s", exc)


def _check_and_send_expiry_alert(sb, user_id: str, days_remaining: int) -> None:
    """Send expiry alert only if not already sent today (de-duplicated via system_status)."""
    dedup_key = f"tg_expiry_alert:{user_id}:{datetime.now(timezone.utc).date()}"
    try:
        existing = (
            sb.table("system_status")
            .select("key")
            .eq("key", dedup_key)
            .limit(1)
            .execute()
        )
        if existing.data:
            return  # Already sent today
        # Mark as sent
        sb.table("system_status").upsert(
            {"key": dedup_key, "value": "sent", "updated_at": datetime.now(timezone.utc).isoformat()},
            on_conflict="key",
        ).execute()
    except Exception:
        pass

    # Deep-link directly to the Facebook/Pages step of onboarding (step 1)
    # so the user lands on the reconnect page rather than the generic start.
    base_url = os.getenv("APP_BASE_URL", "").rstrip("/")
    reconnect_url = f"{base_url}/onboarding/?step=1" if base_url else ""
    telegram_send_token_expiry_warning(user_id, days_remaining, reconnect_url)


# â”€â”€ Bot handlers (python-telegram-bot v20 async) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _cmd_start(update, context):
    """Handle /start <code> â€” connect user to their Telegram chat."""
    args = context.args or []
    chat_id = str(update.effective_chat.id)

    if not args:
        await update.message.reply_text(
            "Ù…Ø±Ø­Ø¨Ø§Ù‹! ðŸ‘‹\n"
            "Ø£Ø±Ø³Ù„ /start <ÙƒÙˆØ¯_Ø§Ù„ØªÙØ¹ÙŠÙ„> Ù„Ù„Ø±Ø¨Ø· Ø¨Ø­Ø³Ø§Ø¨Ùƒ.\n"
            "Ø³ØªØ¬Ø¯ Ø§Ù„ÙƒÙˆØ¯ ÙÙŠ Ø®Ø·ÙˆØ© ØªÙŠÙ„ÙŠØºØ±Ø§Ù… Ø£Ø«Ù†Ø§Ø¡ Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯."
        )
        return

    code = args[0].strip()
    try:
        sb = _get_sb()
        res = (
            sb.table("telegram_connections")
            .select("user_id, is_active")
            .eq("unique_code", code)
            .limit(1)
            .execute()
        )
        if not res.data:
            await update.message.reply_text(
                "âŒ Ø§Ù„ÙƒÙˆØ¯ ØºÙŠØ± ØµØ­ÙŠØ­. ØªØ£ÙƒØ¯ Ù…Ù† Ù†Ø³Ø® Ø§Ù„ÙƒÙˆØ¯ Ø§Ù„ØµØ­ÙŠØ­ Ù…Ù† ØµÙØ­Ø© Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯."
            )
            return

        user_id = res.data[0]["user_id"]
        _mark_connection_active(user_id, chat_id)

        await update.message.reply_text(
            "âœ… <b>ØªÙ… Ø§Ù„Ø±Ø¨Ø· Ø¨Ù†Ø¬Ø§Ø­!</b>\n\n"
            "Ø³ØªØµÙ„Ùƒ Ø¥Ø´Ø¹Ø§Ø±Ø§Øª ÙÙˆØ±ÙŠØ© Ø¨ÙƒÙ„ Ù…Ù†Ø´ÙˆØ± Ù…Ù† Ø§Ù„Ø¢Ù†.\n\n"
            "Ø§Ù„Ø£ÙˆØ§Ù…Ø± Ø§Ù„Ù…ØªØ§Ø­Ø©:\n"
            "  /pause â€” Ø¥ÙŠÙ‚Ø§Ù Ø§Ù„Ø£ØªÙ…ØªØ© Ù…Ø¤Ù‚ØªØ§Ù‹\n"
            "  /resume â€” Ø§Ø³ØªØ¦Ù†Ø§Ù Ø§Ù„Ø£ØªÙ…ØªØ©\n"
            "  /status â€” Ø­Ø§Ù„Ø© Ø§Ù„Ù†Ø¸Ø§Ù…",
            parse_mode="HTML",
        )
        logger.info("Telegram connected: user=%s chat=%s", user_id[:8], chat_id)
    except Exception as exc:
        logger.error("_cmd_start error: %s", exc)
        await update.message.reply_text("Ø­Ø¯Ø« Ø®Ø·Ø£. ÙŠØ±Ø¬Ù‰ Ø§Ù„Ù…Ø­Ø§ÙˆÙ„Ø© Ù„Ø§Ø­Ù‚Ø§Ù‹.")


async def _cmd_pause(update, context):
    """Handle /pause â€” pause automation for this user."""
    chat_id = str(update.effective_chat.id)
    user_id = get_user_id_for_chat(chat_id)
    if not user_id:
        await update.message.reply_text("ÙŠØ¬Ø¨ Ø±Ø¨Ø· Ø­Ø³Ø§Ø¨Ùƒ Ø£ÙˆÙ„Ø§Ù‹. Ø£Ø±Ø³Ù„ /start <ÙƒÙˆØ¯_Ø§Ù„ØªÙØ¹ÙŠÙ„>")
        return
    set_automation_paused(user_id, True)
    await update.message.reply_text(
        "â¸ï¸ <b>ØªÙ… Ø¥ÙŠÙ‚Ø§Ù Ø§Ù„Ø£ØªÙ…ØªØ©</b>\n\nÙ„Ù† ØªÙÙ†Ø´Ø± Ø£ÙŠ Ù…Ù†Ø´ÙˆØ±Ø§Øª Ø­ØªÙ‰ ØªØ±Ø³Ù„ /resume",
        parse_mode="HTML",
    )


async def _cmd_resume(update, context):
    """Handle /resume â€” resume automation for this user."""
    chat_id = str(update.effective_chat.id)
    user_id = get_user_id_for_chat(chat_id)
    if not user_id:
        await update.message.reply_text("ÙŠØ¬Ø¨ Ø±Ø¨Ø· Ø­Ø³Ø§Ø¨Ùƒ Ø£ÙˆÙ„Ø§Ù‹. Ø£Ø±Ø³Ù„ /start <ÙƒÙˆØ¯_Ø§Ù„ØªÙØ¹ÙŠÙ„>")
        return
    set_automation_paused(user_id, False)
    await update.message.reply_text(
        "â–¶ï¸ <b>ØªÙ… Ø§Ø³ØªØ¦Ù†Ø§Ù Ø§Ù„Ø£ØªÙ…ØªØ©</b>\n\nØ³ÙŠØ³ØªØ£Ù†Ù Ø§Ù„Ù†Ø´Ø± Ø§Ù„ØªÙ„Ù‚Ø§Ø¦ÙŠ ÙÙŠ Ø§Ù„Ø¯ÙˆØ±Ø© Ø§Ù„Ù‚Ø§Ø¯Ù…Ø©.",
        parse_mode="HTML",
    )


async def _cmd_status(update, context):
    """Handle /status â€” show automation status for this user."""
    chat_id = str(update.effective_chat.id)
    user_id = get_user_id_for_chat(chat_id)
    if not user_id:
        await update.message.reply_text("ÙŠØ¬Ø¨ Ø±Ø¨Ø· Ø­Ø³Ø§Ø¨Ùƒ Ø£ÙˆÙ„Ø§Ù‹. Ø£Ø±Ø³Ù„ /start <ÙƒÙˆØ¯_Ø§Ù„ØªÙØ¹ÙŠÙ„>")
        return
    paused = is_automation_paused(user_id)
    status_str = "â¸ï¸ Ù…ÙˆÙ‚ÙˆÙØ©" if paused else "â–¶ï¸ ØªØ¹Ù…Ù„"
    await update.message.reply_text(
        f"ðŸ“¡ <b>Ø­Ø§Ù„Ø© Ø§Ù„Ø£ØªÙ…ØªØ©:</b> {status_str}",
        parse_mode="HTML",
    )


async def _callback_query_handler(update, context):
    """Handle Approve/Reject inline button callbacks for approval mode."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    chat_id = str(query.message.chat.id)
    user_id = get_user_id_for_chat(chat_id)
    if not user_id:
        return

    if data.startswith("approve:"):
        content_id = data[8:]
        _approve_content(user_id, content_id)
        await query.edit_message_text(f"âœ… ØªÙ…Øª Ø§Ù„Ù…ÙˆØ§ÙÙ‚Ø© Ø¹Ù„Ù‰ Ø§Ù„Ù†Ø´Ø± â€” Ø³ÙŠÙÙ†Ø´Ø± Ù‚Ø±ÙŠØ¨Ø§Ù‹.")
    elif data.startswith("reject:"):
        content_id = data[7:]
        _reject_content(user_id, content_id)
        await query.edit_message_text(f"âŒ ØªÙ… Ø±ÙØ¶ Ø§Ù„Ù…Ù†Ø´ÙˆØ± ÙˆØ­Ø°ÙÙ‡ Ù…Ù† Ø§Ù„Ù‚Ø§Ø¦Ù…Ø©.")


def _update_scheduled_post_for_content(sb, content_id: str, user_id: str, new_status: str) -> None:
    """
    Update the matching scheduled_posts row for a content_id to new_status.

    This must be called alongside any processed_content status change so that
    fetch_due_posts() (which reads scheduled_posts.status == 'scheduled') can
    pick up newly-approved content.
    """
    try:
        (
            sb.table("scheduled_posts")
            .update({"status": new_status})
            .eq("content_id", content_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.warning("_update_scheduled_post_for_content failed: %s", exc)


def _approve_content(user_id: str, content_id: str) -> None:
    """
    Transition content from pending_approval â†’ approved (processed_content)
    and scheduled_posts â†’ scheduled so the publisher picks it up.

    'approved' status tells the publisher to bypass the approval gate on the
    next pipeline cycle â€” preventing infinite re-gating.
    """
    try:
        sb = _get_sb()
        (
            sb.table("processed_content")
            .update({"status": "approved"})
            .eq("id", content_id)
            .eq("user_id", user_id)
            .eq("status", "pending_approval")
            .execute()
        )
        _update_scheduled_post_for_content(sb, content_id, user_id, "scheduled")
        logger.info("Content approved: %s (user=%s)", content_id[:8], user_id[:8])
    except Exception as exc:
        logger.error("_approve_content failed: %s", exc)


def _reject_content(user_id: str, content_id: str) -> None:
    """Transition content from pending_approval â†’ rejected (both tables)."""
    try:
        sb = _get_sb()
        (
            sb.table("processed_content")
            .update({"status": "rejected", "rejected_reason": "Ø±ÙÙØ¶ Ø¹Ø¨Ø± ØªÙŠÙ„ÙŠØºØ±Ø§Ù…"})
            .eq("id", content_id)
            .eq("user_id", user_id)
            .eq("status", "pending_approval")
            .execute()
        )
        _update_scheduled_post_for_content(sb, content_id, user_id, "rejected")
        logger.info("Content rejected: %s (user=%s)", content_id[:8], user_id[:8])
    except Exception as exc:
        logger.error("_reject_content failed: %s", exc)


def auto_approve_expired_requests() -> None:
    """
    APScheduler job: auto-approve pending_approval content older than 4 hours.

    Content stuck at pending_approval for more than 4h is transitioned to
    'scheduled' so it enters the normal publish queue.
    Both processed_content and scheduled_posts rows are updated so the
    publisher can proceed.
    """
    try:
        sb = _get_sb()
        now_utc = datetime.now(timezone.utc)
        cutoff = (now_utc - timedelta(hours=4)).isoformat()
        # Primary filter: rows where approval_requested_at was set (new flow)
        # and the 4-hour window has elapsed.
        # Fallback: rows where approval_requested_at is NULL but created_at
        # is older than 4h (covers pre-migration rows, rare case).
        res_new = (
            sb.table("processed_content")
            .select("id, user_id, generated_text, approval_requested_at")
            .eq("status", "pending_approval")
            .not_.is_("approval_requested_at", "null")
            .lte("approval_requested_at", cutoff)
            .execute()
        )
        res_legacy = (
            sb.table("processed_content")
            .select("id, user_id, generated_text, approval_requested_at")
            .eq("status", "pending_approval")
            .is_("approval_requested_at", "null")
            .lte("created_at", cutoff)
            .execute()
        )
        combined_rows = (res_new.data or []) + (res_legacy.data or [])
        for row in combined_rows:
            try:
                cid = row["id"]
                uid = row.get("user_id") or ""
                # Set processed_content to "approved" so the publisher skips
                # the approval gate and publishes directly on next pipeline run.
                (
                    sb.table("processed_content")
                    .update({"status": "approved"})
                    .eq("id", cid)
                    .eq("status", "pending_approval")
                    .execute()
                )
                if uid:
                    _update_scheduled_post_for_content(sb, cid, uid, "scheduled")
                logger.info(
                    "Auto-approved content %s for user=%s (4h timeout)",
                    cid[:8],
                    uid[:8] if uid else "?",
                )
                if uid:
                    chat_id = get_chat_id_for_user(uid)
                    if chat_id:
                        _send_message_sync(
                            chat_id,
                            "â° ØªÙ…Øª Ø§Ù„Ù…ÙˆØ§ÙÙ‚Ø© Ø§Ù„ØªÙ„Ù‚Ø§Ø¦ÙŠØ© Ø¹Ù„Ù‰ Ù…Ù†Ø´ÙˆØ± Ù„Ù… ÙŠÙØ±Ø§Ø¬ÙŽØ¹ Ø®Ù„Ø§Ù„ 4 Ø³Ø§Ø¹Ø§Øª."
                        )
            except Exception as inner_exc:
                logger.warning("auto_approve inner error: %s", inner_exc)
    except Exception as exc:
        logger.error("auto_approve_expired_requests failed: %s", exc)


# â”€â”€ Bot startup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_bot_started: bool = False
_bot_thread: Optional[threading.Thread] = None


def _run_bot_polling() -> None:
    """Run the bot's long-polling loop in a dedicated event loop."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set â€” Telegram bot disabled")
        return

    try:
        from telegram.ext import (
            Application,
            CallbackQueryHandler,
            CommandHandler,
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        app = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
        )
        app.add_handler(CommandHandler("start", _cmd_start))
        app.add_handler(CommandHandler("pause", _cmd_pause))
        app.add_handler(CommandHandler("resume", _cmd_resume))
        app.add_handler(CommandHandler("status", _cmd_status))
        app.add_handler(CallbackQueryHandler(_callback_query_handler))

        logger.info("Telegram bot polling started (@%s)", BOT_USERNAME)
        app.run_polling(drop_pending_updates=True, stop_signals=None)
    except Exception as exc:
        logger.error("Telegram bot polling error: %s", exc, exc_info=True)


_BOT_LEADER_KEY = "telegram_bot_leader"
_BOT_LEADER_TTL_SECONDS = 30  # Heartbeat interval; leader renews every 20s


def _acquire_bot_leader_lock() -> bool:
    """
    Try to atomically claim the Telegram bot leader lock in system_status.

    Strategy (fail-closed on uncertainty):
    1. DELETE expired rows where updated_at is older than TTL â€” this makes
       room for a new leader while being idempotent if the row doesn't exist.
    2. Attempt INSERT with ON CONFLICT DO NOTHING (via upsert-like logic).
       Supabase upsert always succeeds, so we simulate atomic-ness by:
       a. Delete the row only if it is expired (conditional delete via filter).
       b. Attempt to insert. If we don't have the row after insert, another
          process won â€” fail closed.
    3. Read back the row to verify we own it (our process_id written as value).

    Returns the process_id string if this process won the lock, or None if
    another live process already holds it.
    Fails closed (returns None) on DB errors to prevent split-brain.
    """
    import uuid as _uuid
    process_id = str(_uuid.uuid4())
    try:
        sb = _get_sb()
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(seconds=_BOT_LEADER_TTL_SECONDS)).isoformat()

        # Step 1: Remove expired lock (conditional on staleness)
        # This is safe to do concurrently â€” only the row older than TTL is deleted.
        sb.table("system_status").delete().eq("key", _BOT_LEADER_KEY).lt("updated_at", cutoff).execute()

        # Step 2: Try to insert our process_id as the leader.
        # Supabase upsert doesn't give us conflict info, so we use insert with
        # ignore_duplicates=True (via on_conflict). If the row already exists
        # (another process just inserted), our insert silently fails.
        try:
            sb.table("system_status").insert({
                "key": _BOT_LEADER_KEY,
                "value": process_id,
                "updated_at": now.isoformat(),
            }).execute()
        except Exception:
            pass  # Row already exists â€” another process may have inserted first

        # Step 3: Read back and verify we own the row
        res = (
            sb.table("system_status")
            .select("value, updated_at")
            .eq("key", _BOT_LEADER_KEY)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None  # Can't verify â€” fail closed
        row = res.data[0]
        if row.get("value") == process_id:
            return process_id  # We won the lock
        # Another process owns the lock â€” check if it's stale
        try:
            updated_at = datetime.fromisoformat(
                (row.get("updated_at") or "").replace("Z", "+00:00")
            )
            if (now - updated_at).total_seconds() < _BOT_LEADER_TTL_SECONDS:
                return None  # Live leader â€” defer to them
        except Exception:
            pass
        return None  # Fail closed on uncertainty
    except Exception as exc:
        logger.warning("Bot leader-lock check failed: %s â€” deferring (fail-closed)", exc)
        return None  # Fail closed: don't risk two pollers


def _bot_leader_heartbeat(stop_event: threading.Event, process_id: str) -> None:
    """Renew the leader lock every 20 seconds while the bot is running.

    Writes the same process_id as the lock value and updates updated_at
    so the TTL check knows the lock is still alive.
    """
    while not stop_event.is_set():
        try:
            sb = _get_sb()
            now_iso = datetime.now(timezone.utc).isoformat()
            sb.table("system_status").update({
                "value": process_id,
                "updated_at": now_iso,
            }).eq("key", _BOT_LEADER_KEY).eq("value", process_id).execute()
        except Exception as exc:
            logger.debug("Heartbeat renewal failed: %s", exc)
        stop_event.wait(20)


def start_telegram_bot() -> None:
    """
    Start the Telegram bot long-polling loop as a daemon thread.

    Uses a distributed leader-election lock (system_status table) to ensure
    only ONE process runs the Telegram long-poll across multiple gunicorn workers.

    Also registers APScheduler jobs for:
    - Daily summary (per-user configured time, every 5min check)
    - Auto-approve expired approval requests (every 15 minutes)
    - Facebook token expiry check (daily at 7:00 UTC)

    Safe to call multiple times â€” idempotent (in-process + distributed).
    """
    global _bot_started, _bot_thread

    if _bot_started:
        logger.debug("Telegram bot already started â€” skipping")
        return

    # â”€â”€ Register background jobs that do NOT require the bot token â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # These run regardless of whether TELEGRAM_BOT_TOKEN is configured so that
    # auto-approve and token-expiry checks keep working even without a bot.
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger

        try:
            from tasks.runner import _scheduler_instance
            sched = _scheduler_instance
        except (ImportError, AttributeError):
            sched = None

        if sched is None or not sched.running:
            sched = BackgroundScheduler(daemon=True, timezone="UTC")
            sched.start()

        # Auto-approve stale approval requests â€” does not need bot token
        sched.add_job(
            auto_approve_expired_requests,
            IntervalTrigger(minutes=15),
            id="tg_auto_approve",
            replace_existing=True,
        )
        # Token-expiry check â€” sends Telegram alert only if bot token is set
        sched.add_job(
            run_token_expiry_check,
            CronTrigger(hour=7, minute=0, timezone="UTC"),
            id="tg_token_expiry",
            replace_existing=True,
        )
        logger.info("Telegram background jobs registered (auto-approve + token-expiry)")
    except Exception as exc:
        logger.warning("Could not register Telegram background jobs: %s", exc)

    # â”€â”€ Bot-token dependent features â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if not TELEGRAM_BOT_TOKEN:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not set â€” Telegram bot polling, notifications, "
            "and daily summaries disabled (background jobs still running)"
        )
        return

    # Distributed singleton: only one gunicorn worker should run the bot.
    leader_process_id = _acquire_bot_leader_lock()
    if not leader_process_id:
        logger.info("Telegram bot leader lock held by another process â€” this worker will skip polling")
        return

    _bot_thread = threading.Thread(
        target=_run_bot_polling,
        daemon=True,
        name="telegram-bot-polling",
    )
    _bot_thread.start()
    _bot_started = True
    logger.info("Telegram bot thread started (leader, process=%s)", leader_process_id[:8])

    # Start heartbeat thread to renew leader lock with our process_id
    _hb_stop = threading.Event()
    _hb_thread = threading.Thread(
        target=_bot_leader_heartbeat,
        args=(_hb_stop, leader_process_id),
        daemon=True,
        name="telegram-bot-heartbeat",
    )
    _hb_thread.start()

    # Register polling-dependent APScheduler jobs
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        try:
            from tasks.runner import _scheduler_instance
            sched = _scheduler_instance
        except (ImportError, AttributeError):
            sched = None

        if sched is None or not sched.running:
            sched = BackgroundScheduler(daemon=True, timezone="UTC")
            sched.start()

        # Daily summary requires bot token to send messages
        sched.add_job(
            run_daily_summaries,
            IntervalTrigger(minutes=5),
            id="tg_daily_summary",
            replace_existing=True,
        )

        # Watchdog: restart polling thread if leader dies
        def _bot_polling_watchdog() -> None:
            global _bot_thread, _bot_started
            if not _bot_started:
                return
            if _bot_thread is not None and _bot_thread.is_alive():
                return
            logger.warning("Telegram bot polling thread is dead â€” attempting restart")
            try:
                new_thread = threading.Thread(
                    target=_run_bot_polling,
                    daemon=True,
                    name="telegram-bot-polling",
                )
                new_thread.start()
                _bot_thread = new_thread
                logger.info("Telegram bot polling thread restarted by watchdog")
            except Exception as wd_exc:
                logger.error("Watchdog failed to restart bot thread: %s", wd_exc)

        sched.add_job(
            _bot_polling_watchdog,
            IntervalTrigger(minutes=2),
            id="tg_bot_watchdog",
            replace_existing=True,
        )
        logger.info("Telegram polling-dependent jobs registered (daily-summary + watchdog)")
    except Exception as exc:
        logger.warning("Could not register Telegram polling jobs: %s", exc)
