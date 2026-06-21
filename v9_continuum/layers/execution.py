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
        Normalizes lot size and routes order to MT5 via connector.
        """
        normalized_lot = self.normalize_lot(symbol, lot)
        return self.connector.place_order(
            symbol=symbol,
            order_type=order_type,
            lot=normalized_lot,
            price=price,
            sl=sl,
            tp=tp,
            comment=comment
        )

    def close_position(self, ticket: int, symbol: str) -> bool:
        """
        Closes a position by ticket.
        """
        return self.connector.close_order(ticket, symbol)
