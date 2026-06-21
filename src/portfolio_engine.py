"""
NowTrading 2.1 — Portfolio Engine
Manages Portfolio Governance and correlated exposure limits.

Constitution §17:
- Maximum correlated exposure allowed.
- e.g. EURUSD BUY + GBPUSD BUY + AUDUSD BUY = 3x USD short exposure.
- Portfolio risk limits override symbol signals.
"""

from typing import Dict
from src.trade_cycle_manager import TradeCycleManager


class PortfolioEngine:
    """Manages overall portfolio exposure and correlation risk."""

    MAX_EXPOSURE = 3  # Maximum allowed exposure in a single direction for a currency/asset

    def __init__(self, cycle_manager: TradeCycleManager):
        self.cycle_manager = cycle_manager

    def can_open_trade(self, symbol: str, direction: str) -> tuple[bool, str]:
        """
        Check if opening this trade violates portfolio exposure limits.
        
        Args:
            symbol: e.g. "EURUSD"
            direction: "BUY" or "SELL"
            
        Returns:
            (approved: bool, reason: str)
        """
        active_cycles = self.cycle_manager.get_all_active_cycles()
        
        # 1. Hard cap check
        from config import settings
        if len(active_cycles) >= settings.MAX_ACTIVE_CYCLES:
            return False, f"Portfolio limit: {len(active_cycles)} >= {settings.MAX_ACTIVE_CYCLES} max cycles"
        
        # Calculate current exposures
        exposures: Dict[str, int] = {}
        
        for cycle in active_cycles.values():
            self._add_cycle_exposure(cycle.symbol, cycle.direction, exposures)
            
        # Simulate adding the new trade
        simulated_exposures = exposures.copy()
        self._add_cycle_exposure(symbol, direction, simulated_exposures)
        
        # Check if limits are exceeded
        for asset, exposure in simulated_exposures.items():
            if abs(exposure) > self.MAX_EXPOSURE:
                direction_str = "LONG" if exposure > 0 else "SHORT"
                return False, f"Portfolio limit exceeded: {abs(exposure)}x {asset} {direction_str} exposure"
                
        return True, "Portfolio exposure OK"

    def _add_cycle_exposure(self, symbol: str, direction: str, exposures: Dict[str, int]):
        """
        Parse symbol and add its directional exposure to the tracking dict.
        Exposures are represented as positive (LONG) or negative (SHORT).
        """
        multiplier = 1 if direction == "BUY" else -1
        
        # Clean symbol suffix if it exists (e.g. EURUSDm -> EURUSD)
        clean_symbol = symbol.replace("m", "")
        
        # FX Pairs (XXXUSD, USDXXX)
        if len(clean_symbol) == 6 and clean_symbol.endswith("USD"):
            base = clean_symbol[:3]
            quote = "USD"
            # e.g. EURUSD BUY -> +1 EUR, -1 USD
            exposures[base] = exposures.get(base, 0) + multiplier
            exposures[quote] = exposures.get(quote, 0) - multiplier
            
        elif len(clean_symbol) == 6 and clean_symbol.startswith("USD"):
            base = "USD"
            quote = clean_symbol[3:]
            # e.g. USDJPY BUY -> +1 USD, -1 JPY
            exposures[base] = exposures.get(base, 0) + multiplier
            exposures[quote] = exposures.get(quote, 0) - multiplier
            
        # Indices (US30, US100, US500)
        elif clean_symbol in ["US30", "US100", "US500", "USTEC"]:
            asset_class = "US_INDEX"
            exposures[asset_class] = exposures.get(asset_class, 0) + multiplier
            
        # Metals / Crypto
        elif clean_symbol == "XAUUSD":
            exposures["XAU"] = exposures.get("XAU", 0) + multiplier
            exposures["USD"] = exposures.get("USD", 0) - multiplier
            
        elif clean_symbol == "BTCUSD":
            exposures["BTC"] = exposures.get("BTC", 0) + multiplier
            exposures["USD"] = exposures.get("USD", 0) - multiplier
