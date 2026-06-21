"""
Tests for Weekend Detection and Resilience Features.
NowTrading 2.1.1 — Prevents recurring errors from today (2026-06-09).
"""

import pytest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.session_manager import is_weekend, is_trading_hours


class TestWeekendDetection:
    """
    Forex market closes Friday ~22:00 UTC → Sunday ~22:00 UTC.
    """

    # ── Saturday: always closed ──

    def test_saturday_morning(self):
        """Saturday 08:00 UTC → weekend."""
        t = datetime(2026, 6, 6, 8, 0, tzinfo=timezone.utc)  # Saturday
        assert t.weekday() == 5  # Verify it's Saturday
        assert is_weekend(t) is True

    def test_saturday_midnight(self):
        """Saturday 00:00 UTC → weekend."""
        t = datetime(2026, 6, 6, 0, 0, tzinfo=timezone.utc)
        assert is_weekend(t) is True

    def test_saturday_2359(self):
        """Saturday 23:59 UTC → weekend."""
        t = datetime(2026, 6, 6, 23, 59, tzinfo=timezone.utc)
        assert is_weekend(t) is True

    # ── Sunday: closed before 22:00, open at 22:00 ──

    def test_sunday_morning(self):
        """Sunday 10:00 UTC → weekend."""
        t = datetime(2026, 6, 7, 10, 0, tzinfo=timezone.utc)  # Sunday
        assert t.weekday() == 6
        assert is_weekend(t) is True

    def test_sunday_2159(self):
        """Sunday 21:59 UTC → still weekend (1 minute before open)."""
        t = datetime(2026, 6, 7, 21, 59, tzinfo=timezone.utc)
        assert is_weekend(t) is True

    def test_sunday_2200(self):
        """Sunday 22:00 UTC → market opens, NOT weekend."""
        t = datetime(2026, 6, 7, 22, 0, tzinfo=timezone.utc)
        assert is_weekend(t) is False

    def test_sunday_2300(self):
        """Sunday 23:00 UTC → market open, NOT weekend."""
        t = datetime(2026, 6, 7, 23, 0, tzinfo=timezone.utc)
        assert is_weekend(t) is False

    # ── Friday: open before 22:00, closed at 22:00 ──

    def test_friday_morning(self):
        """Friday 10:00 UTC → NOT weekend (market open)."""
        t = datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc)  # Friday
        assert t.weekday() == 4
        assert is_weekend(t) is False

    def test_friday_2159(self):
        """Friday 21:59 UTC → NOT weekend (1 minute before close)."""
        t = datetime(2026, 6, 5, 21, 59, tzinfo=timezone.utc)
        assert is_weekend(t) is False

    def test_friday_2200(self):
        """Friday 22:00 UTC → weekend (market closes)."""
        t = datetime(2026, 6, 5, 22, 0, tzinfo=timezone.utc)
        assert is_weekend(t) is True

    def test_friday_2300(self):
        """Friday 23:00 UTC → weekend."""
        t = datetime(2026, 6, 5, 23, 0, tzinfo=timezone.utc)
        assert is_weekend(t) is True

    # ── Weekdays: never weekend ──

    def test_monday_midnight(self):
        """Monday 00:00 UTC → NOT weekend."""
        t = datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)  # Monday
        assert t.weekday() == 0
        assert is_weekend(t) is False

    def test_tuesday(self):
        """Tuesday 15:00 UTC → NOT weekend."""
        t = datetime(2026, 6, 9, 15, 0, tzinfo=timezone.utc)  # Tuesday
        assert t.weekday() == 1
        assert is_weekend(t) is False

    def test_wednesday(self):
        """Wednesday 03:00 UTC → NOT weekend."""
        t = datetime(2026, 6, 10, 3, 0, tzinfo=timezone.utc)  # Wednesday
        assert t.weekday() == 2
        assert is_weekend(t) is False

    def test_thursday(self):
        """Thursday 20:00 UTC → NOT weekend."""
        t = datetime(2026, 6, 11, 20, 0, tzinfo=timezone.utc)  # Thursday
        assert t.weekday() == 3
        assert is_weekend(t) is False


