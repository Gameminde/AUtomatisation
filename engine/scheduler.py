"""Generate and store a posting schedule."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import config
from randomization import get_randomizer

logger = config.get_logger("scheduler")


DEFAULT_COUNTRY_CODE = (
    config.DEFAULT_COUNTRY_CODE
    if config.DEFAULT_COUNTRY_CODE in config.TARGET_POSTING_PRESETS
    else next(iter(config.TARGET_POSTING_PRESETS))
)

PEAK_HOURS = {
    country_code: preset["peak_hours"]
    for country_code, preset in config.TARGET_POSTING_PRESETS.items()
}
DEFAULT_POSTING_WINDOWS = {
    country_code: preset["posting_times"]
    for country_code, preset in config.TARGET_POSTING_PRESETS.items()
}

CONTENT_MIX = {
    "post": 0.7,
    "carousel": 0.3,
}
AUTO_SCHEDULE_TYPES = {"post", "carousel", "text"}


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
            logger.warning(
                "High error rate (%.1f%%) - using 6-8h intervals",
                error_rate * 100,
            )
            return (6, 8)
        if error_rate > 0.2:
            logger.warning(
                "Elevated error rate (%.1f%%) - using 4-6h intervals",
                error_rate * 100,
            )
            return (4, 6)
    except Exception as e:
        logger.debug("Could not get error rate: %s", e)

    return (base_min, base_max)


def get_schedule_preset(
    country_code: Optional[str] = None,
    timezone_name: Optional[str] = None,
) -> Dict:
    normalized_country = (country_code or DEFAULT_COUNTRY_CODE).strip().upper()
    preset = config.TARGET_POSTING_PRESETS.get(
        normalized_country,
        config.TARGET_POSTING_PRESETS[DEFAULT_COUNTRY_CODE],
    )
    return {
        "country_code": preset["country_code"],
        "timezone": timezone_name or preset["timezone"],
        "posting_times": preset["posting_times"],
        "peak_hours": list(preset["peak_hours"]),
    }


def _build_slots_from_times(
    day: date,
    posting_times: str,
    timezone_name: str = "UTC",
) -> List[Dict]:
    """
    Build UTC posting slots from a user-supplied comma-separated HH:MM string.

    Each time token is interpreted in the provided local timezone, then
    converted to UTC for storage. A random 0-10 min jitter is applied to avoid
    exact-hour posting.

    Args:
        day:           Target date.
        posting_times: e.g. "12:00,19:00,21:00"
        timezone_name: IANA timezone name for the local interpretation.
    """
    import random

    slots: List[Dict] = []
    tokens = [t.strip() for t in posting_times.split(",") if t.strip()]
    try:
        local_tz = ZoneInfo(timezone_name)
    except Exception:
        local_tz = ZoneInfo("UTC")
        timezone_name = "UTC"

    for token in tokens:
        try:
            parts = token.split(":")
            hour, minute = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            continue
        jitter_min = random.randint(0, 10)
        total_minute = minute + jitter_min
        extra_hours, clamped_minute = divmod(total_minute, 60)
        clamped_hour = (hour + extra_hours) % 24
        local_dt = datetime(
            day.year,
            day.month,
            day.day,
            clamped_hour,
            clamped_minute,
            tzinfo=local_tz,
        )
        if hour + extra_hours >= 24:
            local_dt = local_dt + timedelta(days=1)
        utc_dt = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
        slots.append(
            {
                "scheduled_time": utc_dt.isoformat(),
                "timezone": timezone_name,
            }
        )
    slots.sort(key=lambda s: s["scheduled_time"])
    return slots


def build_slots_for_day(
    day: date,
    country_code: Optional[str] = None,
    timezone_name: Optional[str] = None,
) -> List[Dict]:
    schedule_preset = get_schedule_preset(
        country_code=country_code,
        timezone_name=timezone_name,
    )
    randomizer = get_randomizer()
    slots: List[Dict] = []
    tz_name = schedule_preset["timezone"]
    tz = ZoneInfo(tz_name)
    for hour in schedule_preset["peak_hours"]:
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
    client = config.get_database_client()
    now = datetime.now(timezone.utc).isoformat()

    try:
        result = (
            client.table("processed_content")
            .select("id, status")
            .eq("status", "retry_scheduled")
            .lte("next_retry_at", now)
            .execute()
        )

        items = [item for item in (result.data or []) if not item.get("fb_post_id")]
        count = 0

        for item in items:
            client.table("processed_content").update(
                {
                    "status": "scheduled",
                    "last_error": None,
                }
            ).eq("id", item["id"]).execute()

            client.table("scheduled_posts").update({"status": "scheduled"}).eq(
                "content_id", item["id"]
            ).execute()

            count += 1

        if count > 0:
            logger.info("Processed %d retries -> scheduled", count)

        return count

    except Exception as e:
        logger.error("Error processing retries: %s", e)
        return 0


def fetch_content_pool(limit: int = 100, user_id: Optional[str] = None):
    """Return unscheduled content items, optionally scoped to a single tenant."""
    client = config.get_database_client()
    query = (
        client.table("processed_content")
        .select("id,post_type,user_id")
        .eq("status", "drafted")
        .limit(limit)
    )
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.execute()
    return response.data or []


def schedule_posts(
    days: int = 7,
    max_per_day: int = 5,
    platforms: str = "facebook",
    user_id: Optional[str] = None,
    posting_times_override: Optional[str] = None,
    country_code: Optional[str] = None,
    timezone_name: Optional[str] = None,
) -> int:
    """
    Schedule posts for the next N days.

    Args:
        days: Number of days to schedule
        max_per_day: Maximum posts per day (configurable 1-5 for Gumroad users)
        platforms: Comma-separated platforms to publish to, e.g. "facebook"
        user_id: Tenant ID – only schedule this user's content and tag rows with their ID
        posting_times_override: Comma-separated HH:MM slot string from UserConfig.posting_times.
        country_code: Country preset code used when no explicit times are supplied.
        timezone_name: IANA timezone used to interpret explicit posting_times and stamp rows.

    Returns:
        Number of posts scheduled
    """
    content_items = fetch_content_pool(user_id=user_id)
    if not content_items:
        logger.warning("No content found in processed_content (user_id=%s)", user_id)
        return 0

    text_items = [
        item
        for item in content_items
        if str(item.get("post_type") or "").strip().lower() in AUTO_SCHEDULE_TYPES
    ]

    client = config.get_database_client()
    scheduled = 0
    start_day = date.today()
    schedule_preset = get_schedule_preset(
        country_code=country_code,
        timezone_name=timezone_name,
    )

    for offset in range(days):
        day = start_day + timedelta(days=offset)
        if posting_times_override:
            slots = _build_slots_from_times(
                day,
                posting_times_override,
                timezone_name=schedule_preset["timezone"],
            )
        else:
            slots = build_slots_for_day(
                day,
                country_code=schedule_preset["country_code"],
                timezone_name=schedule_preset["timezone"],
            )

        slots = slots[:max_per_day]

        for slot in slots:
            if not text_items:
                logger.warning("Not enough content to fill schedule (user_id=%s)", user_id)
                break

            content = text_items.pop(0)
            row_user_id = content.get("user_id") or user_id

            payload: Dict = {
                "content_id": content["id"],
                "scheduled_time": slot["scheduled_time"],
                "timezone": slot["timezone"],
                "priority": 5,
                "status": "scheduled",
                "platforms": platforms,
            }
            if row_user_id:
                payload["user_id"] = row_user_id
            client.table("scheduled_posts").insert(payload).execute()
            status_query = (
                client.table("processed_content")
                .update({"status": "scheduled"})
                .eq("id", content["id"])
            )
            if row_user_id:
                status_query = status_query.eq("user_id", row_user_id)
            status_query.execute()
            scheduled += 1

    logger.info(
        "Scheduled %s posts over %s days (max %s/day, platforms=%s, user_id=%s)",
        scheduled,
        days,
        max_per_day,
        platforms,
        user_id,
    )
    return scheduled


def schedule_for_user(user_config: "UserConfig") -> int:  # type: ignore[name-defined]
    """
    Schedule posts for a single tenant using a UserConfig object.

    The tenant's locale preset, posts_per_day, and posting_times are used
    automatically.
    """
    return schedule_posts(
        days=1,
        max_per_day=user_config.posts_per_day,
        posting_times_override=user_config.posting_times or None,
        user_id=user_config.user_id,
        country_code=user_config.country_code,
        timezone_name=user_config.timezone,
    )


if __name__ == "__main__":
    schedule_posts()
