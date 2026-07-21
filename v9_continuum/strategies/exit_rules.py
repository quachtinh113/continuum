from typing import Dict, Any
from v9_continuum.strategies.base_strategy import SignalEvent

def evaluate_exit_and_dca(current_row: Dict[str, Any], position_state: Dict[str, Any], config: Dict[str, Any]) -> list:
    """Manages active trades: calculates DCA layers (369) and early recovery/take-profit (505)."""
    if not position_state.get("has_open_position", False):
        return []

    symbol = current_row["symbol"]
    current_price = current_row["close"]
    atr = current_row["atr"]
    
    avg_price = position_state["avg_price"]
    position_type = position_state["position_type"]
    current_layer = position_state["current_layer"]
    max_layers = config["max_layers"]
    
    dca_spacing = atr * config["dca_multiplier"]
    
    # 369 Cashflow Spacing Checks
    if current_layer < max_layers:
        if position_type == "LONG" and current_price <= (avg_price - dca_spacing):
            return [SignalEvent(symbol=symbol, action="BUY", confidence=0.9, reason=f"V9_DCA_Layer_{current_layer+1}", risk_hint={"layer": current_layer + 1})]
        elif position_type == "SHORT" and current_price >= (avg_price + dca_spacing):
            return [SignalEvent(symbol=symbol, action="SELL", confidence=0.9, reason=f"V9_DCA_Layer_{current_layer+1}", risk_hint={"layer": current_layer + 1})]

    # 505 Recovery/Drawdown and Profit Targets
    pnl_percentage = position_state["unrealized_pnl_pct"]
    if pnl_percentage <= -config["recovery_threshold_pct"]:
        return [SignalEvent(symbol=symbol, action="REDUCE", confidence=1.0, reason="V9_505_Recovery_Trigger", risk_hint={"reduce_size_pct": 50.0})]
        
    if pnl_percentage >= config["take_profit_pct"]:
        return [SignalEvent(symbol=symbol, action="CLOSE", confidence=1.0, reason="V9_369_Target_Achieved", risk_hint={})]

    return []
