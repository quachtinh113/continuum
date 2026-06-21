"""
NowTrading 2.1 — Backtest Engine
Runs a look-ahead-free historical simulation of the trading strategy.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import pandas_ta as ta

from config import settings
from config.symbols import get_symbol_spec, get_all_symbols
from src.regime_engine import RegimeEngine, MarketRegime
from src.audit_logger import log_info
from src.xgboost_gatekeeper import MLGatekeeper
from src.signal_engine import SignalEngine, Signal
from src.session_manager import get_current_session, is_weekend, Session
from src.hourly_gate import HourlyGate
from src.trade_cycle_manager import TradeCycle, DCALayer, CycleStatus


def get_server_hour(current_time: datetime) -> int:
    """Calculate server hour based on European DST (MT5 Server Time offset)."""
    year = current_time.year
    # Last Sunday of March (Europe DST starts)
    dst_start = datetime(year, 3, 31, 1, tzinfo=timezone.utc)
    dst_start = dst_start - timedelta(days=(dst_start.weekday() + 1) % 7)
    # Last Sunday of October (Europe DST ends)
    dst_end = datetime(year, 10, 31, 1, tzinfo=timezone.utc)
    dst_end = dst_end - timedelta(days=(dst_end.weekday() + 1) % 7)
    
    if dst_start <= current_time < dst_end:
        server_offset = 3
    else:
        server_offset = 2
        
    return (current_time + timedelta(hours=server_offset)).hour


def get_backtest_spread(symbol: str, current_time: datetime) -> float:
    """Calculate spread penalty based on symbol category and Rollover hour (21:00 - 22:00 Server time)."""
    server_hour = get_server_hour(current_time)
    
    # Check if Rollover hour (21:00 - 22:00 Server Time)
    is_rollover = (21 <= server_hour < 22)
    spec = get_symbol_spec(symbol)
    
    if spec.category == "FX":
        pips = 3.0 if is_rollover else 1.0
        return pips * spec.pip_size
    elif spec.category == "GOLD":
        points = 80.0 if is_rollover else 25.0
        return points * spec.pip_size
    elif symbol == "BTCUSD":
        return 15.0 if is_rollover else 5.0
    else:
        return 4.0 if is_rollover else 2.0


class VirtualPortfolio:
    """Tracks account balance, equity, and open trade cycles during backtest."""

    def __init__(self, initial_balance: float = 10000.0, use_spread: bool = False):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.start_of_day_balance = initial_balance
        self.active_cycles: Dict[str, TradeCycle] = {}
        self.closed_cycles: List[TradeCycle] = []
        self.daily_losses: Dict[str, float] = {}  # date string -> total loss
        self.equity_curve: List[Dict[str, Any]] = []
        self.use_spread = use_spread
        # Inline drawdown tracking (used when skip_equity_curve=True)
        self.peak_equity: float = initial_balance
        self.max_drawdown_usd: float = 0.0
        self.max_drawdown_pct: float = 0.0

    def open_cycle(
        self,
        symbol: str,
        direction: str,
        price: float,
        time: datetime,
        session: str,
        ml_features: Optional[Dict[str, float]] = None,
        base_lot: Optional[float] = None,
    ) -> TradeCycle:
        """Open a new virtual trade cycle."""
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
        if self.use_spread:
            spread = get_backtest_spread(symbol, time)
            adjusted_price = price + spread if direction == "BUY" else price - spread
        else:
            adjusted_price = price
        cycle = TradeCycle(
            symbol=symbol,
            direction=direction,
            entry_time=time,
            session=session,
            base_entry_price=adjusted_price,
            tickets=[len(self.closed_cycles) + len(self.active_cycles) + 1],
            ml_features=ml_features,
            base_lot=base_lot,
        )
        self.active_cycles[symbol] = cycle
        return cycle

    def add_dca(self, symbol: str, price: float, time: datetime, lot_size: Optional[float] = None):
        """Add a DCA layer to an active cycle."""
        cycle = self.active_cycles.get(symbol)
        if not cycle:
            return
        if lot_size is None:
            if getattr(settings, "DCA_LOT_STYLE", "DYNAMIC") == "FIXED" and getattr(settings, "DCA_LOTS", None):
                idx = min(len(cycle.dca_layers), len(settings.DCA_LOTS) - 1)
                lot_size = settings.DCA_LOTS[idx]
            else:
                lot_size = cycle.base_lot
        if self.use_spread:
            spread = get_backtest_spread(symbol, time)
            adjusted_price = price + spread if cycle.direction == "BUY" else price - spread
        else:
            adjusted_price = price
        layer = DCALayer(
            entry_price=adjusted_price,
            lot_size=lot_size,
            entry_time=time,
            ticket=len(self.closed_cycles) + len(self.active_cycles) + 1000,
        )
        cycle.dca_layers.append(layer)
        cycle.tickets.append(layer.ticket)

    def close_cycle(self, symbol: str, price: float, time: datetime, reason: str):
        """Close an active cycle and realize P&L."""
        cycle = self.active_cycles.get(symbol)
        if not cycle:
            return

        # Calculate final P&L
        self.update_cycle_pnl(symbol, price, time)
        realized_pnl = cycle.current_profit_usd

        # Remove from active
        self.active_cycles.pop(symbol)

        # Update balance
        self.balance += realized_pnl
        cycle.status = CycleStatus.CLOSED
        cycle.close_reason = reason
        self.closed_cycles.append(cycle)

        # Track daily drawdown
        if realized_pnl < 0:
            date_str = time.strftime("%Y-%m-%d")
            self.daily_losses[date_str] = self.daily_losses.get(date_str, 0.0) + abs(realized_pnl)

    def update_cycle_pnl(self, symbol: str, current_price: float, current_time: datetime):
        """Update a cycle's floating P&L and holding hours."""
        cycle = self.active_cycles.get(symbol)
        if not cycle:
            return

        elapsed = current_time - cycle.entry_time
        cycle.holding_hours = elapsed.total_seconds() / 3600.0

        spec = get_symbol_spec(symbol)
        avg_price = cycle.average_entry_price
        total_lots = cycle.total_lots

        if cycle.direction == "BUY":
            price_diff = current_price - avg_price
        else:
            price_diff = avg_price - current_price

        profit_quote_ccy = price_diff * total_lots * spec.contract_size
        
        # Convert to USD if quote currency is not USD
        if symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD"):
            profit_usd = profit_quote_ccy / current_price
        else:
            profit_usd = profit_quote_ccy

        cycle.current_profit_usd = profit_usd + getattr(cycle, "realized_partial_pnl", 0.0)

    def get_daily_loss(self, time: datetime) -> float:
        """Get total loss realized today."""
        date_str = time.strftime("%Y-%m-%d")
        return self.daily_losses.get(date_str, 0.0)

    def get_equity(self, current_prices: Dict[str, float], time: datetime) -> float:
        """Calculate current equity without appending to equity_curve."""
        floating_pnl = 0.0
        for symbol, cycle in self.active_cycles.items():
            price = current_prices.get(symbol)
            if price is not None:
                self.update_cycle_pnl(symbol, price, time)
            floating_pnl += cycle.current_profit_usd
        return self.balance + floating_pnl

    def update_equity(self, current_prices: Dict[str, float], time: datetime, skip_curve: bool = False):
        """Update account equity based on open position floating P&L."""
        self.equity = self.get_equity(current_prices, time)
        # Always update inline drawdown tracking
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        dd_usd = self.peak_equity - self.equity
        dd_pct = (dd_usd / self.peak_equity) * 100.0 if self.peak_equity > 0 else 0.0
        if dd_usd > self.max_drawdown_usd:
            self.max_drawdown_usd = dd_usd
        if dd_pct > self.max_drawdown_pct:
            self.max_drawdown_pct = dd_pct
        if not skip_curve:
            self.equity_curve.append({
                "time": time,
                "balance": self.balance,
                "equity": self.equity,
                "active_cycles": len(self.active_cycles)
            })


