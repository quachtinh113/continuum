import time
from typing import Optional, Dict, Any, List, Tuple
from src.mt5_connector import MT5Connector, MT5_AVAILABLE
from config.symbols import get_mt5_name, get_symbol_spec

if MT5_AVAILABLE:
    import MetaTrader5 as mt5
else:
    mt5 = None


class ExecutionEngine:
    """
    Handles trade routing, commission calculations, spread auditing,
    and broker lot-size boundary normalization.
    """
    def __init__(self, connector: MT5Connector):
        self.connector = connector
        self._dry_run = not self.connector._dry_run if hasattr(self.connector, "_dry_run") else False
        self.execution_history: List[Dict[str, Any]] = []
        self.circuit_breaker_tripped: bool = False
        self.max_allowed_slippage_pips: float = 0.30

    def normalize_lot(self, symbol: str, lot: float) -> float:
        """
        Retrieves volume constraints from the broker and normalizes lot size.
        Eliminates MT5 error Retcode 10014 (Invalid Volume).
        """
        if not MT5_AVAILABLE or mt5 is None:
            # Stand-in normalization based on standard sizes
            return round(max(0.01, lot), 2)

        mt5_symbol = get_mt5_name(symbol)
        info = mt5.symbol_info(mt5_symbol)
        if info is None:
            return round(max(0.01, lot), 2)

        vol_min = info.volume_min
        vol_step = info.volume_step
        vol_max = info.volume_max

        # Normalization to step
        step_precision = len(str(vol_step).split(".")[1]) if "." in str(vol_step) else 0
        normalized = round(round(lot / vol_step) * vol_step, step_precision)
        normalized = max(vol_min, min(vol_max, normalized))

        return float(normalized)

    def get_realtime_costs(self, symbol: str, lot: float, spread_pips: float) -> Tuple[float, float]:
        """
        Calculates spread cost and estimated commission for a transaction.
        Formula:
          Spread Cost = Spread Pips * Pip Value * Lots
          Commission = Configured base commission per lot (e.g. $7.0 per lot round-turn for Raw Spread)
        Returns: (spread_cost_usd, commission_usd)
        """
        spec = get_symbol_spec(symbol)
        
        # Estimate pip value in USD
        # For EURUSD, pip value is typically $10 for 1 lot (contract size 100k, pip size 0.0001)
        # Pip Value = Pip Size * Contract Size
        pip_val_usd = spec.pip_size * spec.contract_size # in Quote Currency
        
        # Adjust pip value to USD if needed (e.g. for JPY pairs, divide by USDJPY price)
        # A simple approximation or query from MT5 if connected
        current_tick = self.connector.get_tick(symbol)
        if current_tick and (symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD")):
            mid_price = (current_tick["bid"] + current_tick["ask"]) / 2
            pip_val_usd = pip_val_usd / mid_price

        spread_cost = spread_pips * pip_val_usd * lot
        
        # Commission: standard Exness Raw Spread is about $3.5 per side ($7.0 round-turn) per lot.
        # Can be set via parameters, default is $7.0 per lot.
        commission_per_lot = 7.0
        commission = commission_per_lot * lot

        return float(spread_cost), float(commission)

    def route_order(
        self,
        symbol: str,
        order_type: str,
        lot: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "V9 Continuum",
    ) -> Optional[int]:
        """
        Normalizes lot size, records request_price, latency_ms, fill_price,
        and triggers Circuit Breaker if rolling Slippage Drag > 0.3 pips.
        """
        if self.circuit_breaker_tripped:
            print(f"[CIRCUIT BREAKER KILLED] Execution blocked for {symbol}. Slippage exceeds safety threshold ({self.max_allowed_slippage_pips} pips).")
            return None

        t_start = time.perf_counter()
        normalized_lot = self.normalize_lot(symbol, lot)
        
        # Get pre-execution tick request_price
        current_tick = self.connector.get_tick(symbol)
        request_price = price or (current_tick["ask"] if order_type == "BUY" else current_tick["bid"]) if current_tick else None

        ticket = self.connector.place_order(
            symbol=symbol,
            order_type=order_type,
            lot=normalized_lot,
            price=price,
            sl=sl,
            tp=tp,
            comment=comment
        )

        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000.0

        # Post-execution fill_price check
        post_tick = self.connector.get_tick(symbol)
        fill_price = (post_tick["ask"] if order_type == "BUY" else post_tick["bid"]) if post_tick else request_price

        spec = get_symbol_spec(symbol)
        slippage_pips = (abs(fill_price - request_price) / spec.pip_size) if (request_price and fill_price) else 0.0

        record = {
            "symbol": symbol,
            "order_type": order_type,
            "lot": normalized_lot,
            "request_price": request_price,
            "fill_price": fill_price,
            "latency_ms": latency_ms,
            "slippage_pips": slippage_pips,
            "timestamp": time.time()
        }
        self.execution_history.append(record)

        # Audit rolling slippage (last 10 trades)
        recent_slips = [r["slippage_pips"] for r in self.execution_history[-10:]]
        avg_slip = sum(recent_slips) / len(recent_slips) if recent_slips else 0.0
        
        if avg_slip > self.max_allowed_slippage_pips and len(self.execution_history) >= 5:
            self.circuit_breaker_tripped = True
            print(f"[EMERGENCY KILL-SWITCH] Slippage Drag ({avg_slip:.3f} pips) > Limit ({self.max_allowed_slippage_pips} pips)! Circuit Breaker ACTIVATED.")

        return ticket

    def close_position(self, ticket: int, symbol: str) -> bool:
        """
        Closes a position by ticket.
        """
        return self.connector.close_order(ticket, symbol)
