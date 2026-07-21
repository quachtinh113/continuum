from typing import Dict, Any
from v9_continuum.strategies.base_strategy import BaseStrategy, SignalEvent
from v9_continuum.strategies.signal_rules import check_entry_signals
from v9_continuum.strategies.exit_rules import evaluate_exit_and_dca

class HybridDcaV9(BaseStrategy):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

    def calculate_indicators(self, data):
        return data

    def on_bar(self, timestamp: str, current_row: Dict[str, Any], position_state: Dict[str, Any]) -> list:
        # 1. Evaluate Entry L0 signals
        entry_signals = check_entry_signals(current_row, position_state)
        if entry_signals:
            return entry_signals

        # 2. Evaluate DCA/Exit management rules
        management_signals = evaluate_exit_and_dca(current_row, position_state, self.config)
        if management_signals:
            return management_signals

        return [SignalEvent(symbol=current_row["symbol"], action="HOLD", confidence=1.0, reason="V9_Market_Observation", risk_hint={})]