class TestTradingHoursWithWeekend:
    """
    is_trading_hours should return False during weekends,
    even if the UTC hour falls within a session window.
    """

    def test_saturday_during_asia_hours(self):
        """Saturday 03:00 UTC → normally ASIA, but weekend → False."""
        t = datetime(2026, 6, 6, 3, 0, tzinfo=timezone.utc)  # Saturday
        assert is_trading_hours(t) is False

    def test_saturday_during_europe_hours(self):
        """Saturday 10:00 UTC → normally EUROPE, but weekend → False."""
        t = datetime(2026, 6, 6, 10, 0, tzinfo=timezone.utc)
        assert is_trading_hours(t) is False

    def test_sunday_during_us_hours(self):
        """Sunday 18:00 UTC → normally US, but weekend → False."""
        t = datetime(2026, 6, 7, 18, 0, tzinfo=timezone.utc)
        assert is_trading_hours(t) is False

    def test_sunday_after_open(self):
        """Sunday 22:30 UTC → market open, but session OFF (22:00-00:00 is OFF)."""
        t = datetime(2026, 6, 7, 22, 30, tzinfo=timezone.utc)
        # Not weekend anymore, but session is OFF (22:00-00:00)
        assert is_weekend(t) is False
        # Session is OFF at 22:30 UTC
        assert is_trading_hours(t) is False

    def test_monday_asia(self):
        """Monday 03:00 UTC → normal ASIA trading → True."""
        t = datetime(2026, 6, 8, 3, 0, tzinfo=timezone.utc)
        assert is_trading_hours(t) is True

    def test_friday_before_close(self):
        """Friday 21:00 UTC → US session, before weekend close → True."""
        t = datetime(2026, 6, 5, 21, 0, tzinfo=timezone.utc)
        assert is_trading_hours(t) is True

    def test_friday_after_close(self):
        """Friday 22:00 UTC → weekend → False."""
        t = datetime(2026, 6, 5, 22, 0, tzinfo=timezone.utc)
        assert is_trading_hours(t) is False


class TestMT5ConnectorErrorTracking:
    """Test error tracking and throttling in MT5Connector."""

    def test_error_tracking_increment(self):
        """Consecutive errors increment correctly."""
        from src.mt5_connector import MT5Connector
        connector = MT5Connector()

        assert connector.get_symbol_error_count("EURUSD") == 0
        connector.record_symbol_error("EURUSD")
        assert connector.get_symbol_error_count("EURUSD") == 1
        connector.record_symbol_error("EURUSD")
        assert connector.get_symbol_error_count("EURUSD") == 2

    def test_error_tracking_clear(self):
        """Clearing errors resets to 0."""
        from src.mt5_connector import MT5Connector
        connector = MT5Connector()

        connector.record_symbol_error("EURUSD")
        connector.record_symbol_error("EURUSD")
        connector.clear_symbol_error("EURUSD")
        assert connector.get_symbol_error_count("EURUSD") == 0

    def test_global_failure_tracking(self):
        """Global failure counter tracks correctly."""
        from src.mt5_connector import MT5Connector
        connector = MT5Connector()

        assert connector.global_consecutive_failures == 0
        connector.record_global_failure()
        connector.record_global_failure()
        assert connector.global_consecutive_failures == 2
        connector.clear_global_failure()
        assert connector.global_consecutive_failures == 0

    def test_error_log_throttling(self):
        """First call should log, immediate second call should be throttled."""
        from src.mt5_connector import MT5Connector
        connector = MT5Connector()

        # First call → should log
        assert connector._should_log_error("test_key") is True

        # Immediate second call → should be throttled
        assert connector._should_log_error("test_key") is False

    def test_different_keys_not_throttled(self):
        """Different error keys should be independent."""
        from src.mt5_connector import MT5Connector
        connector = MT5Connector()

        assert connector._should_log_error("key_a") is True
        assert connector._should_log_error("key_b") is True  # Different key, not throttled
