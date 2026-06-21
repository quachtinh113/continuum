import time
import math
from typing import Dict, Any, List, Optional, Tuple
from v9_continuum.config import matrix_config


class PortfolioGovernor:
    """
    Centralized Portfolio Risk Governor (Matrix Controller).
    Enforces risk constraints, tokenizes competing signal queues,
    manages news locks, and acts as the global system kill switch.
    """
    def __init__(self):
        self.system_status = "OPERATIONAL"  # OPERATIONAL, LOCKED
        
        # Volatility decay tracking: symbol -> {"spike_atr": float, "spike_time": float, "base_atr": float}
        self._vol_spikes: Dict[str, Dict[str, float]] = {}
        
        # Macro news lock tracking: list of floats (timestamps of macro events)
        self._news_events: List[float] = []

    def is_usd_symbol(self, symbol: str) -> bool:
        """Determines if a symbol is related to the US Dollar."""
        return "USD" in symbol or symbol.startswith("US") or symbol.endswith("USD")

    def is_gold_or_index(self, symbol: str) -> bool:
        """Determines if a symbol is Gold or a stock market index."""
        indices = ["US30", "US100", "US500", "XAUUSD", "DE30"]
        return any(idx in symbol for idx in indices)

    # ── news and Volatility decay ─────────────────────────────────────

    def register_news_event(self, timestamp: float):
        """Registers a macro news event time."""
        self._news_events.append(timestamp)

    def is_news_locked(self, current_time: float) -> Tuple[bool, str]:
        """
        Checks if trade entries are frozen due to a macro news lock window.
        news lock blocks 30 minutes before and after the event.
        """
        lock_window = matrix_config.news_lock_minutes * 60.0
        for event_time in self._news_events:
            diff = abs(current_time - event_time)
            if diff <= lock_window:
                min_remaining = round((lock_window - diff) / 60.0, 1)
                return True, f"Blocked by macro news lock (window expires in {min_remaining}m)"
        return False, "Clear"

    def register_volatility_spike(self, symbol: str, current_atr: float, base_atr: float):
        """Registers a news-driven volatility spike."""
        self._vol_spikes[symbol] = {
            "spike_atr": current_atr,
            "spike_time": time.time(),
            "base_atr": base_atr
        }

    def check_volatility_decay(self, symbol: str, current_atr: float) -> Tuple[bool, str]:
        """
        Exponential Volatility Decay check.
        Formula:
          allowed_atr = base_atr + (spike_atr - base_atr) * e^(-lambda * t)
        If current_atr is below allowed_atr or base_atr, it is considered decayed.
        """
        spike_info = self._vol_spikes.get(symbol)
        if not spike_info:
            return True, "No registered volatility spike"

        elapsed_seconds = time.time() - spike_info["spike_time"]
        decay_rate = 0.005  # lambda parameter
        
        # Block immediately if the spike occurred less than 5 seconds ago
        if elapsed_seconds < 5.0:
            return False, f"Blocked by Volatility Decay Engine: spike is too fresh ({round(elapsed_seconds, 1)}s elapsed)"
            
        allowed_atr = spike_info["base_atr"] + (spike_info["spike_atr"] - spike_info["base_atr"]) * math.exp(-decay_rate * elapsed_seconds)
        
        # If volatility has returned to base levels or decayed below target, clear it
        if current_atr <= spike_info["base_atr"] or current_atr <= allowed_atr:
            self._vol_spikes.pop(symbol, None)
            return True, "Volatility decayed to safe levels"
            
        remaining_vol = round(current_atr - allowed_atr, 5)
        return False, f"Blocked by Volatility Decay Engine (waiting decay of {remaining_vol} ATR)"

    # ── Central Constraints & Kill Switch ─────────────────────────────

    def evaluate_risk_matrix(
        self,
        symbol: str,
        active_positions: List[Dict[str, Any]],
        current_equity: float,
        start_of_day_balance: float,
        current_time: float
    ) -> Tuple[bool, str]:
        """
        Validates global portfolio bounds and triggers emergency Kill Switches.
        """
        if self.system_status == "LOCKED":
            return False, "System status is LOCKED by global drawdown limit"

        # 1. Global Drawdown Kill Switch
        if start_of_day_balance > 0.0:
            drawdown = 100.0 * (start_of_day_balance - current_equity) / start_of_day_balance
            if drawdown >= matrix_config.max_daily_drawdown_percent:
                self.system_status = "LOCKED"
                return False, f"KILL SWITCH TRIGGERED: Drawdown of {drawdown:.2f}% >= {matrix_config.max_daily_drawdown_percent}%"

        # 2. Maximum parallel position count
        unique_active_symbols = len(set(pos["symbol"] for pos in active_positions))
        if unique_active_symbols >= matrix_config.max_open_positions:
            return False, f"Constraint Violated: Max parallel positions count ({matrix_config.max_open_positions}) reached"

        # 3. Macro news lock filter
        news_locked, reason = self.is_news_locked(current_time)
        if news_locked:
            return False, reason

        # 4. USD Exposure factor limit
        if self.is_usd_symbol(symbol):
            usd_active_count = sum(1 for pos in active_positions if self.is_usd_symbol(pos["symbol"]))
            if usd_active_count >= matrix_config.max_usd_exposure:
                return False, f"USD factor concentration exceeded limit ({matrix_config.max_usd_exposure})"

        # 5. Gold & Index combo limit
        if self.is_gold_or_index(symbol):
            gold_index_active = sum(1 for pos in active_positions if self.is_gold_or_index(pos["symbol"]))
            if gold_index_active >= matrix_config.max_gold_index_combo:
                return False, f"Gold & Index combination limit ({matrix_config.max_gold_index_combo}) exceeded"

        return True, "Approved"

    # ── Async Token Queue Window ──────────────────────────────────────

    def process_token_queue(self, tokens: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Async Token Queue Window (100-200ms).
        Processes simultaneous entry signals, scoring candidates by:
          Score = (ADX * 0.7) - (Spread * 0.3)
        Returns the winning token or None.
        """
        if not tokens:
            return None

        scored_tokens = []
        for token in tokens:
            adx = token.get("adx", 0.0)
            spread = token.get("spread", 0.0)
            
            # Institutional priority scoring formula
            score = (adx * 0.7) - (spread * 0.3)
            scored_tokens.append((score, token))

        # Sort descending by score
        scored_tokens.sort(key=lambda x: x[0], reverse=True)
        winner_score, winner_token = scored_tokens[0]
        
        winner_token["governor_score"] = winner_score
        return winner_token
