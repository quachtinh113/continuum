from typing import Dict, Any
from v9_continuum.strategies.base_strategy import SignalEvent

def check_entry_signals(current_row: Dict[str, Any], position_state: Dict[str, Any]) -> list:
    """Checks for initial entry (Layer 0) signals when no position is open."""
    if position_state.get("has_open_position", False):
        return []
        
    symbol = current_row["symbol"]
    adx = current_row["adx"]
    rsi = current_row["rsi"]
    
    if adx >= 25:
        if rsi < 30:
            return [SignalEvent(symbol=symbol, action="BUY", confidence=0.85, reason="V9_L0_Oversold_Trend", risk_hint={"layer": 0})]
        elif rsi > 70:
            return [SignalEvent(symbol=symbol, action="SELL", confidence=0.85, reason="V9_L0_Overbought_Trend", risk_hint={"layer": 0})]
            
    return []
