"""
Tests for ATR DCA Engine (v2.1).
Constitution §13: Tiered ATR-based DCA spacing and validation.
"""

import pytest
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.atr_dca_engine import ATRDCAEngine
from src.signal_engine import SignalEngine
from src.regime_engine import RegimeEngine
from src.trade_cycle_manager import TradeCycle, CycleStatus


def _make_cycle(
    symbol="EURUSD",
    direction="BUY",
    entry_price=1.1050,
    dca_count=0,
    holding_hours=2.0,
    dca_frozen=False,
):
    """Helper to create a TradeCycle for testing."""
    from src.trade_cycle_manager import DCALayer

    cycle = TradeCycle(
        symbol=symbol,
        direction=direction,
        entry_time=datetime.now(timezone.utc) - timedelta(hours=holding_hours),
        session="EUROPE",
        base_entry_price=entry_price,
        holding_hours=holding_hours,
        tickets=[111],
        dca_frozen=dca_frozen,
    )

    for i in range(dca_count):
        offset = 0.0010 * (i + 1)
        price = entry_price - offset if direction == "BUY" else entry_price + offset
        layer = DCALayer(
            entry_price=price,
            lot_size=0.01,
            entry_time=datetime.now(timezone.utc) - timedelta(hours=holding_hours - 1),
            ticket=200 + i,
        )
        cycle.dca_layers.append(layer)
        cycle.tickets.append(200 + i)

    return cycle


@pytest.fixture
def engine():
    """Create ATR DCA Engine with RegimeEngine attached."""
    from config import settings
    # Override settings for tests if needed, but defaults are fine
    settings.DCA_LAYER_1_ATR = 1.0
    settings.DCA_LAYER_2_ATR = 1.5
    settings.DCA_LAYER_3_ATR = 2.0
    settings.HOLDING_MAX_HOURS = 24.0
    return ATRDCAEngine(
        signal_engine=SignalEngine(RegimeEngine()),
    )


class TestDCASpacing:
    """Test ATR-based tier spacing calculation."""

    def test_spacing_layer_1(self, engine):
        spacing = engine.calculate_dca_spacing(0.0010, layer_index=0)
        assert abs(spacing - 0.0010) < 1e-10

    def test_spacing_layer_2(self, engine):
        spacing = engine.calculate_dca_spacing(0.0010, layer_index=1)
        assert abs(spacing - 0.0015) < 1e-10

    def test_spacing_layer_3(self, engine):
        spacing = engine.calculate_dca_spacing(0.0010, layer_index=2)
        assert abs(spacing - 0.0020) < 1e-10


class TestDCAValidation:
    """Test DCA entry conditions."""

    def test_dca_valid_buy(self, engine):
        """Valid BUY DCA layer 1."""
        cycle = _make_cycle(direction="BUY", entry_price=1.1050)
        indicators = {
            "RSI_H4": 60.0, "RSI_H1": 60.0, "RSI_M15": 48.0,
            "ADX": 30.0, "ATR": 0.0010,
        }
        # Layer 1 requires 1.0 ATR distance = 0.0010.
        # Price drops 0.0020 > 0.0010.
        should, reason = engine.should_dca(cycle, 1.1030, indicators)
        assert should is True

    def test_dca_blocked_max_layers(self, engine):
        cycle = _make_cycle(direction="BUY", entry_price=1.1050, dca_count=3)
        indicators = {
            "RSI_H4": 60.0, "RSI_H1": 60.0, "RSI_M15": 48.0,
            "ADX": 30.0, "ATR": 0.0010,
        }
        should, reason = engine.should_dca(cycle, 1.1000, indicators)
        assert should is False
        assert "Max DCA layers" in reason

    def test_dca_blocked_not_enough_distance(self, engine):
        cycle = _make_cycle(direction="BUY", entry_price=1.1050)
        indicators = {
            "RSI_H4": 60.0, "RSI_H1": 60.0, "RSI_M15": 48.0,
            "ADX": 30.0, "ATR": 0.0010,
        }
        # Price only dropped 0.0005 < 0.0010 (layer 1)
        should, reason = engine.should_dca(cycle, 1.1045, indicators)
        assert should is False
        assert "distance" in reason

    def test_dca_blocked_rsi_reversed(self, engine):
        cycle = _make_cycle(direction="BUY", entry_price=1.1050)
        indicators = {
            "RSI_H4": 40.0,   # Below sell threshold — reversed!
            "RSI_H1": 42.0,
            "RSI_M15": 38.0,
            "ADX": 30.0,
            "ATR": 0.0010,
        }
        should, reason = engine.should_dca(cycle, 1.1030, indicators)
        assert should is False
        assert "reversed" in reason or "killed" in reason

    def test_dca_blocked_frozen(self, engine):
        cycle = _make_cycle(direction="BUY", entry_price=1.1050, dca_frozen=True)
        indicators = {
            "RSI_H4": 60.0, "RSI_H1": 60.0, "RSI_M15": 48.0,
            "ADX": 30.0, "ATR": 0.0010,
        }
        should, reason = engine.should_dca(cycle, 1.1030, indicators)
        assert should is False
        assert "frozen" in reason

    def test_dca_blocked_24h(self, engine):
        cycle = _make_cycle(direction="BUY", entry_price=1.1050, holding_hours=25.0)
        indicators = {
            "RSI_H4": 60.0, "RSI_H1": 60.0, "RSI_M15": 48.0,
            "ADX": 30.0, "ATR": 0.0010,
        }
        should, reason = engine.should_dca(cycle, 1.1030, indicators)
        assert should is False
        assert "24h rule" in reason

    def test_dca_blocked_no_atr(self, engine):
        cycle = _make_cycle(direction="BUY", entry_price=1.1050)
        indicators = {
            "RSI_H4": 60.0, "RSI_H1": 60.0, "RSI_M15": 48.0,
            "ADX": 30.0, "ATR": None,
        }
        should, reason = engine.should_dca(cycle, 1.1030, indicators)
        assert should is False

    def test_dca_blocked_buy_price_above(self, engine):
        cycle = _make_cycle(direction="BUY", entry_price=1.1050)
        indicators = {
            "RSI_H4": 60.0, "RSI_H1": 60.0, "RSI_M15": 48.0,
            "ADX": 30.0, "ATR": 0.0010,
        }
        should, reason = engine.should_dca(cycle, 1.1070, indicators)
        assert should is False

    def test_dca_valid_sell(self, engine):
        cycle = _make_cycle(direction="SELL", entry_price=1.1050)
        indicators = {
            "RSI_H4": 40.0, "RSI_H1": 40.0, "RSI_M15": 43.0,
            "ADX": 30.0, "ATR": 0.0010,
        }
        # Price rose 0.0020 > 0.0010 (layer 1)
        should, reason = engine.should_dca(cycle, 1.1070, indicators)
        assert should is True

    def test_dca_blocked_sell_price_below(self, engine):
        cycle = _make_cycle(direction="SELL", entry_price=1.1050)
        indicators = {
            "RSI_H4": 40.0, "RSI_H1": 40.0, "RSI_M15": 43.0,
            "ADX": 30.0, "ATR": 0.0010,
        }
        should, reason = engine.should_dca(cycle, 1.1030, indicators)
        assert should is False
