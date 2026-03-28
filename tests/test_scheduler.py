"""Unit tests for scheduler module aligned with the current runtime."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo


def _table_chain(data=None):
    table = MagicMock()
    table.select.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.eq.return_value = table
    table.lte.return_value = table
    table.limit.return_value = table
    table.order.return_value = table
    table.execute.return_value = MagicMock(data=data or [])
    return table


class TestBuildSlotsForDay:
    def test_build_slots_generates_slots(self):
        from scheduler import build_slots_for_day

        slots = build_slots_for_day(date(2026, 1, 22))
        assert len(slots) > 0

    def test_build_slots_have_timezone(self):
        from scheduler import build_slots_for_day

        for slot in build_slots_for_day(date(2026, 1, 22)):
            assert "timezone" in slot
            assert "scheduled_time" in slot

    def test_build_slots_are_sorted(self):
        from scheduler import build_slots_for_day

        slots = build_slots_for_day(date(2026, 1, 22))
        assert [slot["scheduled_time"] for slot in slots] == sorted(
            slot["scheduled_time"] for slot in slots
        )


class TestBuildSlotsFromTimes:
    def test_build_slots_from_times_returns_utc_slots(self):
        from scheduler import _build_slots_from_times

        slots = _build_slots_from_times(date(2026, 1, 22), "08:00,13:00,19:00")

        assert len(slots) == 3
        assert all(slot["timezone"] == "UTC" for slot in slots)

    def test_build_slots_from_times_skips_invalid_tokens(self):
        from scheduler import _build_slots_from_times

        slots = _build_slots_from_times(date(2026, 1, 22), "08:00,bad,19:00")

        assert len(slots) == 2

    @patch("random.randint", return_value=0)
    def test_build_slots_from_times_uses_local_timezone(self, _mock_randint):
        from scheduler import _build_slots_from_times

        slots = _build_slots_from_times(
            date(2026, 1, 22),
            "08:00",
            timezone_name="Africa/Cairo",
        )

        expected = (
            datetime(2026, 1, 22, 8, 0, tzinfo=ZoneInfo("Africa/Cairo"))
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
            .isoformat()
        )

        assert slots == [{"scheduled_time": expected, "timezone": "Africa/Cairo"}]


class TestEnforceMinGap:
    def test_enforce_min_gap_removes_close_slots(self):
        from scheduler import enforce_min_gap

        slots = [
            {"scheduled_time": "2026-01-22T10:00:00"},
            {"scheduled_time": "2026-01-22T10:30:00"},
            {"scheduled_time": "2026-01-22T12:30:00"},
        ]

        filtered = enforce_min_gap(slots, min_hours=2)

        assert len(filtered) == 2
        assert filtered[0]["scheduled_time"] == "2026-01-22T10:00:00"
        assert filtered[1]["scheduled_time"] == "2026-01-22T12:30:00"

    def test_enforce_min_gap_keeps_spaced_slots(self):
        from scheduler import enforce_min_gap

        slots = [
            {"scheduled_time": "2026-01-22T08:00:00"},
            {"scheduled_time": "2026-01-22T10:00:00"},
            {"scheduled_time": "2026-01-22T12:00:00"},
        ]

        assert len(enforce_min_gap(slots, min_hours=2)) == 3

    def test_enforce_min_gap_empty_list(self):
        from scheduler import enforce_min_gap

        assert enforce_min_gap([], min_hours=2) == []


class TestFetchContentPool:
    @patch("config.get_database_client")
    def test_fetch_content_pool_returns_drafted_rows(self, mock_client_fn):
        from scheduler import fetch_content_pool

        expected = [{"id": "c1", "post_type": "text", "user_id": "user-1"}]
        table = _table_chain(expected)
        client = MagicMock()
        client.table.return_value = table
        mock_client_fn.return_value = client

        assert fetch_content_pool(limit=10) == expected

    @patch("config.get_database_client")
    def test_fetch_content_pool_scopes_user(self, mock_client_fn):
        from scheduler import fetch_content_pool

        table = _table_chain([])
        client = MagicMock()
        client.table.return_value = table
        mock_client_fn.return_value = client

        fetch_content_pool(limit=10, user_id="user-1")

        table.eq.assert_any_call("user_id", "user-1")

    @patch("config.get_database_client")
    def test_fetch_content_pool_empty(self, mock_client_fn):
        from scheduler import fetch_content_pool

        table = _table_chain([])
        client = MagicMock()
        client.table.return_value = table
        mock_client_fn.return_value = client

        assert fetch_content_pool() == []


class TestSchedulePosts:
    @patch("scheduler.fetch_content_pool", return_value=[])
    def test_schedule_posts_no_content(self, mock_pool):
        from scheduler import schedule_posts

        assert schedule_posts(days=7) == 0

    @patch("config.get_database_client")
    @patch("scheduler.build_slots_for_day")
    @patch("scheduler.fetch_content_pool")
    def test_schedule_posts_inserts_rows_and_updates_content(
        self, mock_pool, mock_build_slots, mock_client_fn
    ):
        from scheduler import schedule_posts

        mock_pool.return_value = [
            {"id": "c1", "post_type": "text", "user_id": "user-1"},
            {"id": "c2", "post_type": "text", "user_id": "user-1"},
        ]
        mock_build_slots.return_value = [
            {"scheduled_time": "2026-01-22T10:00:00", "timezone": "UTC"},
            {"scheduled_time": "2026-01-22T12:00:00", "timezone": "UTC"},
        ]

        scheduled_table = _table_chain([{}])
        content_table = _table_chain([{}])
        client = MagicMock()

        def table_for(name):
            return {
                "scheduled_posts": scheduled_table,
                "processed_content": content_table,
            }[name]

        client.table.side_effect = table_for
        mock_client_fn.return_value = client

        result = schedule_posts(days=1, max_per_day=2, user_id="user-1")

        assert result == 2
        assert scheduled_table.insert.call_count == 2
        assert content_table.update.call_count == 2

    @patch("config.get_database_client")
    @patch("scheduler.build_slots_for_day")
    @patch("scheduler.fetch_content_pool")
    def test_schedule_posts_skips_draft_only_formats(
        self, mock_pool, mock_build_slots, mock_client_fn
    ):
        from scheduler import schedule_posts

        mock_pool.return_value = [
            {"id": "c1", "post_type": "story_sequence", "user_id": "user-1"},
            {"id": "c2", "post_type": "reel_script", "user_id": "user-1"},
        ]
        mock_build_slots.return_value = [
            {"scheduled_time": "2026-01-22T10:00:00", "timezone": "UTC"},
        ]
        client = MagicMock()
        scheduled_table = _table_chain([{}])
        content_table = _table_chain([{}])
        client.table.side_effect = lambda name: {
            "scheduled_posts": scheduled_table,
            "processed_content": content_table,
        }[name]
        mock_client_fn.return_value = client

        assert schedule_posts(days=1, max_per_day=1, user_id="user-1") == 0
        scheduled_table.insert.assert_not_called()

    @patch("config.get_database_client")
    @patch("scheduler._build_slots_from_times")
    @patch("scheduler.fetch_content_pool")
    def test_schedule_posts_respects_posting_times_override(
        self, mock_pool, mock_build_slots_from_times, mock_client_fn
    ):
        from scheduler import schedule_posts

        mock_pool.return_value = [{"id": "c1", "post_type": "text", "user_id": "row-user"}]
        mock_build_slots_from_times.return_value = [
            {"scheduled_time": "2026-01-22T08:00:00", "timezone": "UTC"}
        ]

        scheduled_table = _table_chain([{}])
        content_table = _table_chain([{}])
        client = MagicMock()
        client.table.side_effect = lambda name: {
            "scheduled_posts": scheduled_table,
            "processed_content": content_table,
        }[name]
        mock_client_fn.return_value = client

        result = schedule_posts(days=1, posting_times_override="08:00,13:00")

        assert result == 1
        mock_build_slots_from_times.assert_called_once()

    @patch("config.get_database_client")
    @patch("scheduler.build_slots_for_day")
    @patch("scheduler.fetch_content_pool")
    def test_schedule_posts_uses_row_user_id_as_canonical_tag(
        self, mock_pool, mock_build_slots, mock_client_fn
    ):
        from scheduler import schedule_posts

        mock_pool.return_value = [{"id": "c1", "post_type": "text", "user_id": "row-user"}]
        mock_build_slots.return_value = [
            {"scheduled_time": "2026-01-22T10:00:00", "timezone": "UTC"}
        ]

        scheduled_table = _table_chain([{}])
        content_table = _table_chain([{}])
        client = MagicMock()
        client.table.side_effect = lambda name: {
            "scheduled_posts": scheduled_table,
            "processed_content": content_table,
        }[name]
        mock_client_fn.return_value = client

        schedule_posts(days=1, user_id="request-user")

        payload = scheduled_table.insert.call_args[0][0]
        assert payload["user_id"] == "row-user"


class TestProcessRetries:
    @patch("config.get_database_client")
    def test_process_retries_promotes_due_items(self, mock_client_fn):
        from scheduler import process_retries

        content_table = _table_chain([{"id": "c1", "status": "retry_scheduled", "fb_post_id": None}])
        schedule_table = _table_chain([{}])
        client = MagicMock()
        client.table.side_effect = lambda name: {
            "processed_content": content_table,
            "scheduled_posts": schedule_table,
        }[name]
        mock_client_fn.return_value = client

        assert process_retries() == 1
        assert content_table.update.call_count >= 1
        assert schedule_table.update.call_count >= 1


class TestScheduleForUser:
    @patch("scheduler.schedule_posts", return_value=3)
    def test_schedule_for_user_uses_user_config(self, mock_schedule_posts):
        from scheduler import schedule_for_user

        user_config = MagicMock(
            user_id="user-1",
            posts_per_day=3,
            posting_times="08:00,13:00,19:00",
            country_code="MA",
            timezone="Africa/Casablanca",
        )

        assert schedule_for_user(user_config) == 3
        mock_schedule_posts.assert_called_once_with(
            days=1,
            max_per_day=3,
            posting_times_override="08:00,13:00,19:00",
            user_id="user-1",
            country_code="MA",
            timezone_name="Africa/Casablanca",
        )


class TestConstants:
    def test_content_mix_is_text_only(self):
        from scheduler import CONTENT_MIX

        assert CONTENT_MIX == {"post": 0.7, "carousel": 0.3}

    def test_peak_hours_exist(self):
        from scheduler import PEAK_HOURS

        assert "US" in PEAK_HOURS
        assert "UK" in PEAK_HOURS
        assert "FR" in PEAK_HOURS
        assert "DE" in PEAK_HOURS
        assert "AE" in PEAK_HOURS
        assert "SA" in PEAK_HOURS
        assert "QA" in PEAK_HOURS
        assert "KW" in PEAK_HOURS
        assert "OTHER" in PEAK_HOURS

    def test_default_posting_windows_exist(self):
        from scheduler import DEFAULT_POSTING_WINDOWS

        assert DEFAULT_POSTING_WINDOWS["US"] == "11:00,14:00,19:00"
        assert DEFAULT_POSTING_WINDOWS["FR"] == "12:00,18:00,20:00"
        assert DEFAULT_POSTING_WINDOWS["AE"] == "12:00,18:00,21:00"

    def test_peak_hours_values_are_hours(self):
        from scheduler import PEAK_HOURS

        for hours in PEAK_HOURS.values():
            for hour in hours:
                assert 0 <= hour <= 23
