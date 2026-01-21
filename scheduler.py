"""Generate and store a posting schedule."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List
from zoneinfo import ZoneInfo

import config

logger = config.get_logger("scheduler")


PEAK_HOURS = {
    "US_EST": [7, 12, 18, 20],
    "US_PST": [9, 14, 20, 22],
    "UK_GMT": [8, 13, 17, 21],
}

CONTENT_MIX = {
    "text": 0.60,
    "reel": 0.40,
}


def build_slots_for_day(day: date) -> List[Dict]:
    slots: List[Dict] = []
    for tz_key, hours in PEAK_HOURS.items():
        tz_name = config.TARGET_TIMEZONES[tz_key]
        tz = ZoneInfo(tz_name)
        for hour in hours:
            local_dt = datetime(day.year, day.month, day.day, hour, 0, tzinfo=tz)
            utc_dt = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
            slots.append(
                {
                    "scheduled_time": utc_dt.isoformat(),
                    "timezone": tz_name,
                }
            )
    slots.sort(key=lambda item: item["scheduled_time"])
    return enforce_min_gap(slots, min_hours=2)


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


def fetch_content_pool(limit: int = 100):
    client = config.get_supabase_client()
    response = (
        client.table("processed_content")
        .select("id,post_type")
        .limit(limit)
        .execute()
    )
    return response.data or []


def schedule_posts(days: int = 7) -> int:
    content_items = fetch_content_pool()
    if not content_items:
        logger.warning("No content found in processed_content")
        return 0

    text_items = [item for item in content_items if item["post_type"] == "text"]
    reel_items = [item for item in content_items if item["post_type"] == "reel"]

    client = config.get_supabase_client()
    scheduled = 0
    start_day = date.today()

    for offset in range(days):
        day = start_day + timedelta(days=offset)
        slots = build_slots_for_day(day)
        total_slots = len(slots)
        text_target = int(total_slots * CONTENT_MIX["text"])
        reel_target = total_slots - text_target

        for slot in slots:
            post_type = "text" if text_target > 0 else "reel"
            if post_type == "text" and text_items:
                content = text_items.pop(0)
                text_target -= 1
            elif reel_items:
                content = reel_items.pop(0)
                reel_target -= 1
            elif text_items:
                content = text_items.pop(0)
            else:
                logger.warning("Not enough content to fill schedule")
                break

            payload = {
                "content_id": content["id"],
                "scheduled_time": slot["scheduled_time"],
                "timezone": slot["timezone"],
                "priority": 5,
                "status": "scheduled",
            }
            client.table("scheduled_posts").insert(payload).execute()
            scheduled += 1

    logger.info("Scheduled %s posts", scheduled)
    return scheduled


if __name__ == "__main__":
    schedule_posts()
