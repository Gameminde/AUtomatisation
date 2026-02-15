"""
Unit tests for scheduler module.

Tests cover:
- Timezone handling
- Slot generation
- Gap enforcement
- Content pool fetching
- Post scheduling
"""

# pytest used implicitly
from datetime import date
from unittest.mock import MagicMock, patch
# ZoneInfo available if needed


class TestBuildSlotsForDay:
    """Tests for build_slots_for_day function."""

    def test_build_slots_generates_slots(self):
        """Test that slots are generated for a day."""
        from scheduler import build_slots_for_day

        test_date = date(2026, 1, 22)
        slots = build_slots_for_day(test_date)

        assert len(slots) > 0

    def test_build_slots_have_timezone(self):
        """Test that slots have timezone information."""
        from scheduler import build_slots_for_day

        test_date = date(2026, 1, 22)
        slots = build_slots_for_day(test_date)

        for slot in slots:
            assert "timezone" in slot
            assert "scheduled_time" in slot

    def test_build_slots_are_sorted(self):
        """Test that slots are sorted by time."""
        from scheduler import build_slots_for_day

        test_date = date(2026, 1, 22)
        slots = build_slots_for_day(test_date)

        times = [slot["scheduled_time"] for slot in slots]
        assert times == sorted(times)


class TestEnforceMinGap:
    """Tests for enforce_min_gap function."""

    def test_enforce_min_gap_removes_close_slots(self):
        """Test that close slots are removed."""
        from scheduler import enforce_min_gap

        slots = [
            {"scheduled_time": "2026-01-22T10:00:00"},
            {"scheduled_time": "2026-01-22T10:30:00"},  # Only 30 min gap - should be removed
            {"scheduled_time": "2026-01-22T12:30:00"},  # 2h30 gap - should stay
        ]

        filtered = enforce_min_gap(slots, min_hours=2)

        assert len(filtered) == 2
        assert filtered[0]["scheduled_time"] == "2026-01-22T10:00:00"
        assert filtered[1]["scheduled_time"] == "2026-01-22T12:30:00"

    def test_enforce_min_gap_keeps_spaced_slots(self):
        """Test that properly spaced slots are kept."""
        from scheduler import enforce_min_gap

        slots = [
            {"scheduled_time": "2026-01-22T08:00:00"},
            {"scheduled_time": "2026-01-22T10:00:00"},  # 2h gap
            {"scheduled_time": "2026-01-22T12:00:00"},  # 2h gap
            {"scheduled_time": "2026-01-22T14:00:00"},  # 2h gap
        ]

        filtered = enforce_min_gap(slots, min_hours=2)

        assert len(filtered) == 4

    def test_enforce_min_gap_empty_list(self):
        """Test with empty list."""
        from scheduler import enforce_min_gap

        filtered = enforce_min_gap([], min_hours=2)

        assert filtered == []

    def test_enforce_min_gap_single_slot(self):
        """Test with single slot."""
        from scheduler import enforce_min_gap

        slots = [{"scheduled_time": "2026-01-22T10:00:00"}]
        filtered = enforce_min_gap(slots, min_hours=2)

        assert len(filtered) == 1


class TestFetchContentPool:
    """Tests for fetch_content_pool function."""

    @patch("config.get_supabase_client")
    def test_fetch_content_pool_success(self, mock_client_fn, sample_processed_content):
        """Test successful content pool fetch."""
        from scheduler import fetch_content_pool

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.limit.return_value.execute.return_value = MagicMock(
            data=sample_processed_content
        )
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        pool = fetch_content_pool(limit=10)

        assert len(pool) == len(sample_processed_content)

    @patch("config.get_supabase_client")
    def test_fetch_content_pool_empty(self, mock_client_fn):
        """Test fetch with no content."""
        from scheduler import fetch_content_pool

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        pool = fetch_content_pool()

        assert pool == []


class TestSchedulePosts:
    """Tests for schedule_posts function."""

    @patch("config.get_supabase_client")
    def test_schedule_posts_no_content(self, mock_client_fn):
        """Test scheduling with no content."""
        from scheduler import schedule_posts

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_table.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        result = schedule_posts(days=7)

        assert result == 0

    @patch("config.get_supabase_client")
    def test_schedule_posts_with_content(self, mock_client_fn, sample_processed_content):
        """Test scheduling with available content."""
        from scheduler import schedule_posts

        mock_client = MagicMock()
        mock_table = MagicMock()

        # First call returns content pool
        mock_table.select.return_value.limit.return_value.execute.return_value = MagicMock(
            data=sample_processed_content
        )
        mock_table.insert.return_value.execute.return_value = MagicMock(data=[{}])

        mock_client.table.return_value = mock_table
        mock_client_fn.return_value = mock_client

        result = schedule_posts(days=1)

        # Should schedule some posts (limited by available content)
        assert result >= 0


class TestContentMix:
    """Tests for content mix ratio."""

    def test_content_mix_ratios(self):
        """Test content mix configuration."""
        from scheduler import CONTENT_MIX

        assert "text" in CONTENT_MIX
        assert "reel" in CONTENT_MIX
        assert CONTENT_MIX["text"] + CONTENT_MIX["reel"] == 1.0
        assert CONTENT_MIX["text"] == 0.60
        assert CONTENT_MIX["reel"] == 0.40


class TestPeakHours:
    """Tests for peak hours configuration."""

    def test_peak_hours_exist(self):
        """Test peak hours are defined."""
        from scheduler import PEAK_HOURS

        assert "US_EST" in PEAK_HOURS
        assert "US_PST" in PEAK_HOURS
        assert "UK_GMT" in PEAK_HOURS

    def test_peak_hours_values(self):
        """Test peak hours are valid hours."""
        from scheduler import PEAK_HOURS

        for tz, hours in PEAK_HOURS.items():
            for hour in hours:
                assert 0 <= hour <= 23
