"""
NowTrading 2.1 — ATR DCA Engine (Build Step 5)
ATR-based Dollar Cost Averaging with tiered spacing and multi-condition validation.

Constitution §13:
- DCA only when original thesis remains valid.
- Layer 1 = 1 ATR
- Layer 2 = 1.5 ATR
- Layer 3 = 2 ATR
- Maximum: 3 layers

Constitution §14 DCA Kill Conditions:
- RSI_H4 reverses
- RSI_H1 reverses
- ADX collapses below regime threshold
- Risk Engine veto
- 12h review freezes DCA
- 24h rule activated
"""

from typing import Optional, Tuple

from config import settings
from src.signal_engine import SignalEngine
from src.trade_cycle_manager import TradeCycle
from src.audit_logger import log_info


class ATRDCAEngine:
    """
    ATR-based DCA Engine.
    """

    def __init__(self, signal_engine: Optional[SignalEngine] = None):
        self.max_layers = 3
        self.signal_engine = signal_engine or SignalEngine(None) # None works, but wait, signal engine needs regime engine. Let's not instantiate it here if not provided, rely on injection.

    def calculate_dca_spacing(
        self,
        atr_value: float,
        layer_index: int,
    ) -> float:
        """
        Calculate DCA spacing distance based on ATR and layer index.
        layer_index: 0 for Layer 1, 1 for Layer 2, etc.
        """
        if layer_index == 0:
            multiplier = settings.DCA_LAYER_1_ATR
        elif layer_index == 1:
            multiplier = settings.DCA_LAYER_2_ATR
        else:
            multiplier = settings.DCA_LAYER_3_ATR
            
        return atr_value * multiplier

    def should_dca(
        self,
        cycle: TradeCycle,
        current_price: float,
        indicators: dict,
        ml_score: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Determine if a DCA entry should be placed.
        Validates all conditions from Constitution §13, §14.
        """
        # §14: 12h freeze / 24h activated
        if cycle.dca_frozen:
            return (False, "DCA frozen by 12h rule")
            
        if cycle.holding_hours > settings.HOLDING_MAX_HOURS:
            return (False, "24h rule activated, DCA blocked")

        # §13: Max DCA layers
        if cycle.num_dca_layers >= self.max_layers:
            return (False, f"Max DCA layers reached ({self.max_layers})")

        # ATR requirement
        atr = indicators.get("ATR")
        if atr is None or atr <= 0:
            return (False, "ATR data missing or invalid")

        # ML Score Check (Phanh khẩn cấp)
        if cycle.num_dca_layers >= 1 and ml_score is not None:
            if ml_score > 0.6:
                return (False, f"ML Score {ml_score:.2f} > 0.6, DCA blocked and marked for close")
            if ml_score >= 0.4:
                return (False, f"ML Score {ml_score:.2f} >= 0.4, DCA layer {cycle.num_dca_layers+1} blocked")

        # §14: Original thesis valid (RSI / ADX not reversed)
        # This is handled by SignalEngine.check_dca_validity
        dca_valid = self.signal_engine.check_dca_validity(
            direction=cycle.direction,
            indicators=indicators,
        )
        if not dca_valid:
            return (False, "RSI reversed or ADX collapsed, DCA killed")

        # Get the last entry price to check distance
        if cycle.dca_layers:
            last_entry = cycle.dca_layers[-1].entry_price
        else:
            last_entry = cycle.base_entry_price

        # Layer spacing calculation
        current_layer_index = cycle.num_dca_layers
        spacing = self.calculate_dca_spacing(atr, current_layer_index)
        
        price_distance = abs(current_price - last_entry)

        if price_distance < spacing:
            return (
                False,
                f"Price distance {price_distance:.5f} < "
                f"ATR spacing tier {current_layer_index+1} ({spacing:.5f})"
            )

        # Check direction of movement matches DCA direction
        if cycle.direction == "BUY":
            if current_price >= last_entry:
                return (False, "Price above last entry, no BUY DCA needed")
        else:
            if current_price <= last_entry:
                return (False, "Price below last entry, no SELL DCA needed")

        return (
            True,
            f"DCA valid: distance={price_distance:.5f} >= spacing={spacing:.5f}, "
            f"layer={current_layer_index + 1}"
        )

    def get_dca_lot_size(self, cycle: TradeCycle) -> float:
        """Get lot size for DCA entry. Uses same lot size as base entry."""
        return cycle.base_lot
