from dataclasses import dataclass
from typing import Dict, Any, Literal

@dataclass(frozen=True)
class SignalEvent:
    symbol: str
    action: Literal["BUY", "SELL", "REDUCE", "CLOSE", "HOLD"]
    confidence: float
    reason: str
    risk_hint: dict

class BaseStrategy:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def calculate_indicators(self, data):
        return data

    def on_bar(self, timestamp: str, current_row: Dict[str, Any], position_state: Dict[str, Any]) -> list:
        raise NotImplementedError
