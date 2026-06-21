"""
Unit Tests for refactored Break-Even logic in TradeCycleManager.
"""

import pytest
from datetime import datetime, timezone
from src.trade_cycle_manager import TradeCycleManager, TradeCycle, CycleStatus
from config import settings


@pytest.fixture
def manager():
    """Create a TradeCycleManager instance."""
    return TradeCycleManager()


class TestBreakEvenLogic:
    """Test Suite for Break-Even activation and exit buffer rules."""

    def test_be_not_activated(self, manager):
        """Price does not reach the activation distance -> BE should not activate."""
        cycle = manager.open_cycle(
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1000,
            session="EUROPE",
            ticket=111
        )
        # settings: activation = 0.75, buffer = 0.0
        # For atr = 0.0100, activation_distance = 0.0075. Target = 1.1075
        # Price goes to 1.1050 (below 1.1075)
        action = manager.check_break_even("EURUSD", current_price=1.1050, atr=0.0100)
        assert action is None
        assert cycle.be_activated is False

    def test_be_activated_and_exited_zero_buffer_buy(self, manager):
        """BUY: Price reaches activation, then pulls back to entry -> BREAK_EVEN."""
        cycle = manager.open_cycle(
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1000,
            session="EUROPE",
            ticket=111
        )
        # atr = 0.0100 -> activation_distance = 0.0075. Target = 1.1075
        # 1. Price reaches activation target
        action1 = manager.check_break_even("EURUSD", current_price=1.1080, atr=0.0100)
        assert action1 is None
        assert cycle.be_activated is True

        # 2. Price pulls back to entry price (1.1000)
        action2 = manager.check_break_even("EURUSD", current_price=1.1000, atr=0.0100)
        assert action2 == "BREAK_EVEN"

    def test_be_activated_and_exited_zero_buffer_sell(self, manager):
        """SELL: Price reaches activation, then pulls back to entry -> BREAK_EVEN."""
        cycle = manager.open_cycle(
            symbol="EURUSD",
            direction="SELL",
            entry_price=1.1000,
            session="EUROPE",
            ticket=111
        )
        # atr = 0.0100 -> activation_distance = 0.0075. Target = 1.0925
        # 1. Price reaches activation target (1.0920)
        action1 = manager.check_break_even("EURUSD", current_price=1.0920, atr=0.0100)
        assert action1 is None
        assert cycle.be_activated is True

        # 2. Price pulls back to entry price (1.1000)
        action2 = manager.check_break_even("EURUSD", current_price=1.1000, atr=0.0100)
        assert action2 == "BREAK_EVEN"

    def test_be_activated_positive_buffer_buy(self, manager):
        """BUY: positive buffer -> exits above entry (locks profit)."""
        original_activation = getattr(settings, "BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER", 0.75)
        original_buffer = getattr(settings, "BREAK_EVEN_BUFFER_ATR_MULTIPLIER", 0.0)

        # Set positive buffer (0.1 * ATR = 0.0010 profit locking)
        settings.BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER = 0.75
        settings.BREAK_EVEN_BUFFER_ATR_MULTIPLIER = 0.1

        try:
            cycle = manager.open_cycle("EURUSD", "BUY", 1.1000, "EUROPE", 111)
            # atr = 0.0100 -> activation at 1.1075, exit at 1.1010
            
            # Activate
            manager.check_break_even("EURUSD", current_price=1.1080, atr=0.0100)
            assert cycle.be_activated is True

            # Pulls back but above buffer (1.1020) -> holds
            action_hold = manager.check_break_even("EURUSD", current_price=1.1020, atr=0.0100)
            assert action_hold is None

            # Pulls back to buffer level (1.1010) -> exits
            action_exit = manager.check_break_even("EURUSD", current_price=1.1010, atr=0.0100)
            assert action_exit == "BREAK_EVEN"
        finally:
            settings.BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER = original_activation
            settings.BREAK_EVEN_BUFFER_ATR_MULTIPLIER = original_buffer

    def test_be_activated_negative_buffer_buy(self, manager):
        """BUY: negative buffer -> exits below entry (allows noise)."""
        original_activation = getattr(settings, "BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER", 0.75)
        original_buffer = getattr(settings, "BREAK_EVEN_BUFFER_ATR_MULTIPLIER", 0.0)

        # Set negative buffer (-0.2 * ATR = -0.0020 noise allowance)
        settings.BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER = 0.75
        settings.BREAK_EVEN_BUFFER_ATR_MULTIPLIER = -0.2

        try:
            cycle = manager.open_cycle("EURUSD", "BUY", 1.1000, "EUROPE", 111)
            # atr = 0.0100 -> activation at 1.1075, exit at 1.0980
            
            # Activate
            manager.check_break_even("EURUSD", current_price=1.1080, atr=0.0100)
            assert cycle.be_activated is True

            # Pulls back slightly below entry to 1.0990 (above exit 1.0980) -> holds
            action_hold = manager.check_break_even("EURUSD", current_price=1.0990, atr=0.0100)
            assert action_hold is None

            # Pulls back to exit level (1.0980) -> exits
            action_exit = manager.check_break_even("EURUSD", current_price=1.0980, atr=0.0100)
            assert action_exit == "BREAK_EVEN"
        finally:
            settings.BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER = original_activation
            settings.BREAK_EVEN_BUFFER_ATR_MULTIPLIER = original_buffer
