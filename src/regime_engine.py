"""
NowTrading 2.1 — Regime Engine
Classifies the market into regimes based on ADX.

Constitution §4:
- RANGE: ADX < 18 (Mean Reversion, Reduced risk)
- TRANSITION: 18 <= ADX < 25 (No new entries, Manage existing only)
- TREND: ADX >= 25 (Full strategy enabled)
"""

from enum import Enum
from typing import Optional

from config import settings


class MarketRegime(Enum):
    RANGE = "RANGE"
    TRANSITION = "TRANSITION"
    TREND = "TREND"
    UNKNOWN = "UNKNOWN"


class RegimeEngine:
    """Classifies market regime based on ADX."""

    def __init__(self):
        self.range_threshold = settings.ADX_RANGE_THRESHOLD
        self.trend_threshold = settings.ADX_TREND_THRESHOLD

    def get_regime(self, adx: Optional[float]) -> MarketRegime:
        """
        Determine the market regime based on current ADX value.
        """
        if adx is None:
            return MarketRegime.UNKNOWN

        if adx < self.range_threshold:
            return MarketRegime.RANGE
        elif self.range_threshold <= adx < self.trend_threshold:
            return MarketRegime.TRANSITION
        else:
            return MarketRegime.TREND

    def can_open_new_trades(self, regime: MarketRegime) -> bool:
        """
        Check if the current regime allows opening new trades.
        According to §4, TRANSITION mode disables new entries.
        RANGE allows mean reversion, TREND allows full strategy.
        """
        if regime == MarketRegime.TRANSITION or regime == MarketRegime.UNKNOWN:
            return False
        return True
