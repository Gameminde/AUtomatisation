"""Generate and store a posting schedule."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import config
from randomization import get_randomizer

logger = config.get_logger("scheduler")


PEAK_HOURS = {
    "US_EST": [7, 12, 18, 20],
    "US_PST": [9, 14, 20, 22],
    "UK_GMT": [8, 13, 17, 21],
}

# Simplified: Photo posts only (no Reels for v2.0 Gumroad)
CONTENT_MIX = {
    "text": 1.0,  # 100% photo posts with text
}


def get_adaptive_interval(base_min: int = 2, base_max: int = 4) -> Tuple[int, int]:
    """
    v2.1: Get adaptive posting interval based on error rate.
    
    - If error_rate > 0.2 (20% failures) -> widen to 4-6h
    - If error_rate > 0.4 (40% failures) -> widen to 6-8h
    - Otherwise -> use base interval
    """
    try:
        # Import here to avoid circular imports
        import error_handler
        error_rate = error_handler.get_recent_error_rate(hours=24)
        
        if error_rate > 0.4:
            logger.warning("🚨 High error rate (%.1f%%) - using 6-8h intervals", error_rate * 100)
            return (6, 8)
        elif error_rate > 0.2:
            logger.warning("⚠️ Elevated error rate (%.1f%%) - using 4-6h intervals", error_rate * 100)
            return (4, 6)
    except Exception as e:
        logger.debug("Could not get error rate: %s", e)
    
    return (base_min, base_max)


def build_slots_for_day(day: date) -> List[Dict]:
    randomizer = get_randomizer()
    slots: List[Dict] = []
    for tz_key, hours in PEAK_HOURS.items():
        tz_name = config.TARGET_TIMEZONES[tz_key]
        tz = ZoneInfo(tz_name)
        for hour in hours:
            local_dt = datetime(day.year, day.month, day.day, hour, 0, tzinfo=tz)
            # Add random minute jitter (5-25 min) to avoid posting at exact hours
            jitter = randomizer.add_minute_jitter(local_dt)
            local_dt = local_dt + jitter
            utc_dt = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
            slots.append(
                {
                    "scheduled_time": utc_dt.isoformat(),
                    "timezone": tz_name,
                }
            )
    slots.sort(key=lambda item: item["scheduled_time"])
    # v2.1: Use adaptive intervals based on error rate
    min_h, max_h = get_adaptive_interval()
    return enforce_min_gap_random(slots, min_hours=min_h, max_hours=max_h)


def enforce_min_gap(slots: List[Dict], min_hours: int) -> List[Dict]:
    if not slots:
        return slots
    filtered = [slots[0]]
    last_time = datetime.fromisoformat(slots[0]["scheduled_time"])
    for slot in slots[1:]:
        current = datetime.fromisoformat(slot["scheduled_time"])
        if (current - last_time).total_seconds() >= min_hours * 3600:
            filtered.append(slot)
            last_time = current
    return filtered


def enforce_min_gap_random(slots: List[Dict], min_hours: int, max_hours: int) -> List[Dict]:
    """Enforce random gaps between posts (human-like)."""
    if not slots:
        return slots
    randomizer = get_randomizer()
    filtered = [slots[0]]
    last_time = datetime.fromisoformat(slots[0]["scheduled_time"])
    for slot in slots[1:]:
        current = datetime.fromisoformat(slot["scheduled_time"])
        # Random interval for this gap
        random_interval = randomizer.randomize_interval(min_hours, max_hours)
        required_gap = random_interval.total_seconds()
        if (current - last_time).total_seconds() >= required_gap:
            filtered.append(slot)
            last_time = current
    return filtered


def process_retries() -> int:
    """
    v2.1.1: Maintenance task to move due retries back to 'scheduled'.
    
    Checks for:
    - status = 'retry_scheduled'
    - next_retry_at <= NOW
    - fb_post_id IS NULL (safety)
    """
    client = config.get_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        # Find due retries
        # v2.1.1 fix: PostgREST null check syntax
        result = (
            client.table("processed_content")
            .select("id, status")
            .eq("status", "retry_scheduled")
            .lte("next_retry_at", now)
            .execute()
        )
        
        # Filter out items that already have fb_post_id (double-safety in Python)
        items = [item for item in (result.data or []) if not item.get("fb_post_id")]
        count = 0
        
        for item in items:
            # Move back to scheduled
            client.table("processed_content").update({
                "status": "scheduled",
                "last_error": None  # Clear error for fresh attempt
                # Note: retry_count is preserved
            }).eq("id", item["id"]).execute()
            
            # Also update schedule table if needed (though publisher drives from content status now?)
            # Actually publisher looks at scheduled_posts JOIN processed_content (implicitly via logic)
            # But let's make sure the schedule entry is also 'scheduled'
            client.table("scheduled_posts").update({
                "status": "scheduled"
            }).eq("content_id", item["id"]).execute()
            
            count += 1
            
        if count > 0:
            logger.info("♻️ Processed %d retries -> scheduled", count)
        
        return count
        
    except Exception as e:
        logger.error(f"Error processing retries: {e}")
        return 0


def fetch_content_pool(limit: int = 100):
    client = config.get_supabase_client()
    response = client.table("processed_content").select("id,post_type").limit(limit).execute()
    return response.data or []


def schedule_posts(days: int = 7, max_per_day: int = 5) -> int:
    """
    Schedule posts for the next N days.
    
    Args:
        days: Number of days to schedule
        max_per_day: Maximum posts per day (configurable 1-5 for Gumroad users)
    
    Returns:
        Number of posts scheduled
    """
    content_items = fetch_content_pool()
    if not content_items:
        logger.warning("No content found in processed_content")
        return 0

    # Simplified: All posts are text/photo (no Reels)
    text_items = [item for item in content_items if item["post_type"] == "text"]

    client = config.get_supabase_client()
    scheduled = 0
    start_day = date.today()

    for offset in range(days):
        day = start_day + timedelta(days=offset)
        slots = build_slots_for_day(day)
        
        # Limit slots to max_per_day
        slots = slots[:max_per_day]

        for slot in slots:
            if not text_items:
                logger.warning("Not enough content to fill schedule")
                break

            content = text_items.pop(0)

            payload = {
                "content_id": content["id"],
                "scheduled_time": slot["scheduled_time"],
                "timezone": slot["timezone"],
                "priority": 5,
                "status": "scheduled",
            }
            client.table("scheduled_posts").insert(payload).execute()
            scheduled += 1

    logger.info("Scheduled %s posts over %s days (max %s/day)", scheduled, days, max_per_day)
    return scheduled


if __name__ == "__main__":
    schedule_posts()
