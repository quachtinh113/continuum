"""
NowTrading 2.1 — MT5 Connector
Handles all MetaTrader 5 API interactions: connection, data retrieval, order execution.
Supports DRY_RUN mode (no real orders placed).

v2.1.1: Added auto-reconnect, health check, error classification, and error throttling.
"""

import time
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import pandas as pd

from config import settings
from config.symbols import get_mt5_name, get_symbol_spec
from src.audit_logger import log_info, log_error

# Try to import MT5 — graceful fallback for testing on non-Windows
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False


# ── MT5 Timeframe Mapping ──────────────────────────────────
TIMEFRAME_MAP = {
    "M1":  mt5.TIMEFRAME_M1 if MT5_AVAILABLE else 1,
    "M5":  mt5.TIMEFRAME_M5 if MT5_AVAILABLE else 5,
    "M15": mt5.TIMEFRAME_M15 if MT5_AVAILABLE else 15,
    "M30": mt5.TIMEFRAME_M30 if MT5_AVAILABLE else 30,
    "H1":  mt5.TIMEFRAME_H1 if MT5_AVAILABLE else 16385,
    "H4":  mt5.TIMEFRAME_H4 if MT5_AVAILABLE else 16388,
    "D1":  mt5.TIMEFRAME_D1 if MT5_AVAILABLE else 16408,
}

# ── Error codes that indicate market closed (not real errors) ──
_MARKET_CLOSED_ERRORS = {-1, -10002}


