"""
NowTrading 2.1 — Trade Cycle Manager (Build Step 4)
Manages trade cycle lifecycle: open, update, close, with time-based rules.

Constitution §5:
- Profit Rule: holding > 1h AND profit > $5 → close
- 12-Hour Rule: holding > 12h AND no profit → reduce/cut using ADX/ATR
- 24-Hour Rule: holding > 24h AND no profit → force close all
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
from enum import Enum

from config import settings
from src.audit_logger import log_cycle_event, log_info


class CycleStatus(Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    REDUCING = "REDUCING"


@dataclass
class DCALayer:
    """Represents one DCA entry within a trade cycle."""
    entry_price: float
    lot_size: float
    entry_time: datetime
    ticket: int  # MT5 order ticket (-1 for dry run)


@dataclass
class TradeCycle:
    """
    A trade cycle represents a complete trading position
    including initial entry and any DCA layers.
    """
    symbol: str
    direction: str              # "BUY" or "SELL"
    entry_time: datetime
    session: str
    base_entry_price: float
    current_profit_usd: float = 0.0
    dca_layers: List[DCALayer] = field(default_factory=list)
    holding_hours: float = 0.0
    tickets: List[int] = field(default_factory=list)
    status: CycleStatus = CycleStatus.ACTIVE
    close_reason: str = ""
    dca_frozen: bool = False
    ml_features: Optional[Dict[str, float]] = None
    ml_score: Optional[float] = None
    be_activated: bool = False
    base_lot: float = 0.01


    @property
    def total_lots(self) -> float:
        """Total lots across all entries including DCA."""
        dca_lots = sum(layer.lot_size for layer in self.dca_layers)
        return self.base_lot + dca_lots

    @property
    def num_dca_layers(self) -> int:
        return len(self.dca_layers)

    @property
    def average_entry_price(self) -> float:
        """Weighted average entry price across all layers."""
        total_cost = self.base_entry_price * self.base_lot
        total_lots = self.base_lot

        for layer in self.dca_layers:
            total_cost += layer.entry_price * layer.lot_size
            total_lots += layer.lot_size

        return total_cost / total_lots if total_lots > 0 else self.base_entry_price


class TradeCycleManager:
    """
    Manages all active trade cycles and applies time-based rules.
    """

    def __init__(self):
        # Active cycles: symbol → TradeCycle
        self._active_cycles: Dict[str, TradeCycle] = {}
        # History of closed cycles
        self._closed_cycles: List[TradeCycle] = []

    # ── Cycle CRUD ──────────────────────────────────────────

    def open_cycle(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        session: str,
        ticket: int,
        entry_time: Optional[datetime] = None,
        ml_features: Optional[Dict[str, float]] = None,
        base_lot: Optional[float] = None,
    ) -> Optional[TradeCycle]:
        """
        Open a new trade cycle for a symbol.
        Returns the newly created TradeCycle or None if symbol already has active cycle.
        """
        if symbol in self._active_cycles:
            log_info(f"Cannot open cycle: {symbol} already has active cycle")
            return None
        if entry_time is None:
            entry_time = datetime.now(timezone.utc)
        if base_lot is None:
            from config.symbols import get_symbol_spec
            spec = get_symbol_spec(symbol)
            if spec.category == "FX":
                base_lot = settings.FX_BASE_LOT
            elif spec.category in ["GOLD", "COMMODITY"]:
                base_lot = settings.COMMODITY_BASE_LOT
            elif spec.category == "CRYPTO":
                base_lot = settings.CRYPTO_BASE_LOT
            else:
                base_lot = settings.MAX_LOT_SIZE

        cycle = TradeCycle(
            symbol=symbol,
            direction=direction,
            entry_time=entry_time,
            session=session,
            base_entry_price=entry_price,
            tickets=[ticket],
            ml_features=ml_features,
            base_lot=base_lot,
        )
        self._active_cycles[symbol] = cycle

        log_cycle_event(
            event="CYCLE_OPEN",
            symbol=symbol,
            direction=direction,
            details={
                "entry_price": entry_price,
                "session": session,
                "ticket": ticket,
                "lot_size": base_lot,
            },
        )

        return cycle

    def get_cycle(self, symbol: str) -> Optional[TradeCycle]:
        """Get active cycle for a symbol."""
        return self._active_cycles.get(symbol)

    def has_active_cycle(self, symbol: str) -> bool:
        """Check if symbol has an active cycle."""
        return symbol in self._active_cycles

    def get_all_active_cycles(self) -> Dict[str, TradeCycle]:
        """Get all active cycles."""
        return dict(self._active_cycles)

    def get_active_cycle_count(self) -> int:
        """Get number of active cycles."""
        return len(self._active_cycles)

    # ── Cycle Update ────────────────────────────────────────

    def update_cycle(
        self,
        symbol: str,
        current_price: float,
        current_time: Optional[datetime] = None,
    ) -> Optional[TradeCycle]:
        """
        Update a cycle's profit and holding time.

        Args:
            symbol: Symbol key
            current_price: Current market price
            current_time: Current UTC time (defaults to now)

        Returns:
            Updated TradeCycle or None if no active cycle.
        """
        cycle = self._active_cycles.get(symbol)
        if cycle is None:
            return None

        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Update holding hours
        elapsed = current_time - cycle.entry_time
        cycle.holding_hours = elapsed.total_seconds() / 3600.0

        # Calculate P&L (simplified — real P&L comes from MT5 positions)
        avg_price = cycle.average_entry_price
        total_lots = cycle.total_lots

        if cycle.direction == "BUY":
            price_diff = current_price - avg_price
        else:
            price_diff = avg_price - current_price

        # Simplified profit estimation (actual profit tracked by MT5)
        # This uses pip value estimation
        from config.symbols import get_symbol_spec
        spec = get_symbol_spec(symbol)
        cycle.current_profit_usd = price_diff * total_lots * spec.contract_size

        return cycle

    # ── Time-Based Rules ────────────────────────────────────

    def check_profit_rule(
        self, 
        symbol: str, 
        atr: Optional[float] = None, 
        current_price: Optional[float] = None
    ) -> Optional[str]:
        """
        Constitution §5 Profit Rule:
        If holding > 1h AND profit > dynamic target → close.

        Returns:
            "CLOSE_PROFIT" if rule triggered, None otherwise.
        """
        cycle = self._active_cycles.get(symbol)
        if cycle is None:
            return None

        target_usd = settings.PROFIT_TARGET_USD
        if atr is not None and atr > 0 and current_price is not None:
            from config.symbols import get_symbol_spec
            spec = get_symbol_spec(symbol)
            profit_quote_ccy = (atr * settings.TAKE_PROFIT_ATR_MULTIPLIER) * cycle.total_lots * spec.contract_size
            if symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD"):
                target_usd = profit_quote_ccy / current_price
            else:
                target_usd = profit_quote_ccy

        if (
            cycle.holding_hours > 1.0
            and cycle.current_profit_usd > target_usd
        ):
            return "CLOSE_PROFIT"

        return None

    def get_dynamic_ml_threshold(self, current_layer: int) -> float:
        """
        Get dynamic ML veto threshold based on the active DCA layer.
        As the grid deepens, the safety tolerance decreases (threshold decreases).
        """
        if current_layer == 0:
            return getattr(settings, "ML_VETO_THRESHOLD_L0", 0.75)
        elif current_layer == 1:
            return getattr(settings, "ML_VETO_THRESHOLD_L1", 0.68)
        elif current_layer == 2:
            return getattr(settings, "ML_VETO_THRESHOLD_L2", 0.58)
        else:
            return getattr(settings, "ML_VETO_THRESHOLD_L3", 0.50)

    def check_ml_veto(self, symbol: str, ml_score: Optional[float] = None) -> Optional[str]:
        """
        ML Veto Rule:
        If ML Score > dynamic threshold at any point, force close the trade immediately.
        """
        if ml_score is None:
            return None
            
        cycle = self._active_cycles.get(symbol)
        if cycle is None:
            return None
            
        threshold = self.get_dynamic_ml_threshold(cycle.num_dca_layers)
        if ml_score > threshold:
            return "ML_VETO_CLOSE"
            
        return None

    def check_break_even(
        self,
        symbol: str,
        current_price: float,
        atr: Optional[float] = None,
        minor_liquidity_swept: bool = False
    ) -> Optional[str]:
        """
        Check and apply Break-Even (BE) activation logic:
        1. If price reaches the activation distance (based on ATR) or minor liquidity is swept, activate BE.
        2. Once BE is activated, if price pulls back to average entry price plus/minus
           the dynamic buffer (based on ATR), close the cycle.
        """
        cycle = self._active_cycles.get(symbol)
        if cycle is None:
            return None

        if atr is None or atr <= 0:
            return None

        avg_price = cycle.average_entry_price
        
        activation_mult = getattr(settings, "BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER", 1.5)
        buffer_mult = getattr(settings, "BREAK_EVEN_BUFFER_ATR_MULTIPLIER", 0.0)
        
        activation_distance = atr * activation_mult
        buffer_distance = atr * buffer_mult

        if activation_mult < 900.0:
            if cycle.direction == "BUY":
                # Check for BE activation (price reached activation distance or minor liquidity swept)
                if not cycle.be_activated and (current_price >= avg_price + activation_distance or minor_liquidity_swept):
                    cycle.be_activated = True
                    log_info(f"🛡️ BE Activated for BUY {symbol} (Price {current_price:.5f} >= {avg_price + activation_distance:.5f} or Liq Swept)")

                # Check for BE exit (pullback to average entry + buffer distance or below)
                if cycle.be_activated and current_price <= avg_price + buffer_distance:
                    return "BREAK_EVEN"

            elif cycle.direction == "SELL":
                # Check for BE activation (price reached activation distance or minor liquidity swept)
                if not cycle.be_activated and (current_price <= avg_price - activation_distance or minor_liquidity_swept):
                    cycle.be_activated = True
                    log_info(f"🛡️ BE Activated for SELL {symbol} (Price {current_price:.5f} <= {avg_price - activation_distance:.5f} or Liq Swept)")

                # Check for BE exit (pullback to average entry - buffer distance or above)
                if cycle.be_activated and current_price >= avg_price - buffer_distance:
                    return "BREAK_EVEN"

        return None


    def check_hard_stop_rule(
        self, 
        symbol: str, 
        atr: Optional[float] = None, 
        current_price: Optional[float] = None
    ) -> Optional[str]:
        """
        Hard-Stop on Expectancy Rule (R:R = 1.5x):
        Max loss = 1.5 * expected profit. Expected profit is based on current total_lots.
        """
        if atr is None or atr <= 0 or current_price is None:
            return None
            
        cycle = self._active_cycles.get(symbol)
        if cycle is None:
            return None

        from config.symbols import get_symbol_spec
        spec = get_symbol_spec(symbol)
        
        # Expected profit = (ATR * multiplier) * total_lots * contract_size
        profit_quote_ccy = (atr * settings.TAKE_PROFIT_ATR_MULTIPLIER) * cycle.total_lots * spec.contract_size
        
        if symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD"):
            expected_profit_usd = profit_quote_ccy / current_price
        else:
            expected_profit_usd = profit_quote_ccy
            
        max_loss_usd = 1.5 * expected_profit_usd
        
        if cycle.current_profit_usd < -max_loss_usd:
            return "FORCE_CLOSE_RR_LIMIT"
            
        return None

    def check_12h_rule(
        self,
        symbol: str,
        current_price: float,
        adx: Optional[float] = None,
        atr: Optional[float] = None,
        ml_score: Optional[float] = None,
    ) -> Optional[str]:
        """
        Constitution §5 12-Hour Rule:
        If holding > 12h AND no profit → check ATR range.
        If price is within ATR range, continue to hold. Otherwise reduce/cut.
        """
        cycle = self._active_cycles.get(symbol)
        if cycle is None:
            return None

        if cycle.holding_hours <= settings.HOLDING_REDUCE_HOURS:
            return None

        if cycle.current_profit_usd > 0:
            return None  # Has profit, no action needed

        # ATR_ADAPTIVE_DCA_CHECK
        if atr is not None and atr > 0:
            distance = abs(current_price - cycle.average_entry_price)
            threshold = settings.ATR_DCA_CHECK_MULTIPLIER * atr
            if distance <= threshold:
                # Normal consolidation, keep holding
                return None
            
        # Outside ATR range: freeze DCA
        if not cycle.dca_frozen:
            cycle.dca_frozen = True
            log_info(f"12-Hour Rule │ Price out of ATR range. Freezing DCA for {symbol}")

        # ── ML Exit Control ──
        if ml_score is not None:
            if ml_score > settings.ML_VETO_THRESHOLD:
                log_info(f"12-Hour Rule │ ML Score {ml_score:.4f} > {settings.ML_VETO_THRESHOLD}. Forcing CUT_ALL.")
                return "CUT_ALL"
            else:
                # ML says it's relatively safe to keep holding
                return None

        # ── Fallback Decision: reduce or cut based on ADX ──
        if adx is not None and adx > settings.ADX_TREND_THRESHOLD:
            # Trend still strong — just reduce worst DCA layer (Partial Exit)
            if cycle.num_dca_layers > 0:
                return "REDUCE_DCA"
            else:
                return "CUT_ALL"
        else:
            # Trend weak or no ADX data — cut everything
            return "CUT_ALL"

    def check_conditional_force_close(
        self,
        symbol: str,
        current_price: float,
        adx: Optional[float] = None,
        rsi_h4: Optional[float] = None,
        rsi_h1: Optional[float] = None,
    ) -> Optional[str]:
        """
        Constitution §5 Conditional Force Close Rule (REGIME_FILTER_EXIT):
        If no profit:
        - Only close if trend reversed (ADX > 25 & H1/H4 RSI opposite)
        - Or H1 RSI is overextended against position.
        """
        cycle = self._active_cycles.get(symbol)
        if cycle is None:
            return None

        if cycle.current_profit_usd > 0:
            return None

        # REGIME_FILTER_EXIT
        trend_reversed = False
        if adx is not None and adx >= settings.ADX_TREND_THRESHOLD:
            if cycle.direction == "BUY":
                # Reversed means trend is bearish
                trend_reversed = (
                    rsi_h4 is not None and rsi_h4 < settings.RSI_SELL_THRESHOLD
                    and rsi_h1 is not None and rsi_h1 < settings.RSI_SELL_THRESHOLD
                )
            else:
                # Reversed means trend is bullish
                trend_reversed = (
                    rsi_h4 is not None and rsi_h4 > settings.RSI_BUY_THRESHOLD
                    and rsi_h1 is not None and rsi_h1 > settings.RSI_BUY_THRESHOLD
                )

        if trend_reversed:
            return "FORCE_CLOSE"

        # Overextended check
        overextended = False
        if rsi_h1 is not None:
            if cycle.direction == "BUY":
                overextended = rsi_h1 < settings.RSI_OVEREXTENDED_LOW
            else:
                overextended = rsi_h1 > settings.RSI_OVEREXTENDED_HIGH

        if overextended:
            return "FORCE_CLOSE"

        # Otherwise, sideways/no trend reversal, continue to hold
        return None

    # ── Cycle Close ─────────────────────────────────────────

    def close_cycle(
        self,
        symbol: str,
        reason: str,
    ) -> Optional[TradeCycle]:
        """
        Close a trade cycle and move to history.

        Args:
            symbol: Symbol key
            reason: Close reason (e.g. "PROFIT_TARGET", "24H_RULE")

        Returns:
            Closed TradeCycle or None if not found.
        """
        cycle = self._active_cycles.pop(symbol, None)
        if cycle is None:
            return None

        cycle.status = CycleStatus.CLOSED
        cycle.close_reason = reason
        self._closed_cycles.append(cycle)

        log_cycle_event(
            event="CYCLE_CLOSE",
            symbol=symbol,
            direction=cycle.direction,
            details={
                "reason": reason,
                "holding_hours": round(cycle.holding_hours, 2),
                "profit_usd": round(cycle.current_profit_usd, 2),
                "total_lots": cycle.total_lots,
                "dca_layers": cycle.num_dca_layers,
                "avg_entry": round(cycle.average_entry_price, 5),
            },
        )

        return cycle

    def remove_worst_dca(self, symbol: str) -> Optional[DCALayer]:
        """
        Remove the worst-performing DCA layer (for 12h reduce rule).

        Returns:
            Removed DCALayer or None.
        """
        cycle = self._active_cycles.get(symbol)
        if cycle is None or not cycle.dca_layers:
            return None

        # Find worst DCA layer (furthest from current profitable direction)
        # For BUY: highest entry price is worst
        # For SELL: lowest entry price is worst
        if cycle.direction == "BUY":
            worst_idx = max(range(len(cycle.dca_layers)),
                           key=lambda i: cycle.dca_layers[i].entry_price)
        else:
            worst_idx = min(range(len(cycle.dca_layers)),
                           key=lambda i: cycle.dca_layers[i].entry_price)

        worst = cycle.dca_layers.pop(worst_idx)

        # Remove ticket
        if worst.ticket in cycle.tickets:
            cycle.tickets.remove(worst.ticket)

        log_cycle_event(
            event="DCA_REMOVE",
            symbol=symbol,
            direction=cycle.direction,
            details={
                "removed_price": worst.entry_price,
                "removed_ticket": worst.ticket,
                "remaining_layers": cycle.num_dca_layers,
            },
        )

        return worst

    def add_dca_layer(
        self,
        symbol: str,
        entry_price: float,
        lot_size: float,
        ticket: int,
        entry_time: Optional[datetime] = None,
    ) -> bool:
        """
        Add a DCA layer to an existing cycle.

        Returns:
            True if added successfully.
        """
        cycle = self._active_cycles.get(symbol)
        if cycle is None:
            return False
            
        if cycle.dca_frozen:
            log_info(f"Cannot add DCA for {symbol}: DCA is frozen by 12h rule.")
            return False

        if entry_time is None:
            entry_time = datetime.now(timezone.utc)

        layer = DCALayer(
            entry_price=entry_price,
            lot_size=lot_size,
            entry_time=entry_time,
            ticket=ticket,
        )

        cycle.dca_layers.append(layer)
        cycle.tickets.append(ticket)

        log_cycle_event(
            event="DCA_ADD",
            symbol=symbol,
            direction=cycle.direction,
            details={
                "dca_price": entry_price,
                "dca_lot": lot_size,
                "ticket": ticket,
                "total_layers": cycle.num_dca_layers,
                "avg_entry": round(cycle.average_entry_price, 5),
            },
        )

        return True

    # ── Queries ─────────────────────────────────────────────

    def get_closed_cycles(self) -> List[TradeCycle]:
        """Get all closed cycles."""
        return list(self._closed_cycles)

    def get_daily_closed_profit(self) -> float:
        """Get total profit from today's closed cycles."""
        today = datetime.now(timezone.utc).date()
        return sum(
            c.current_profit_usd
            for c in self._closed_cycles
            if c.entry_time.date() == today
        )
