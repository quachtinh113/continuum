"""
Edge case tests for NowTrading 2.1.
Verifies logic compatibility between MAX_LOT_SIZE and cumulative DCA exposure.
"""

import pytest
from datetime import datetime, timezone
from config import settings
from src.trade_cycle_manager import TradeCycleManager
from src.atr_dca_engine import ATRDCAEngine
from src.risk_engine import RiskEngine
from src.hourly_gate import HourlyGate
from src.portfolio_engine import PortfolioEngine


@pytest.fixture
def clean_settings():
    """Reset settings to target values."""
    prev_fx = settings.FX_BASE_LOT
    prev_max = settings.MAX_LOT_SIZE
    
    settings.FX_BASE_LOT = 0.02
    settings.MAX_LOT_SIZE = 0.10
    
    yield
    
    settings.FX_BASE_LOT = prev_fx
    settings.MAX_LOT_SIZE = prev_max


def test_dca_exposure_ceiling_over_max_lot(clean_settings):
    """
    Verify that the TradeCycle's base lot is correctly recorded and
    that cumulative DCA exposure is allowed to exceed MAX_LOT_SIZE (0.10)
    without being capped or vetoed by the risk engine.
    """
    cycle_manager = TradeCycleManager()
    hourly_gate = HourlyGate()
    portfolio_engine = PortfolioEngine(cycle_manager)
    risk_engine = RiskEngine(cycle_manager, hourly_gate, portfolio_engine)
    dca_engine = ATRDCAEngine()

    # 1. Open the trade cycle with the correct FX base lot
    # Simulate what main.py does: calculate dynamic lot (which caps at MAX_LOT_SIZE = 0.10)
    symbol = "EURUSD"
    direction = "BUY"
    entry_price = 1.1000
    
    # In live trading, main.py calculates lot_size (0.02)
    lot_size = risk_engine.get_dynamic_lot_size(
        base_lot=settings.FX_BASE_LOT,
        balance=1015.23,
        equity=1015.23,
        symbol=symbol,
    )
    
    assert lot_size == 0.02
    
    # Open the cycle passing the base_lot
    cycle = cycle_manager.open_cycle(
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        session="EUROPE",
        ticket=1001,
        entry_time=datetime.now(timezone.utc),
        base_lot=lot_size,
    )
    
    assert cycle is not None
    assert cycle.base_lot == 0.02  # Crucial: Must be 0.02, NOT defaulted to MAX_LOT_SIZE (0.10)

    # 2. Simulate DCA Layers being added
    # Layer 1
    dca_lot_1 = dca_engine.get_dca_lot_size(cycle)
    assert dca_lot_1 == 0.02
    cycle_manager.add_dca_layer(symbol, 1.0950, dca_lot_1, 1002)
    
    # Layer 2
    dca_lot_2 = dca_engine.get_dca_lot_size(cycle)
    assert dca_lot_2 == 0.02
    cycle_manager.add_dca_layer(symbol, 1.0900, dca_lot_2, 1003)
    
    # At this point: Base (0.02) + Layer 1 (0.02) + Layer 2 (0.02) = 0.06 lot.
    # Suppose our strategy decides to add Layer 3 with a larger lot (e.g. 0.04 or 0.08)
    # The cumulative exposure will go to 0.10 or 0.14.
    dca_lot_3 = 0.06
    
    # Risk check for adding DCA
    risk_decision = risk_engine.can_dca(
        symbol=symbol,
        indicators={"RSI_H4": 60, "RSI_H1": 50, "RSI_M15": 40, "ADX": 30, "ATR": 0.0015},
        spread_pips=1.5,
        data_age_seconds=10,
    )
    
    assert risk_decision.approved is True
    
    # Add Layer 3
    success = cycle_manager.add_dca_layer(symbol, 1.0850, dca_lot_3, 1004)
    assert success is True
    
    # Total exposure must be 0.12, which exceeds settings.MAX_LOT_SIZE (0.10)
    assert round(cycle.total_lots, 4) == 0.12
    assert cycle.total_lots > settings.MAX_LOT_SIZE
