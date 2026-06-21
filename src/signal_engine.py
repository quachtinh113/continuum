"""
NowTrading 2.1 — Signal Engine (Build Step 2)
Evaluates multi-timeframe indicators to generate BUY/SELL/HOLD signals based on Market Regime.

Constitution v2.1:
- BUY: RSI_H4 > 55 AND RSI_H1 > 55 (Trend) -> RSI_M15 > 50 AND Pullback Exhausted.
- SELL: RSI_H4 < 45 AND RSI_H1 < 45 (Trend) -> RSI_M15 < 50 AND Pullback Exhausted.
"""

from enum import Enum
from typing import Optional, Dict, Any

from config import settings
from src.regime_engine import MarketRegime, RegimeEngine


class Signal(Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SignalEngine:
    """
    Signal Engine evaluates indicators and produces trading signals.
    Integrates Regime classification.
    """

    def __init__(self, regime_engine: RegimeEngine):
        self.regime_engine = regime_engine
        self.rsi_buy = settings.RSI_BUY_THRESHOLD
        self.rsi_sell = settings.RSI_SELL_THRESHOLD
        self.rsi_pullback = settings.RSI_PULLBACK_THRESHOLD
        self.strict_pullback = getattr(settings, "STRICT_PULLBACK_EXHAUSTION", True)

    def evaluate(self, indicators: Dict[str, Any]) -> Signal:
        """
        Evaluate indicators and return a trading signal.

        Args:
            indicators: Dict containing RSI_H4, RSI_H1, RSI_M15, ADX, ATR, and pullback booleans.

        Returns:
            Signal.BUY, Signal.SELL, or Signal.HOLD
        """
        rsi_h4 = indicators.get("RSI_H4")
        rsi_h1 = indicators.get("RSI_H1")
        rsi_m15 = indicators.get("RSI_M15")
        adx = indicators.get("ADX")

        # If any core indicator is missing → HOLD (safety)
        if any(v is None for v in [rsi_h4, rsi_h1, rsi_m15, adx]):
            return Signal.HOLD

        # Regime Engine Check
        regime = self.regime_engine.get_regime(adx)
        if not self.regime_engine.can_open_new_trades(regime):
            return Signal.HOLD

        # Pullback variables
        m15_rsi_rising = indicators.get("M15_RSI_RISING", False)
        m15_rsi_falling = indicators.get("M15_RSI_FALLING", False)
        m15_close_rising = indicators.get("M15_CLOSE_RISING", False)
        m15_close_falling = indicators.get("M15_CLOSE_FALLING", False)
        m15_fresh_local_low = indicators.get("M15_FRESH_LOCAL_LOW", True)
        m15_fresh_local_high = indicators.get("M15_FRESH_LOCAL_HIGH", True)

        # ── BUY LOGIC (§5) ──
        bullish_trend = (rsi_h4 > self.rsi_buy) and (rsi_h1 > self.rsi_buy)
        if bullish_trend:
            # Entry Trigger
            trigger = rsi_m15 > self.rsi_pullback
            if self.strict_pullback:
                exhaustion = m15_rsi_rising and m15_close_rising and not m15_fresh_local_low
            else:
                exhaustion = m15_rsi_rising and not m15_fresh_local_low
            
            if trigger and exhaustion:
                return Signal.BUY

        # ── SELL LOGIC (§6) ──
        bearish_trend = (rsi_h4 < self.rsi_sell) and (rsi_h1 < self.rsi_sell)
        if bearish_trend:
            # Entry Trigger
            trigger = rsi_m15 < self.rsi_pullback
            if self.strict_pullback:
                exhaustion = m15_rsi_falling and m15_close_falling and not m15_fresh_local_high
            else:
                exhaustion = m15_rsi_falling and not m15_fresh_local_high
            
            if trigger and exhaustion:
                return Signal.SELL

        return Signal.HOLD

    def check_dca_validity(
        self,
        direction: str,
        indicators: Dict[str, Any],
    ) -> bool:
        """
        Check if DCA is valid for an existing trade direction.

        Constitution §14 DCA Kill Conditions:
        - RSI_H4 reverses
        - RSI_H1 reverses
        - ADX collapses below regime threshold
        """
        rsi_h4 = indicators.get("RSI_H4")
        rsi_h1 = indicators.get("RSI_H1")
        adx = indicators.get("ADX")

        if any(v is None for v in [rsi_h4, rsi_h1, adx]):
            return False

        # ADX collapse check (assuming below RANGE threshold kills it)
        if adx < settings.ADX_RANGE_THRESHOLD:
            return False

        if direction == "BUY":
            # Reversal means going below SELL threshold
            if rsi_h4 < self.rsi_sell or rsi_h1 < self.rsi_sell:
                return False
            return True

        elif direction == "SELL":
            # Reversal means going above BUY threshold
            if rsi_h4 > self.rsi_buy or rsi_h1 > self.rsi_buy:
                return False
            return True

        return False

    def get_signal_reason(
        self,
        signal: Signal,
        indicators: Dict[str, Any],
    ) -> str:
        """Generate a human-readable reason for the signal."""
        rsi_h4 = indicators.get("RSI_H4")
        rsi_h1 = indicators.get("RSI_H1")
        rsi_m15 = indicators.get("RSI_M15")
        adx = indicators.get("ADX")
        
        regime_name = "UNKNOWN"
        if adx is not None:
            regime_name = self.regime_engine.get_regime(adx).value

        if signal == Signal.BUY:
            return (
                f"BUY: RSI H4={rsi_h4:.1f}>55 H1={rsi_h1:.1f}>55 "
                f"M15={rsi_m15:.1f}>50 [Pullback Exhausted] (Regime: {regime_name})"
            )
        elif signal == Signal.SELL:
            return (
                f"SELL: RSI H4={rsi_h4:.1f}<45 H1={rsi_h1:.1f}<45 "
                f"M15={rsi_m15:.1f}<50 [Pullback Exhausted] (Regime: {regime_name})"
            )
        else:
            return f"HOLD: Regime={regime_name} or Pullback not exhausted"