class BacktestEngine:
    """Runs a historical simulation on downloaded CSV files."""

    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = Path(data_dir)
        self.regime_engine = RegimeEngine()
        self.signal_engine = SignalEngine(self.regime_engine)
        self.hourly_gate = HourlyGate()
        self.ml_gatekeeper = MLGatekeeper()

    def load_and_prepare_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Load historical CSV data for a symbol and compute aligned indicators.
        Shifts index timestamps to end-of-bar to guarantee look-ahead-free merge.
        """
        f_m15 = self.data_dir / f"{symbol}_M15.csv"
        f_h1 = self.data_dir / f"{symbol}_H1.csv"
        f_h4 = self.data_dir / f"{symbol}_H4.csv"

        if not (f_m15.exists() and f_h1.exists() and f_h4.exists()):
            return None

        # Load raw data
        df_m15 = pd.read_csv(f_m15)
        df_h1 = pd.read_csv(f_h1)
        df_h4 = pd.read_csv(f_h4)

        for df in [df_m15, df_h1, df_h4]:
            df["time"] = pd.to_datetime(df["time"], utc=True)

        # 1. Compute H4 Indicators
        df_h4["RSI_H4"] = ta.rsi(df_h4["close"], length=settings.RSI_PERIOD)
        # Shift index to "available_time" (+4h)
        df_h4["available_time"] = df_h4["time"] + pd.Timedelta(hours=4)
        df_h4_shifted = df_h4[["available_time", "RSI_H4"]].set_index("available_time")

        # 2. Compute H1 Indicators
        df_h1["RSI_H1"] = ta.rsi(df_h1["close"], length=settings.RSI_PERIOD)
        df_h1["ADX"] = ta.adx(df_h1["high"], df_h1["low"], df_h1["close"], length=settings.ADX_PERIOD)[f"ADX_{settings.ADX_PERIOD}"]
        df_h1["ATR"] = ta.atr(df_h1["high"], df_h1["low"], df_h1["close"], length=settings.ATR_PERIOD)
        # Shift index to "available_time" (+1h)
        df_h1["available_time"] = df_h1["time"] + pd.Timedelta(hours=1)
        df_h1_shifted = df_h1[["available_time", "RSI_H1", "ADX", "ATR"]].set_index("available_time")

        # 3. Compute M15 Indicators & Pullback Exhaustion Features
        df_m15["RSI_M15"] = ta.rsi(df_m15["close"], length=settings.RSI_PERIOD)
        df_m15["ATR_M15"] = ta.atr(df_m15["high"], df_m15["low"], df_m15["close"], length=settings.ATR_PERIOD)

        # Pullback features (vectorized)
        df_m15["M15_RSI_RISING"] = df_m15["RSI_M15"] > df_m15["RSI_M15"].shift(1)
        df_m15["M15_RSI_FALLING"] = df_m15["RSI_M15"] < df_m15["RSI_M15"].shift(1)
        df_m15["M15_CLOSE_RISING"] = df_m15["close"] > df_m15["close"].shift(1)
        df_m15["M15_CLOSE_FALLING"] = df_m15["close"] < df_m15["close"].shift(1)

        lb = settings.PULLBACK_LOOKBACK_BARS
        df_m15["M15_FRESH_LOCAL_LOW"] = df_m15["low"] < df_m15["low"].shift(1).rolling(lb).min()
        df_m15["M15_FRESH_LOCAL_HIGH"] = df_m15["high"] > df_m15["high"].shift(1).rolling(lb).max()

        # Shift index to "available_time" (+15m)
        df_m15["available_time"] = df_m15["time"] + pd.Timedelta(minutes=15)
        df_m15_shifted = df_m15.set_index("available_time")

        # 4. Look-Ahead-Free Merge
        master = df_m15_shifted.join(df_h1_shifted, how="left")
        master = master.join(df_h4_shifted, how="left")
        
        # Forward fill the hourly and 4-hourly indicator values
        master = master.ffill()
        
        # Drop rows where indicators are still NaN (startup period)
        master = master.dropna(subset=["RSI_H4", "RSI_H1", "ADX", "ATR", "RSI_M15"])
        
        # Add symbol column for multi-symbol merging
        master["symbol"] = symbol
        
        return master.reset_index()

    def run_backtest(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        initial_balance: float = 10000.0,
        no_time_stop: bool = False,
        use_spread: bool = False,
        preloaded_df: Optional[pd.DataFrame] = None,
        skip_equity_curve: bool = False,
        skip_ml_export: bool = False,
    ) -> Tuple[VirtualPortfolio, Dict[str, Any]]:
        """Run a portfolio-wide chronological simulation of NowTrading 2.1 strategy."""
        
        # 1. Load and align all symbols data
        if preloaded_df is None:
            symbol_dfs = {}
            for s in symbols:
                df = self.load_and_prepare_data(s)
                if df is not None:
                    # Filter by backtest date range
                    df = df[(df["available_time"] >= start_date) & (df["available_time"] <= end_date)]
                    if not df.empty:
                        symbol_dfs[s] = df
                else:
                    print(f"Skipping symbol {s}: CSV data missing or incomplete.")

            if not symbol_dfs:
                raise ValueError("No historical data available for the specified symbols and date range.")

            # Combined timeline of all available times
            all_dfs = list(symbol_dfs.values())
            combined_df = pd.concat(all_dfs, ignore_index=True)
            # Sort chronologically by available_time, then symbol
            combined_df = combined_df.sort_values(by=["available_time", "symbol"])
        else:
            combined_df = preloaded_df[(preloaded_df["available_time"] >= start_date) & (preloaded_df["available_time"] <= end_date)]

        # Reset HourlyGate state
        self.hourly_gate.reset()

        portfolio = VirtualPortfolio(initial_balance, use_spread=use_spread)
        
        # Convert to records once to bypass pandas overhead in the loop
        records = combined_df.to_dict(orient="records")
        
        # Group by available_time in pure Python
        grouped_data = {}
        for r in records:
            t = r["available_time"]
            if t not in grouped_data:
                grouped_data[t] = []
            grouped_data[t].append(r)
            
        # Chronological loop
        sorted_times = sorted(grouped_data.keys())
        
        last_date = None
        day_blocked = False
        
        for t_stamp in sorted_times:
            current_time = t_stamp.to_pydatetime().replace(tzinfo=timezone.utc) if hasattr(t_stamp, "to_pydatetime") else t_stamp
            if not isinstance(current_time, datetime):
                current_time = pd.Timestamp(current_time).to_pydatetime().replace(tzinfo=timezone.utc)
            else:
                current_time = current_time.replace(tzinfo=timezone.utc)
                
            current_date = current_time.strftime("%Y-%m-%d")
            
            if last_date is None or current_date != last_date:
                portfolio.start_of_day_balance = portfolio.balance
                day_blocked = False
                last_date = current_date
            
            # Map symbol prices for current timestep
            group_records = grouped_data[t_stamp]
            current_prices = {r["symbol"]: r["close"] for r in group_records}
            indicators_map = {r["symbol"]: r for r in group_records}
            
            # Check daily drawdown cut (corrective)
            current_equity = portfolio.get_equity(current_prices, current_time)
            if not day_blocked and (portfolio.start_of_day_balance - current_equity >= settings.MAX_DAILY_DRAWDOWN_USD):
                day_blocked = True
                active_symbols = list(portfolio.active_cycles.keys())
                for s in active_symbols:
                    close_price = current_prices.get(s, portfolio.active_cycles[s].average_entry_price)
                    portfolio.close_cycle(s, close_price, current_time, "DAILY_DRAWDOWN_CUT")
                    self.hourly_gate.reset(s)
            
            # 1. Update existing active cycles: Evaluate Exits & DCAs
            symbols_to_process = list(portfolio.active_cycles.keys())
            for s in symbols_to_process:
                cycle = portfolio.active_cycles[s]
                
                # Check if current bar has price data for this symbol
                if s not in current_prices:
                    continue
                    
                row = indicators_map[s]
                bar_high = row["high"]
                bar_low = row["low"]
                bar_close = row["close"]
                bar_open = row["open"]
                
                # Update holding hours and profit using M15 close price
                portfolio.update_cycle_pnl(s, bar_close, current_time)
                
                # Track maximum adverse excursion (MAE)
                if cycle.direction == "BUY":
                    ae = cycle.base_entry_price - bar_low
                else:
                    ae = bar_high - cycle.base_entry_price
                if not hasattr(cycle, "max_adverse_excursion") or ae > cycle.max_adverse_excursion:
                    cycle.max_adverse_excursion = ae
                
                # ── Close rules checks ──
                if not no_time_stop:
                        
                    # A.0 Calculate ML Score
                    ml_score = None
                    if settings.ML_GATEKEEPER_ACTIVE and getattr(self, "ml_gatekeeper", None) and self.ml_gatekeeper.is_ready:
                        features = {
                            "RSI_M15": row.get("RSI_M15"),
                            "RSI_H1": row.get("RSI_H1"),
                            "RSI_H4": row.get("RSI_H4"),
                            "ADX": row.get("ADX"),
                            "ATR": row.get("ATR"),
                            "hour": current_time.hour
                        }
                        ml_score = self.ml_gatekeeper.score_trade(features, bar_close, current_time.hour)

                    # A.1 ML Veto Close (Dynamic Threshold with flat fallback)
                    if ml_score is not None:
                        current_layer = cycle.num_dca_layers
                        if current_layer == 0:
                            threshold = getattr(settings, "ML_VETO_THRESHOLD_L0", settings.ML_VETO_THRESHOLD)
                        elif current_layer == 1:
                            threshold = getattr(settings, "ML_VETO_THRESHOLD_L1", settings.ML_VETO_THRESHOLD)
                        elif current_layer == 2:
                            threshold = getattr(settings, "ML_VETO_THRESHOLD_L2", settings.ML_VETO_THRESHOLD)
                        else:
                            threshold = getattr(settings, "ML_VETO_THRESHOLD_L3", settings.ML_VETO_THRESHOLD)
                            
                        if ml_score > threshold:
                            portfolio.close_cycle(s, bar_close, current_time, "ML_VETO_CLOSE")
                            self.hourly_gate.reset(s)
                            continue
                        
                    # A.2 Hard Stop Loss (Pips-based or ATR-based)
                    spec = get_symbol_spec(s)
                    hard_sl_triggered = False
                    if getattr(settings, "HARD_STOP_LOSS_PIPS", 0.0) > 0:
                        max_loss_price = settings.HARD_STOP_LOSS_PIPS * spec.pip_size
                        avg_price = cycle.average_entry_price
                        if cycle.direction == "BUY":
                            hard_sl_triggered = (avg_price - bar_close >= max_loss_price)
                        else:
                            hard_sl_triggered = (bar_close - avg_price >= max_loss_price)
                        
                        if hard_sl_triggered:
                            portfolio.close_cycle(s, bar_close, current_time, "HARD_STOP_LOSS")
                            self.hourly_gate.reset(s)
                            continue
                    
                    if not hard_sl_triggered:
                        atr = row.get("ATR")
                        if atr is not None and atr > 0:
                            profit_quote_ccy = (atr * settings.TAKE_PROFIT_ATR_MULTIPLIER) * cycle.total_lots * spec.contract_size
                            if s.endswith("JPY") or s.endswith("CHF") or s.endswith("CAD"):
                                expected_profit_usd = profit_quote_ccy / bar_close
                            else:
                                expected_profit_usd = profit_quote_ccy
                                
                            max_loss_usd = 1.5 * expected_profit_usd
                            if cycle.current_profit_usd < -max_loss_usd:
                                portfolio.close_cycle(s, bar_close, current_time, "FORCE_CLOSE_RR_LIMIT")
                                self.hourly_gate.reset(s)
                                continue

                    # B. Conditional Force Close Rule (REGIME_FILTER_EXIT)
                    if cycle.current_profit_usd <= 0:
                        adx = row.get("ADX")
                        rsi_h4 = row.get("RSI_H4")
                        rsi_h1 = row.get("RSI_H1")
                        
                        trend_reversed = False
                        if adx is not None and adx >= settings.ADX_TREND_THRESHOLD:
                            if cycle.direction == "BUY":
                                trend_reversed = (
                                    rsi_h4 is not None and rsi_h4 < settings.RSI_SELL_THRESHOLD
                                    and rsi_h1 is not None and rsi_h1 < settings.RSI_SELL_THRESHOLD
                                )
                            else:
                                trend_reversed = (
                                    rsi_h4 is not None and rsi_h4 > settings.RSI_BUY_THRESHOLD
                                    and rsi_h1 is not None and rsi_h1 > settings.RSI_BUY_THRESHOLD
                                )
                        
                        overextended = False
                        if rsi_h1 is not None:
                            if cycle.direction == "BUY":
                                overextended = rsi_h1 < settings.RSI_OVEREXTENDED_LOW
                            else:
                                overextended = rsi_h1 > settings.RSI_OVEREXTENDED_HIGH
                                
                        if trend_reversed or overextended:
                            portfolio.close_cycle(s, bar_close, current_time, "CONDITIONAL_FORCE_CLOSE")
                            self.hourly_gate.reset(s)
                            continue

                    # B. 12-Hour Review Rule (ATR_ADAPTIVE_DCA_CHECK)
                    if cycle.holding_hours > settings.HOLDING_REDUCE_HOURS and cycle.current_profit_usd <= 0:
                        
                        # ── ML Exit Control ──
                        if ml_score is not None:
                            if ml_score > settings.ML_VETO_THRESHOLD:
                                portfolio.close_cycle(s, bar_close, current_time, "12H_CUT_ALL")
                                self.hourly_gate.reset(s)
                                continue
                            else:
                                # ML says hold, skip fallback logic
                                continue
                                
                        # Fallback logic
                        atr = row.get("ATR")
                        adx = row.get("ADX")
                        
                        atr_check_passed = False
                        if atr is not None and atr > 0:
                            distance = abs(bar_close - cycle.average_entry_price)
                            threshold = settings.ATR_DCA_CHECK_MULTIPLIER * atr
                            if distance <= threshold:
                                atr_check_passed = True
                                
                        if not atr_check_passed:
                            if not cycle.dca_frozen:
                                cycle.dca_frozen = True
                            
                            rule_decision = "CUT_ALL"
                            if adx is not None and adx > settings.ADX_TREND_THRESHOLD:
                                if cycle.num_dca_layers > 0:
                                    rule_decision = "REDUCE_DCA"
                                    
                            if rule_decision == "CUT_ALL":
                                portfolio.close_cycle(s, bar_close, current_time, "12H_CUT_ALL")
                                self.hourly_gate.reset(s)
                                continue
                            elif rule_decision == "REDUCE_DCA" and cycle.dca_layers:
                                worst_layer = cycle.dca_layers.pop()
                                cycle.tickets.remove(worst_layer.ticket)
                                cycle.dca_frozen = True
                                lot_size = worst_layer.lot_size
                                spec = get_symbol_spec(s)
                                if cycle.direction == "BUY":
                                    layer_loss = (bar_close - worst_layer.entry_price) * lot_size * spec.contract_size
                                else:
                                    layer_loss = (worst_layer.entry_price - bar_close) * lot_size * spec.contract_size
                                portfolio.balance += layer_loss
                                cycle.realized_partial_pnl = getattr(cycle, "realized_partial_pnl", 0.0) + layer_loss
                                portfolio.update_cycle_pnl(s, bar_close, current_time)
                
                # C. Take Profit Rule (Pips-based or ATR-based)
                if cycle.holding_hours > 1.0:
                    spec = get_symbol_spec(s)
                    avg_price = cycle.average_entry_price
                    total_lots = cycle.total_lots
                    if getattr(settings, "TAKE_PROFIT_PIPS", 0.0) > 0:
                        required_diff = settings.TAKE_PROFIT_PIPS * spec.pip_size
                    else:
                        atr = row.get("ATR")
                        if atr is not None and atr > 0:
                            required_diff = atr * settings.TAKE_PROFIT_ATR_MULTIPLIER
                        else:
                            required_diff = settings.PROFIT_TARGET_USD / (total_lots * spec.contract_size)
                    
                    if cycle.direction == "BUY":
                        target_price = avg_price + required_diff
                        # Did price touch target?
                        if bar_high >= target_price:
                            fill_price = max(bar_open, target_price)
                            portfolio.close_cycle(s, fill_price, current_time, "TAKE_PROFIT")
                            self.hourly_gate.reset(s)
                            continue
                    else: # SELL
                        target_price = avg_price - required_diff
                        if bar_low <= target_price:
                            fill_price = min(bar_open, target_price)
                            portfolio.close_cycle(s, fill_price, current_time, "TAKE_PROFIT")
                            self.hourly_gate.reset(s)
                            continue

                # ── Break-Even Rule ──
                atr = row.get("ATR")
                if atr is not None and atr > 0:
                    avg_price = cycle.average_entry_price
                    activation_mult = getattr(settings, "BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER", 0.75)
                    buffer_mult = getattr(settings, "BREAK_EVEN_BUFFER_ATR_MULTIPLIER", 0.0)
                    
                    activation_distance = atr * activation_mult
                    buffer_distance = atr * buffer_mult

                    if cycle.direction == "BUY":
                        # 1. Activate BE if price reached activation distance
                        if not getattr(cycle, "be_activated", False) and bar_high >= avg_price + activation_distance:
                            cycle.be_activated = True
                        
                        # 2. If BE is active and price pulls back to average entry + buffer distance, exit
                        if getattr(cycle, "be_activated", False) and bar_low <= avg_price + buffer_distance:
                            fill_price = min(bar_open, avg_price + buffer_distance)
                            portfolio.close_cycle(s, fill_price, current_time, "BREAK_EVEN")
                            self.hourly_gate.reset(s)
                            continue
                    else: # SELL
                        # 1. Activate BE if price reached activation distance
                        if not getattr(cycle, "be_activated", False) and bar_low <= avg_price - activation_distance:
                            cycle.be_activated = True
                        
                        # 2. If BE is active and price pulls back to average entry - buffer distance, exit
                        if getattr(cycle, "be_activated", False) and bar_high >= avg_price - buffer_distance:
                            fill_price = max(bar_open, avg_price - buffer_distance)
                            portfolio.close_cycle(s, fill_price, current_time, "BREAK_EVEN")
                            self.hourly_gate.reset(s)
                            continue


                # ── DCA rules check ──
                # Spacing based on H1 ATR or Fixed Pips
                atr = row["ATR"]
                if atr is not None and atr > 0 and not cycle.dca_frozen and cycle.num_dca_layers < settings.MAX_DCA_LAYERS:
                    spec = get_symbol_spec(s)
                    if getattr(settings, "DCA_STEP_PIPS", 0.0) > 0:
                        spacing = settings.DCA_STEP_PIPS * spec.pip_size
                    else:
                        multipliers = [settings.DCA_LAYER_1_ATR, settings.DCA_LAYER_2_ATR, settings.DCA_LAYER_3_ATR]
                        spacing = atr * multipliers[cycle.num_dca_layers]
                    
                    last_entry = cycle.dca_layers[-1].entry_price if cycle.dca_layers else cycle.base_entry_price
                    
                    # Thesis check
                    dca_valid = self.signal_engine.check_dca_validity(cycle.direction, row)
                    
                    # Daily drawdown check (includes realized loss and floating loss)
                    daily_realized = portfolio.get_daily_loss(current_time)
                    current_floating_loss = sum(max(0.0, -c.current_profit_usd) for c in portfolio.active_cycles.values())
                    drawdown_ok = (daily_realized + current_floating_loss) < settings.MAX_DAILY_DRAWDOWN_USD
                    
                    # Check rollover hour
                    server_hour = get_server_hour(current_time)
                    rollover_block = (21 <= server_hour < 22)
                    
                    if dca_valid and drawdown_ok and not day_blocked and not rollover_block:
                        if cycle.num_dca_layers >= 1 and ml_score is not None and ml_score >= 0.4:
                            pass # Block DCA
                        else:
                            if cycle.direction == "BUY":
                                dca_price = last_entry - spacing
                                if bar_low <= dca_price:
                                    fill_price = min(bar_open, dca_price)
                                    portfolio.add_dca(s, fill_price, current_time)
                            else: # SELL
                                dca_price = last_entry + spacing
                                if bar_high >= dca_price:
                                    fill_price = max(bar_open, dca_price)
                                    portfolio.add_dca(s, fill_price, current_time)

            # 2. Check for New Entries (only at the first M15 bar of each hour when Hourly Gate opens)
            # This is equivalent to being in the live bot's minute 0-4 window.
            # In historical data, available_time for M15 bars starts at 00, 15, 30, 45.
            # So the candle closing at the hour mark (available_time.minute == 0) is the only evaluation point.
            is_new_hour_bar = current_time.minute == 0
            
            # Weekend filter
            if not is_weekend(current_time) and is_new_hour_bar:
                server_hour = get_server_hour(current_time)
                rollover_block = (21 <= server_hour < 22)
                
                session = get_current_session(current_time)
                if session != Session.OFF:
                    for row in group_records:
                        s = row["symbol"]
                        
                        # Already has active cycle?
                        if s in portfolio.active_cycles:
                            continue
                            
                        # Daily drawdown hit? (includes realized loss and floating loss)
                        daily_realized = portfolio.get_daily_loss(current_time)
                        current_floating_loss = sum(max(0.0, -c.current_profit_usd) for c in portfolio.active_cycles.values())
                        if (daily_realized + current_floating_loss) >= settings.MAX_DAILY_DRAWDOWN_USD or day_blocked or rollover_block:
                            continue
                            
                        # Evaluate Circuit Breaker & Dynamic Lot
                        equity = portfolio.get_equity(current_prices, current_time)
                        balance = portfolio.balance
                        drawdown = 0.0
                        if balance > 0:
                            drawdown = (balance - equity) / balance
                            
                        if drawdown > 0.08:
                            continue # Circuit breaker freeze
                            
                        # Max portfolio active cycles reached?
                        if len(portfolio.active_cycles) >= settings.MAX_ACTIVE_CYCLES:
                            continue

                        # Evaluate Signal
                        signal = self.signal_engine.evaluate(row)
                        
                        if signal in [Signal.BUY, Signal.SELL]:
                            # Portfolio exposure limits (simulate add)
                            sim_exposures = {}
                            for c in portfolio.active_cycles.values():
                                self._add_exposure(c.symbol, c.direction, sim_exposures)
                            
                            # Add simulated trade
                            dir_str = "BUY" if signal == Signal.BUY else "SELL"
                            self._add_exposure(s, dir_str, sim_exposures)
                            
                            portfolio_ok = True
                            for asset, val in sim_exposures.items():
                                if abs(val) > 3: # MAX_EXPOSURE = 3
                                    portfolio_ok = False
                                    break
                                    
                            # Check hourly gate (cannot trade twice in same hourly bucket)
                            # In M15 data, the hour bucket is unique per hour.
                            hour_bucket = current_time.strftime("%Y-%m-%d %H")
                            gate_ok = True
                            # HourlyGate class is in memory but let's manage custom hourly check for historical simplicity
                            # since HourlyGate is simple
                            last_gate_bucket = self.hourly_gate.get_status().get(s)
                            if last_gate_bucket == hour_bucket:
                                  gate_ok = False
                                
                            if portfolio_ok and gate_ok:
                                # Open new cycle
                                bar_close = row["close"]
                                features = {
                                    "RSI_M15": row.get("RSI_M15"),
                                    "RSI_H1": row.get("RSI_H1"),
                                    "RSI_H4": row.get("RSI_H4"),
                                    "ADX": row.get("ADX"),
                                    "ATR": row.get("ATR"),
                                    "hour": current_time.hour
                                }
                                
                                # ── ML Gatekeeper Entry Veto ──
                                ml_score = None
                                if settings.ML_GATEKEEPER_ACTIVE and getattr(self, "ml_gatekeeper", None) and self.ml_gatekeeper.is_ready:
                                    score = self.ml_gatekeeper.score_trade(features, bar_close, current_time.hour)
                                    ml_score = score
                                    if score is not None:
                                        is_safe = self.ml_gatekeeper.is_entry_safe(score)
                                        if not is_safe:
                                            # Skip entry, ML Vetoed
                                            continue

                                # ── Dynamic Lot Size Calculation (aligned with risk_engine.py get_dynamic_lot_size()) ──
                                spec = get_symbol_spec(s)
                                if spec.category == "FX":
                                    final_base_lot = settings.FX_BASE_LOT
                                elif spec.category in ["GOLD", "COMMODITY"]:
                                    final_base_lot = settings.COMMODITY_BASE_LOT
                                elif spec.category == "CRYPTO":
                                    final_base_lot = settings.CRYPTO_BASE_LOT
                                else:
                                    final_base_lot = settings.MAX_LOT_SIZE

                                # DD Protection (cut 50% if drawdown > 5%)
                                if drawdown > 0.05:
                                    final_base_lot = final_base_lot * 0.5

                                # ML Lot Scaling (3-tier)
                                if ml_score is not None:
                                    if ml_score < settings.ML_LOT_BOOST_THRESHOLD:
                                        final_base_lot = final_base_lot * settings.ML_LOT_BOOST_MULTIPLIER
                                    elif ml_score > settings.ML_LOT_REDUCE_THRESHOLD:
                                        final_base_lot = final_base_lot * settings.ML_LOT_REDUCE_MULTIPLIER

                                final_base_lot = max(0.01, min(round(final_base_lot, 2), settings.MAX_LOT_SIZE * 10))
                                        
                                portfolio.open_cycle(s, dir_str, bar_close, current_time, session.value, features, final_base_lot)
                                self.hourly_gate.record_trade(s, current_time)

            # Update portfolio equity curve
            portfolio.update_equity(current_prices, current_time, skip_curve=skip_equity_curve)

        # 3. Compile Performance Metrics
        metrics = self._calculate_metrics(portfolio, skip_ml_export=skip_ml_export)
        return portfolio, metrics

    def check_12h_rule(self, cycle: TradeCycle, adx: Optional[float]) -> str:
        """Helper to decide on 12h rule action."""
        if adx is not None and adx > settings.ADX_TREND_THRESHOLD:
            if cycle.num_dca_layers > 0:
                return "REDUCE_DCA"
            else:
                return "CUT_ALL"
        else:
            return "CUT_ALL"

    def _add_exposure(self, symbol: str, direction: str, exposures: Dict[str, int]):
        """Ported helper from PortfolioEngine for backtest validation."""
        multiplier = 1 if direction == "BUY" else -1
        clean_symbol = symbol.replace("m", "")
        if len(clean_symbol) == 6 and clean_symbol.endswith("USD"):
            base, quote = clean_symbol[:3], "USD"
            exposures[base] = exposures.get(base, 0) + multiplier
            exposures[quote] = exposures.get(quote, 0) - multiplier
        elif len(clean_symbol) == 6 and clean_symbol.startswith("USD"):
            base, quote = "USD", clean_symbol[3:]
            exposures[base] = exposures.get(base, 0) + multiplier
            exposures[quote] = exposures.get(quote, 0) - multiplier
        elif clean_symbol in ["US30", "US100", "US500", "USTEC"]:
            exposures["US_INDEX"] = exposures.get("US_INDEX", 0) + multiplier
        elif clean_symbol == "XAUUSD":
            exposures["XAU"] = exposures.get("XAU", 0) + multiplier
            exposures["USD"] = exposures.get("USD", 0) - multiplier
        elif clean_symbol == "BTCUSD":
            exposures["BTC"] = exposures.get("BTC", 0) + multiplier
            exposures["USD"] = exposures.get("USD", 0) - multiplier

    def _calculate_metrics(self, portfolio: VirtualPortfolio, skip_ml_export: bool = False) -> Dict[str, Any]:
        """Compute all stats and performance KPIs of the backtest."""
        closed = portfolio.closed_cycles
        total_cycles = len(closed)
        
        if total_cycles == 0:
            return {
                "total_profit_usd": 0.0,
                "profit_percent": 0.0,
                "total_cycles": 0,
                "win_rate": 0.0,
                "max_drawdown_usd": 0.0,
                "max_drawdown_percent": 0.0,
            }

        winning_cycles = [c for c in closed if c.current_profit_usd > 0]
        losing_cycles = [c for c in closed if c.current_profit_usd <= 0]
        
        total_profit = sum(c.current_profit_usd for c in closed)
        profit_percent = (total_profit / portfolio.initial_balance) * 100.0
        
        win_rate = (len(winning_cycles) / total_cycles) * 100.0
        
        gross_profit = sum(c.current_profit_usd for c in winning_cycles)
        gross_loss = abs(sum(c.current_profit_usd for c in losing_cycles))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        # Drawdown calculation - prefer inline tracked values, fallback to equity_curve
        if portfolio.max_drawdown_usd > 0 or not portfolio.equity_curve:
            max_drawdown_usd = portfolio.max_drawdown_usd
            max_drawdown_percent = portfolio.max_drawdown_pct
        else:
            max_drawdown_usd = 0.0
            max_drawdown_percent = 0.0
            peak_equity = portfolio.initial_balance

            for step in portfolio.equity_curve:
                equity = step["equity"]
                if equity > peak_equity:
                    peak_equity = equity
                dd_usd = peak_equity - equity
                dd_pct = (dd_usd / peak_equity) * 100.0 if peak_equity > 0 else 0.0
                
                if dd_usd > max_drawdown_usd:
                    max_drawdown_usd = dd_usd
                if dd_pct > max_drawdown_percent:
                    max_drawdown_percent = dd_pct

        # Average holding hours
        avg_holding_hours = sum(c.holding_hours for c in closed) / total_cycles

        # DCA stats
        total_dca_layers = sum(c.num_dca_layers for c in closed)
        avg_dca_layers = total_dca_layers / total_cycles
        max_dca_reached = max((c.num_dca_layers for c in closed), default=0)

        # Close reasons breakdown
        reasons = {}
        for c in closed:
            reasons[c.close_reason] = reasons.get(c.close_reason, 0) + 1

        # Export ML Features
        ml_data = []
        for c in closed:
            if c.ml_features:
                if c.symbol == "XAUUSD":
                    mae = getattr(c, "max_adverse_excursion", 0.0)
                    is_win = 0 if mae > 25.0 else 1
                else:
                    is_win = 1 if c.current_profit_usd > 0 else 0
                
                row = {
                    "symbol": c.symbol,
                    "direction": c.direction,
                    "entry_time": c.entry_time.isoformat(),
                    "session": c.session,
                    "profit_usd": c.current_profit_usd,
                    "is_win": is_win,
                    **c.ml_features
                }
                ml_data.append(row)
        
        if ml_data and not skip_ml_export:
            df_ml = pd.DataFrame(ml_data)
            ml_file = settings.PROJECT_ROOT / "logs" / "training_data.csv"
            df_ml.to_csv(ml_file, index=False)

        return {
            "initial_balance": portfolio.initial_balance,
            "final_balance": portfolio.balance,
            "total_profit_usd": round(total_profit, 2),
            "profit_percent": round(profit_percent, 2),
            "total_cycles": total_cycles,
            "win_rate": round(win_rate, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_usd": round(max_drawdown_usd, 2),
            "max_drawdown_percent": round(max_drawdown_percent, 2),
            "avg_holding_hours": round(avg_holding_hours, 1),
            "avg_dca_layers": round(avg_dca_layers, 2),
            "max_dca_reached": max_dca_reached,
            "reasons": reasons,
        }
