"""
Tests for Hourly Gate.
Constitution §4: One trade per symbol per hourly bucket.
"""

import pytest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hourly_gate import HourlyGate


@pytest.fixture
def gate():
    """Create HourlyGate with 5-minute window."""
    return HourlyGate(window_minutes=5)


class TestHourlyGateWindow:
    """Test trade timing within gate window."""

    def test_allow_at_minute_1(self, gate):
        """Trade at minute 1 → allowed."""
        t = datetime(2025, 1, 15, 14, 1, 0, tzinfo=timezone.utc)
        allowed, reason = gate.can_trade("EURUSD", t)
        assert allowed is True

    def test_block_at_minute_0(self, gate):
        """Trade at minute 0 (first 60s) → blocked."""
        t = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
        allowed, reason = gate.can_trade("EURUSD", t)
        assert allowed is False
        assert "First 60 seconds cooldown" in reason

    def test_allow_at_minute_3(self, gate):
        """Trade within window (minute 3) → allowed."""
        t = datetime(2025, 1, 15, 14, 3, 0, tzinfo=timezone.utc)
        allowed, reason = gate.can_trade("EURUSD", t)
        assert allowed is True

    def test_allow_at_minute_4(self, gate):
        """Trade at minute 4 → allowed (< 5)."""
        t = datetime(2025, 1, 15, 14, 4, 59, tzinfo=timezone.utc)
        allowed, reason = gate.can_trade("EURUSD", t)
        assert allowed is True

    def test_block_at_minute_5(self, gate):
        """Trade at minute 5 → blocked."""
        t = datetime(2025, 1, 15, 14, 5, 0, tzinfo=timezone.utc)
        allowed, reason = gate.can_trade("EURUSD", t)
        assert allowed is False

    def test_block_at_minute_30(self, gate):
        """Trade at minute 30 → blocked."""
        t = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        allowed, reason = gate.can_trade("EURUSD", t)
        assert allowed is False


class TestDuplicatePrevention:
    """Test one trade per symbol per hour."""

    def test_block_duplicate_same_hour(self, gate):
        """Second trade in same hour → blocked."""
        t1 = datetime(2025, 1, 15, 14, 1, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 15, 14, 2, 0, tzinfo=timezone.utc)

        allowed1, _ = gate.can_trade("EURUSD", t1)
        assert allowed1 is True
        gate.record_trade("EURUSD", t1)

        allowed2, reason = gate.can_trade("EURUSD", t2)
        assert allowed2 is False
        assert "Already traded" in reason

    def test_allow_different_hour(self, gate):
        """Trade in next hour → allowed."""
        t1 = datetime(2025, 1, 15, 14, 1, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 15, 15, 1, 0, tzinfo=timezone.utc)

        gate.record_trade("EURUSD", t1)

        allowed, _ = gate.can_trade("EURUSD", t2)
        assert allowed is True

    def test_allow_different_symbol_same_hour(self, gate):
        """Different symbol in same hour → allowed."""
        t = datetime(2025, 1, 15, 14, 1, 0, tzinfo=timezone.utc)

        gate.record_trade("EURUSD", t)

        allowed, _ = gate.can_trade("GBPUSD", t)
        assert allowed is True

    def test_block_same_symbol_same_bucket(self, gate):
        """Same symbol, different minute in same bucket → blocked."""
        t1 = datetime(2025, 1, 15, 14, 1, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 1, 15, 14, 3, 0, tzinfo=timezone.utc)

        gate.record_trade("XAUUSD", t1)

        allowed, _ = gate.can_trade("XAUUSD", t2)
        assert allowed is False


class TestReset:
    """Test gate reset functionality."""

    def test_reset_single_symbol(self, gate):
        """Reset one symbol → that symbol can trade again."""
        t = datetime(2025, 1, 15, 14, 1, 0, tzinfo=timezone.utc)
        gate.record_trade("EURUSD", t)
        gate.record_trade("GBPUSD", t)

        gate.reset("EURUSD")

        allowed_eur, _ = gate.can_trade("EURUSD", t)
        allowed_gbp, _ = gate.can_trade("GBPUSD", t)
        assert allowed_eur is True
        assert allowed_gbp is False

    def test_reset_all(self, gate):
        """Reset all → all symbols can trade again."""
        t = datetime(2025, 1, 15, 14, 1, 0, tzinfo=timezone.utc)
        gate.record_trade("EURUSD", t)
        gate.record_trade("GBPUSD", t)

        gate.reset()

        allowed_eur, _ = gate.can_trade("EURUSD", t)
        allowed_gbp, _ = gate.can_trade("GBPUSD", t)
        assert allowed_eur is True
        assert allowed_gbp is True
