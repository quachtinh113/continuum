import pytest
from v9_continuum.strategies.hybrid_dca_v9 import HybridDcaV9

def test_entry_signals():
    config = {"max_layers": 3, "dca_multiplier": 2.3, "take_profit_pct": 0.015, "recovery_threshold_pct": 0.05}
    strategy = HybridDcaV9(config)
    
    current_row = {"symbol": "XAUUSD", "adx": 30.0, "rsi": 20.0, "close": 2000.0, "atr": 10.0}
    position_state = {"has_open_position": False}
    
    signals = strategy.on_bar("2026-06-30T12:00:00", current_row, position_state)
    assert len(signals) == 1
    assert signals[0].action == "BUY"
    assert signals[0].reason == "V9_L0_Oversold_Trend"

def test_dca_spacing():
    config = {"max_layers": 3, "dca_multiplier": 2.3, "take_profit_pct": 0.015, "recovery_threshold_pct": 0.05}
    strategy = HybridDcaV9(config)
    
    # Required spacing: 10.0 * 2.3 = 23.0. Price drops to (2000 - 23) = 1977
    current_row = {"symbol": "XAUUSD", "adx": 15.0, "rsi": 50.0, "close": 1976.0, "atr": 10.0}
    position_state = {
        "has_open_position": True,
        "avg_price": 2000.0,
        "position_type": "LONG",
        "current_layer": 0,
        "unrealized_pnl_pct": -0.01
    }
    
    signals = strategy.on_bar("2026-06-30T12:00:00", current_row, position_state)
    assert len(signals) == 1
    assert signals[0].action == "BUY"
    assert "V9_DCA_Layer_1" in signals[0].reason
