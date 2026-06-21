"""
Tests for Trade Cycle Manager.
Constitution §5: Profit Rule, 12-Hour Rule, 24-Hour Rule.
"""

import pytest
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trade_cycle_manager import TradeCycleManager, TradeCycle, CycleStatus


@pytest.fixture
def manager():
    """Create a TradeCycleManager."""
    return TradeCycleManager()


class TestCycleOpen:
    """Test opening trade cycles."""

    def test_open_cycle(self, manager):
        """Open a new cycle successfully."""
        cycle = manager.open_cycle(
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1050,
            session="EUROPE",
            ticket=12345,
        )
        assert cycle is not None
        assert cycle.symbol == "EURUSD"
        assert cycle.direction == "BUY"
        assert cycle.status == CycleStatus.ACTIVE

    def test_cannot_open_duplicate(self, manager):
        """Cannot open two cycles for same symbol."""
        manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        result = manager.open_cycle("EURUSD", "SELL", 1.1060, "EUROPE", 222)
        assert result is None

    def test_open_different_symbols(self, manager):
        """Can open cycles for different symbols."""
        c1 = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        c2 = manager.open_cycle("GBPUSD", "SELL", 1.2650, "EUROPE", 222)
        assert c1 is not None
        assert c2 is not None
        assert manager.get_active_cycle_count() == 2


class TestProfitRule:
    """Constitution §5: Holding > 1h AND profit > $5 → close."""

    def test_profit_rule_triggered(self, manager):
        """Profit > $5 after > 1h → CLOSE_PROFIT."""
        entry_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111, entry_time)

        # Simulate 2 hours later with profit
        now = entry_time + timedelta(hours=2)
        cycle.holding_hours = 2.0
        cycle.current_profit_usd = 8.0

        action = manager.check_profit_rule("EURUSD")
        assert action == "CLOSE_PROFIT"

    def test_profit_rule_not_enough_time(self, manager):
        """Profit > $5 but < 1h → no close."""
        entry_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111, entry_time)

        cycle.holding_hours = 0.5  # Only 30 minutes
        cycle.current_profit_usd = 10.0

        action = manager.check_profit_rule("EURUSD")
        assert action is None

    def test_profit_rule_not_enough_profit(self, manager):
        """Holding > 1h but profit < $5 → no close."""
        entry_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111, entry_time)

        cycle.holding_hours = 3.0
        cycle.current_profit_usd = 3.0

        action = manager.check_profit_rule("EURUSD")
        assert action is None

    def test_profit_rule_exactly_5_usd(self, manager):
        """Profit exactly $5 → no close (must be > $5)."""
        entry_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111, entry_time)

        cycle.holding_hours = 2.0
        cycle.current_profit_usd = 5.0

        action = manager.check_profit_rule("EURUSD")
        assert action is None


class Test12HourRule:
    """Constitution §5: Holding > 12h AND no profit → check ATR / ADX."""

    def test_12h_cut_weak_adx(self, manager):
        """Holding > 12h, no profit, weak ADX → CUT_ALL."""
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle.holding_hours = 13.0
        cycle.current_profit_usd = -10.0

        action = manager.check_12h_rule("EURUSD", current_price=1.1050, adx=15.0)
        assert action == "CUT_ALL"

    def test_12h_reduce_strong_adx_with_dca(self, manager):
        """Holding > 12h, no profit, strong ADX, has DCA → REDUCE_DCA."""
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle.holding_hours = 14.0
        cycle.current_profit_usd = -5.0

        # Add a DCA layer
        manager.add_dca_layer("EURUSD", 1.1000, 0.01, 222)

        action = manager.check_12h_rule("EURUSD", current_price=1.1000, adx=30.0)
        assert action == "REDUCE_DCA"

    def test_12h_cut_strong_adx_no_dca(self, manager):
        """Holding > 12h, no profit, strong ADX, no DCA layers → CUT_ALL."""
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle.holding_hours = 14.0
        cycle.current_profit_usd = -5.0

        action = manager.check_12h_rule("EURUSD", current_price=1.1050, adx=30.0)
        assert action == "CUT_ALL"

    def test_12h_not_triggered_under_time(self, manager):
        """Holding < 12h → no action."""
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle.holding_hours = 10.0
        cycle.current_profit_usd = -5.0

        action = manager.check_12h_rule("EURUSD", current_price=1.1050, adx=15.0)
        assert action is None

    def test_12h_not_triggered_has_profit(self, manager):
        """Holding > 12h but has profit → no action."""
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle.holding_hours = 14.0
        cycle.current_profit_usd = 2.0

        action = manager.check_12h_rule("EURUSD", current_price=1.1050, adx=15.0)
        assert action is None

    def test_12h_adaptive_atr_hold(self, manager):
        """Holding > 12h, inside ATR range → None (hold)."""
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle.holding_hours = 13.0
        cycle.current_profit_usd = -10.0

        # avg_entry = 1.1050, atr = 0.0010, multiplier = 2.0 -> threshold = 0.0020
        # distance = abs(1.1040 - 1.1050) = 0.0010 <= 0.0020 -> hold
        action = manager.check_12h_rule("EURUSD", current_price=1.1040, adx=15.0, atr=0.0010)
        assert action is None
        assert cycle.dca_frozen is False

    def test_12h_adaptive_atr_out_of_range(self, manager):
        """Holding > 12h, outside ATR range → freeze and decide."""
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle.holding_hours = 13.0
        cycle.current_profit_usd = -10.0

        # avg_entry = 1.1050, atr = 0.0010, multiplier = 2.0 -> threshold = 0.0020
        # distance = abs(1.1020 - 1.1050) = 0.0030 > 0.0020 -> freeze, and cut due to weak adx
        action = manager.check_12h_rule("EURUSD", current_price=1.1020, adx=15.0, atr=0.0010)
        assert action == "CUT_ALL"
        assert cycle.dca_frozen is True