class MT5Connector:
    """
    MetaTrader 5 connection and order management.

    When LIVE_TRADING=false (DRY_RUN), still connects to MT5 for data
    but does not place real orders.

    v2.1.1 Features:
    - Auto-reconnect with configurable backoff
    - Health check (terminal_info based)
    - Error classification: market_closed vs real_error
    - Consecutive error tracking per symbol
    - Error log throttling (avoid spam)
    """

    def __init__(self):
        self._connected = False
        self._dry_run = not settings.LIVE_TRADING

        # Error tracking
        self._consecutive_errors: Dict[str, int] = {}  # symbol -> count
        self._global_consecutive_failures: int = 0
        self._last_error_log_time: Dict[str, float] = {}  # key -> timestamp

        # Reconnect config
        backoff_str = getattr(settings, "MT5_RECONNECT_BACKOFF", "5,10,30")
        self._reconnect_backoff = [int(x) for x in backoff_str.split(",")]
        self._reconnect_max_retries = getattr(settings, "MT5_RECONNECT_MAX_RETRIES", 3)

    # ── Connection ──────────────────────────────────────────

    def connect(self) -> bool:
        """
        Initialize MT5 connection.

        Returns:
            True if connected successfully.
        """
        if not MT5_AVAILABLE:
            log_error("MetaTrader5 package not installed. Install with: pip install MetaTrader5")
            return False

        if not mt5.initialize(path=settings.MT5_PATH):
            # Fallback: try auto-detect (common with Exness installations)
            if not mt5.initialize():
                log_error(f"MT5 initialize failed: {mt5.last_error()}")
                return False

        # Login
        authorized = mt5.login(
            login=settings.MT5_ACCOUNT,
            password=settings.MT5_PASSWORD,
            server=settings.MT5_SERVER,
        )

        if not authorized:
            log_error(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        self._connected = True
        self._global_consecutive_failures = 0
        account = mt5.account_info()

        mode = "🔴 LIVE TRADING" if not self._dry_run else "🟡 DRY RUN (Paper)"
        log_info(
            f"MT5 Connected │ {mode} │ "
            f"Account: {account.login} │ "
            f"Balance: ${account.balance:.2f} │ "
            f"Server: {account.server}"
        )

        return True

    def disconnect(self):
        """Shutdown MT5 connection."""
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False
            log_info("MT5 Disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Health Check & Auto-Reconnect ──────────────────────

    def health_check(self) -> bool:
        """
        Check if MT5 terminal is still alive and responsive.

        Returns:
            True if terminal is healthy.
        """
        if not MT5_AVAILABLE or not self._connected:
            return False

        try:
            info = mt5.terminal_info()
            if info is None:
                return False
            # Check if terminal is connected to trade server
            return info.connected
        except Exception:
            return False

    def ensure_connected(self) -> bool:
        """
        Ensure MT5 connection is alive. Auto-reconnect if needed.

        Uses exponential backoff: e.g., 5s, 10s, 30s between retries.

        Returns:
            True if connected (either already was or successfully reconnected).
        """
        if self.health_check():
            return True

        log_info("⚠️ MT5 connection lost. Attempting auto-reconnect...")

        # Shutdown existing connection cleanly
        if MT5_AVAILABLE:
            try:
                mt5.shutdown()
            except Exception:
                pass
        self._connected = False

        # Retry with backoff
        for attempt in range(self._reconnect_max_retries):
            backoff = self._reconnect_backoff[min(attempt, len(self._reconnect_backoff) - 1)]
            log_info(
                f"🔄 Reconnect attempt {attempt + 1}/{self._reconnect_max_retries} "
                f"(waiting {backoff}s)..."
            )
            time.sleep(backoff)

            if self.connect():
                log_info(f"✅ MT5 reconnected successfully on attempt {attempt + 1}")
                return True

        log_error(
            f"❌ MT5 reconnect failed after {self._reconnect_max_retries} attempts. "
            f"Will retry next iteration."
        )
        return False

    # ── Error Tracking ─────────────────────────────────────

    def record_symbol_error(self, symbol: str):
        """Record a consecutive error for a symbol."""
        self._consecutive_errors[symbol] = self._consecutive_errors.get(symbol, 0) + 1

    def clear_symbol_error(self, symbol: str):
        """Clear consecutive error count for a symbol."""
        self._consecutive_errors[symbol] = 0

    def get_symbol_error_count(self, symbol: str) -> int:
        """Get consecutive error count for a symbol."""
        return self._consecutive_errors.get(symbol, 0)

    def record_global_failure(self):
        """Record that ALL symbols failed in this iteration."""
        self._global_consecutive_failures += 1

    def clear_global_failure(self):
        """Reset global consecutive failure counter."""
        self._global_consecutive_failures = 0

    @property
    def global_consecutive_failures(self) -> int:
        return self._global_consecutive_failures

    def _should_log_error(self, key: str) -> bool:
        """
        Check if enough time has passed to log this error again (throttling).

        Returns True if we should log, False if throttled.
        """
        now = time.time()
        throttle_seconds = getattr(settings, "ERROR_LOG_THROTTLE_SECONDS", 300)
        last_time = self._last_error_log_time.get(key, 0)

        if now - last_time >= throttle_seconds:
            self._last_error_log_time[key] = now
            return True
        return False

    # ── Data Retrieval ──────────────────────────────────────

    def get_rates(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
    ) -> Optional[pd.DataFrame]:
        """
        Get candlestick data from MT5.

        Args:
            symbol: Symbol key (e.g. "EURUSD")
            timeframe: Timeframe string (e.g. "H1", "H4", "M15")
            count: Number of bars to retrieve

        Returns:
            DataFrame with columns: time, open, high, low, close, tick_volume
            or None if failed.
        """
        if not self._connected:
            if self._should_log_error("not_connected"):
                log_error("get_rates called but not connected")
            return None

        mt5_symbol = get_mt5_name(symbol)
        tf = TIMEFRAME_MAP.get(timeframe)

        if tf is None:
            log_error(f"Unknown timeframe: {timeframe}")
            return None

        rates = mt5.copy_rates_from_pos(mt5_symbol, tf, 0, count)

        if rates is None or len(rates) == 0:
            last_error = mt5.last_error()
            error_code = last_error[0] if last_error else None

            # Classify error: market closed vs real error
            if error_code in _MARKET_CLOSED_ERRORS:
                # Market closed — throttle logging heavily
                log_key = f"market_closed_{symbol}_{timeframe}"
                if self._should_log_error(log_key):
                    log_error(
                        f"No rates for {mt5_symbol} {timeframe} (market likely closed)",
                        error=str(last_error),
                    )
            else:
                # Real error — log with normal throttle
                log_key = f"rates_error_{symbol}_{timeframe}"
                if self._should_log_error(log_key):
                    log_error(
                        f"No rates for {mt5_symbol} {timeframe}",
                        error=str(last_error),
                    )

            self.record_symbol_error(symbol)
            return None

        # Success — clear error tracking
        self.clear_symbol_error(symbol)

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df

    def get_tick(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Get current tick data (bid, ask, spread).

        Args:
            symbol: Symbol key

        Returns:
            Dict with bid, ask, spread, time or None.
        """
        if not self._connected:
            return None

        mt5_symbol = get_mt5_name(symbol)
        tick = mt5.symbol_info_tick(mt5_symbol)

        if tick is None:
            if self._should_log_error(f"tick_{symbol}"):
                log_error(f"No tick for {mt5_symbol}")
            return None

        spec = get_symbol_spec(symbol)
        spread_pips = (tick.ask - tick.bid) / spec.pip_size

        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "spread_pips": round(spread_pips, 1),
            "time": datetime.fromtimestamp(tick.time, tz=timezone.utc),
        }

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account balance, equity, margin info."""
        if not self._connected:
            return None

        info = mt5.account_info()
        if info is None:
            return None

        return {
            "login": info.login,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "profit": info.profit,
            "leverage": info.leverage,
        }

    # ── Order Execution ─────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        order_type: str,
        lot: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "NowTrading2.0",
    ) -> Optional[int]:
        """
        Place a market order.

        In DRY_RUN mode, logs the order but does not execute.

        Args:
            symbol: Symbol key
            order_type: "BUY" or "SELL"
            lot: Lot size
            price: Price (uses market price if None)
            sl: Stop loss price
            tp: Take profit price
            comment: Order comment

        Returns:
            Order ticket number (or -1 for dry run), None on failure.
        """
        mt5_symbol = get_mt5_name(symbol)

        # Get current price if not provided
        if price is None:
            tick = self.get_tick(symbol)
            if tick is None:
                log_error(f"Cannot get price for {symbol}")
                return None
            price = tick["ask"] if order_type == "BUY" else tick["bid"]

        # DRY RUN
        if self._dry_run:
            log_info(
                f"🟡 DRY RUN ORDER │ {order_type} {lot} {symbol} @ {price} │ "
                f"SL={sl} TP={tp}"
            )
            return -1  # Fake ticket for dry run

        # LIVE ORDER
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": mt5_symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": 20,
            "magic": 202500,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if sl is not None:
            request["sl"] = sl
        if tp is not None:
            request["tp"] = tp

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            log_error(
                f"Order failed for {symbol}",
                retcode=result.retcode if result else "None",
                comment=result.comment if result else "No result",
            )
            return None

        log_info(
            f"🟢 ORDER FILLED │ {order_type} {lot} {symbol} @ {result.price} │ "
            f"Ticket: {result.order}"
        )
        return result.order

    def close_order(self, ticket: int, symbol: str) -> bool:
        """
        Close a position by ticket.

        Args:
            ticket: Order ticket number
            symbol: Symbol key

        Returns:
            True if closed successfully.
        """
        if self._dry_run:
            log_info(f"🟡 DRY RUN CLOSE │ Ticket: {ticket} │ {symbol}")
            return True

        mt5_symbol = get_mt5_name(symbol)

        # Get position info
        position = mt5.positions_get(ticket=ticket)
        if position is None or len(position) == 0:
            log_error(f"Position not found: ticket={ticket}")
            return False

        pos = position[0]
        close_type = (
            mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY
            else mt5.ORDER_TYPE_BUY
        )

        tick = mt5.symbol_info_tick(mt5_symbol)
        close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": mt5_symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": close_price,
            "deviation": 20,
            "magic": 202500,
            "comment": "NowTrading2.0 Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            log_error(
                f"Close failed for ticket {ticket}",
                retcode=result.retcode if result else "None",
            )
            return False

        log_info(f"🔴 POSITION CLOSED │ Ticket: {ticket} │ {symbol} │ P&L: ${pos.profit:.2f}")
        return True

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get open positions, optionally filtered by symbol.

        Returns:
            List of position dicts.
        """
        if not self._connected:
            return []

        if symbol:
            mt5_symbol = get_mt5_name(symbol)
            positions = mt5.positions_get(symbol=mt5_symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        return [
            {
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "BUY" if pos.type == 0 else "SELL",
                "volume": pos.volume,
                "price_open": pos.price_open,
                "price_current": pos.price_current,
                "profit": pos.profit,
                "time": datetime.fromtimestamp(pos.time, tz=timezone.utc),
                "magic": pos.magic,
                "comment": pos.comment,
            }
            for pos in positions
        ]

    def get_daily_profit(self) -> float:
        """
        Calculate total profit/loss for today from closed and open positions.

        Returns:
            Total P&L in USD.
        """
        if not self._connected:
            return 0.0

        account = mt5.account_info()
        if account is None:
            return 0.0

        # Current unrealized P&L
        return account.profit
