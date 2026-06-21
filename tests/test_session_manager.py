"""
Tests for Session Manager.
Constitution: Bot trades all 3 sessions — Asia, Europe, US.
"""

import pytest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.session_manager import (
    Session,
    get_current_session,
    is_trading_hours,
    get_session_name,
)


class TestAsiaSession:
    """Asia session: 00:00 - 09:00 UTC."""

    def test_asia_early(self):
        """00:30 UTC → ASIA."""
        t = datetime(2025, 1, 15, 0, 30, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.ASIA

    def test_asia_mid(self):
        """04:00 UTC → ASIA."""
        t = datetime(2025, 1, 15, 4, 0, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.ASIA

    def test_asia_late(self):
        """06:30 UTC → ASIA (before EU overlap)."""
        t = datetime(2025, 1, 15, 6, 30, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.ASIA


class TestEuropeSession:
    """Europe session: 07:00 - 16:00 UTC."""

    def test_europe_solo(self):
        """10:00 UTC → EUROPE."""
        t = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.EUROPE

    def test_europe_mid(self):
        """11:00 UTC → EUROPE."""
        t = datetime(2025, 1, 15, 11, 0, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.EUROPE


class TestUSSession:
    """US session: 13:00 - 22:00 UTC."""

    def test_us_solo(self):
        """18:00 UTC → US."""
        t = datetime(2025, 1, 15, 18, 0, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.US

    def test_us_late(self):
        """21:00 UTC → US."""
        t = datetime(2025, 1, 15, 21, 0, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.US


class TestOverlapSessions:
    """Overlap session detection."""

    def test_asia_europe_overlap(self):
        """07:30 UTC → OVERLAP_ASIA_EU."""
        t = datetime(2025, 1, 15, 7, 30, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.OVERLAP_ASIA_EU

    def test_europe_us_overlap(self):
        """14:00 UTC → OVERLAP_EU_US."""
        t = datetime(2025, 1, 15, 14, 0, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.OVERLAP_EU_US

    def test_overlap_start(self):
        """13:00 UTC → OVERLAP_EU_US (EU + US both active)."""
        t = datetime(2025, 1, 15, 13, 0, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.OVERLAP_EU_US


class TestOffHours:
    """Off-market hours: 22:00 - 00:00 UTC."""

    def test_off_hours_late_night(self):
        """23:00 UTC → OFF."""
        t = datetime(2025, 1, 15, 23, 0, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.OFF

    def test_off_hours_2230(self):
        """22:30 UTC → OFF."""
        t = datetime(2025, 1, 15, 22, 30, tzinfo=timezone.utc)
        assert get_current_session(t) == Session.OFF


class TestTradingHours:
    """Test is_trading_hours helper."""

    def test_trading_hours_during_session(self):
        """During any session → True."""
        t = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        assert is_trading_hours(t) is True

    def test_not_trading_hours_off(self):
        """During OFF hours → False."""
        t = datetime(2025, 1, 15, 23, 0, tzinfo=timezone.utc)
        assert is_trading_hours(t) is False


class TestSessionName:
    """Test get_session_name helper."""

    def test_session_name_asia(self):
        t = datetime(2025, 1, 15, 3, 0, tzinfo=timezone.utc)
        assert get_session_name(t) == "ASIA"

    def test_session_name_europe(self):
        t = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        assert get_session_name(t) == "EUROPE"

    def test_session_name_us(self):
        t = datetime(2025, 1, 15, 18, 0, tzinfo=timezone.utc)
        assert get_session_name(t) == "US"