class Test24HourRule:
    """Constitution §5: Holding > 24h AND no profit → REGIME_FILTER_EXIT."""

    def test_24h_sideways_holds(self, manager):
        """Holding > 24h, no profit, sideways/no reversal/not overextended → None (hold)."""
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle.holding_hours = 25.0
        cycle.current_profit_usd = -15.0

        action = manager.check_conditional_force_close("EURUSD", current_price=1.1050)
        assert action is None

    def test_24h_rsi_overextended_close(self, manager):
        """Holding > 24h, H1 RSI overextended against position → FORCE_CLOSE."""
        # BUY overextended low
        cycle1 = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle1.holding_hours = 25.0
        cycle1.current_profit_usd = -15.0

        action1 = manager.check_conditional_force_close("EURUSD", current_price=1.1050, rsi_h1=29.0)
        assert action1 == "FORCE_CLOSE"

        # SELL overextended high
        manager.close_cycle("EURUSD", "FORCE_CLOSE")
        cycle2 = manager.open_cycle("GBPUSD", "SELL", 1.2500, "EUROPE", 222)
        cycle2.holding_hours = 25.0
        cycle2.current_profit_usd = -15.0

        action2 = manager.check_conditional_force_close("GBPUSD", current_price=1.2500, rsi_h1=71.0)
        assert action2 == "FORCE_CLOSE"

    def test_24h_trend_reversed_close(self, manager):
        """Holding > 24h, trend reversed (ADX > 25, RSI trend opposite) → FORCE_CLOSE."""
        # BUY reversed to bearish
        cycle1 = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle1.holding_hours = 25.0
        cycle1.current_profit_usd = -15.0

        # ADX >= 25, RSI_H4 & RSI_H1 both bearish (< 45)
        action1 = manager.check_conditional_force_close("EURUSD", current_price=1.1050, adx=26.0, rsi_h4=40.0, rsi_h1=40.0)
        assert action1 == "FORCE_CLOSE"

        # SELL reversed to bullish
        manager.close_cycle("EURUSD", "FORCE_CLOSE")
        cycle2 = manager.open_cycle("GBPUSD", "SELL", 1.2500, "EUROPE", 222)
        cycle2.holding_hours = 25.0
        cycle2.current_profit_usd = -15.0

        # ADX >= 25, RSI_H4 & RSI_H1 both bullish (> 55)
        action2 = manager.check_conditional_force_close("GBPUSD", current_price=1.2500, adx=26.0, rsi_h4=60.0, rsi_h1=60.0)
        assert action2 == "FORCE_CLOSE"



    def test_24h_not_triggered_has_profit(self, manager):
        """Holding > 24h but has profit → no action."""
        cycle = manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        cycle.holding_hours = 30.0
        cycle.current_profit_usd = 3.0

        action = manager.check_conditional_force_close("EURUSD", current_price=1.1050, rsi_h1=25.0)
        assert action is None


class TestDCALayers:
    """Test DCA layer management."""

    def test_add_dca_layer(self, manager):
        """Add DCA layer to cycle."""
        manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        result = manager.add_dca_layer("EURUSD", 1.1000, 0.01, 222)
        assert result is True

        cycle = manager.get_cycle("EURUSD")
        assert cycle.num_dca_layers == 1

    def test_remove_worst_dca_buy(self, manager):
        """Remove worst DCA for BUY (highest entry)."""
        manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        manager.add_dca_layer("EURUSD", 1.1020, 0.01, 222)  # Better
        manager.add_dca_layer("EURUSD", 1.1000, 0.01, 333)  # Best (lowest)

        worst = manager.remove_worst_dca("EURUSD")
        assert worst is not None
        assert worst.entry_price == 1.1020  # Highest DCA entry = worst for BUY

    def test_average_entry_price(self, manager):
        """Average entry with DCA layers."""
        manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        manager.add_dca_layer("EURUSD", 1.1000, 0.01, 222)

        cycle = manager.get_cycle("EURUSD")
        # avg = (1.1050 * 0.01 + 1.1000 * 0.01) / (0.01 + 0.01) = 1.1025
        assert abs(cycle.average_entry_price - 1.1025) < 0.0001


class TestCycleClose:
    """Test cycle closing."""

    def test_close_cycle(self, manager):
        """Close cycle moves it to history."""
        manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)
        closed = manager.close_cycle("EURUSD", "PROFIT_TARGET")

        assert closed is not None
        assert closed.status == CycleStatus.CLOSED
        assert closed.close_reason == "PROFIT_TARGET"
        assert manager.has_active_cycle("EURUSD") is False
        assert len(manager.get_closed_cycles()) == 1

    def test_close_nonexistent(self, manager):
        """Close non-existent cycle → None."""
        result = manager.close_cycle("EURUSD", "TEST")
        assert result is None
