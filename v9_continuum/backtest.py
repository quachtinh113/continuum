import os
import sys
import math
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from v9_continuum.config import matrix_config
from v9_continuum.core.governor import PortfolioGovernor
from v9_continuum.layers.regime import (
    fit_ou_process, KalmanFilterTracker, EuropeRegimeDetector,
    calculate_kama, calculate_adx, MarketRegime, calculate_rsi
)
from v9_continuum.layers.position import PositionSizer
from v9_continuum.layers.signal import SMCEngine, MLSignalEngine, Signal
from src.session_manager import get_current_session, is_weekend, Session
from config.symbols import get_symbol_spec, get_all_symbols

def get_backtest_spread_pips(symbol: str, current_hour: int) -> float:
    """Simulates rollover spread widening (21:00 - 22:00 UTC)."""
    is_rollover = (21 <= current_hour < 22)
    spec = get_symbol_spec(symbol)
    if spec.category == "FX":
        return 3.0 if is_rollover else 1.0
    elif spec.category in ["GOLD", "COMMODITY"]:
        return 80.0 if is_rollover else 20.0
    return 4.0 if is_rollover else 1.5


def calculate_actual_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculates the standard Average True Range (ATR)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


class V9VirtualPortfolio:
    """Tracks account balance, equity, drawdowns, and active positions during backtest."""
    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.start_of_day_balance = initial_balance
        self.active_cycles: Dict[str, Dict[str, Any]] = {}
        self.closed_cycles: List[Dict[str, Any]] = []
        
        self.peak_equity = initial_balance
        self.max_drawdown_usd = 0.0
        self.max_drawdown_pct = 0.0

    def update_equity(self, current_prices: Dict[str, float], current_time: datetime):
        floating_pnl = 0.0
        for symbol, cycle in self.active_cycles.items():
            price = current_prices.get(symbol, cycle["entry_price"])
            
            spec = get_symbol_spec(symbol)
            diff = (price - cycle["entry_price"]) if cycle["direction"] == "BUY" else (cycle["entry_price"] - price)
            
            # DCA layers
            total_lots = cycle["base_lot"]
            layer_pnl = 0.0
            for layer in cycle["dca_layers"]:
                total_lots += layer["lot"]
                l_diff = (price - layer["price"]) if cycle["direction"] == "BUY" else (layer["price"] - price)
                layer_pnl += l_diff * layer["lot"] * spec.contract_size

            base_pnl = diff * cycle["base_lot"] * spec.contract_size
            cycle_pnl = base_pnl + layer_pnl
            
            # Convert to USD if JPY/CHF/CAD quote currency
            if symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD"):
                cycle_pnl = cycle_pnl / price

            cycle["floating_pnl"] = cycle_pnl
            floating_pnl += cycle_pnl

        self.equity = self.balance + floating_pnl
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        
        dd_usd = self.peak_equity - self.equity
        dd_pct = (dd_usd / self.peak_equity) * 100.0 if self.peak_equity > 0 else 0.0
        
        self.max_drawdown_usd = max(self.max_drawdown_usd, dd_usd)
        self.max_drawdown_pct = max(self.max_drawdown_pct, dd_pct)


class V9ContinuumBacktester:
    """Historical backtest simulator mirroring the exact V9 Continuum rules."""
    def __init__(self, data_dir: str = "data/historical", base_target_usd: float = 180.0, risk_percent: float = 0.15, dca_multiplier_scale: float = 1.0, ml_veto_threshold: float = 0.60, ml_extend_threshold: float = 0.40, ml_cut_threshold: float = 0.65):
        self.data_dir = Path(data_dir)
        self.base_target_usd = base_target_usd
        self.risk_percent = risk_percent
        self.dca_multiplier_scale = dca_multiplier_scale
        self.ml_veto_threshold = ml_veto_threshold
        self.ml_extend_threshold = ml_extend_threshold
        self.ml_cut_threshold = ml_cut_threshold
        self.governor = PortfolioGovernor()
        self.position_sizer = PositionSizer()
        self.smc_engine = SMCEngine()
        self.ml_engine = MLSignalEngine()
        self.europe_detector = EuropeRegimeDetector()
        
        self.kalman_trackers: Dict[str, KalmanFilterTracker] = {}

    def prepare_data(self, symbol: str) -> Optional[pd.DataFrame]:
        f_m15 = self.data_dir / f"{symbol}_M15.csv"
        f_h1 = self.data_dir / f"{symbol}_H1.csv"
        f_h4 = self.data_dir / f"{symbol}_H4.csv"
        
        if not (f_m15.exists() and f_h1.exists() and f_h4.exists()):
            return None
            
        df_m15 = pd.read_csv(f_m15)
        df_h1 = pd.read_csv(f_h1)
        df_h4 = pd.read_csv(f_h4)
        
        df_m15["time"] = pd.to_datetime(df_m15["time"], utc=True)
        df_h1["time"] = pd.to_datetime(df_h1["time"], utc=True)
        df_h4["time"] = pd.to_datetime(df_h4["time"], utc=True)
        
        # Calculate indicators look-ahead free
        df_h4["RSI_H4"] = calculate_rsi(df_h4["close"], period=14)
        df_h4["available_time"] = df_h4["time"] + pd.Timedelta(hours=4)
        df_h4_shifted = df_h4[["available_time", "RSI_H4"]].set_index("available_time")
        
        df_h1["ADX"] = calculate_adx(df_h1["high"], df_h1["low"], df_h1["close"])
        df_h1["ATR"] = calculate_actual_atr(df_h1["high"], df_h1["low"], df_h1["close"], period=14)
        df_h1["KAMA"] = calculate_kama(df_h1["close"])
        df_h1["RSI_H1"] = calculate_rsi(df_h1["close"], period=14)
        
        df_h1["available_time"] = df_h1["time"] + pd.Timedelta(hours=1)
        df_h1_shifted = df_h1[["available_time", "ADX", "ATR", "KAMA", "RSI_H1"]].set_index("available_time")
        
        df_m15["RSI_M15"] = calculate_rsi(df_m15["close"], period=14)
        df_m15["available_time"] = df_m15["time"] + pd.Timedelta(minutes=15)
        df_m15_shifted = df_m15.set_index("available_time")
        
        # Join
        master = df_m15_shifted.join(df_h1_shifted, how="left")
        master = master.join(df_h4_shifted, how="left").ffill().dropna()
        
        # Calculate RSI_Delta and Volatility_Index
        master["RSI_Delta"] = master["RSI_H4"] - master["RSI_M15"]
        master["Volatility_Index"] = master["ATR"] / master["close"]
        
        master["symbol"] = symbol
        return master.reset_index()

    def run(self, symbols: List[str], start_date: datetime, end_date: datetime, initial_balance: float = 10000.0) -> Tuple[V9VirtualPortfolio, Dict[str, Any]]:
        # Load and align
        print("Loading and preparing historical indicators...")
        symbol_dfs = []
        for s in symbols:
            df = self.prepare_data(s)
            if df is not None:
                df = df[(df["available_time"] >= start_date) & (df["available_time"] <= end_date)]
                if not df.empty:
                    symbol_dfs.append(df)
        
        if not symbol_dfs:
            raise ValueError("No data found for symbols in the date range.")

        combined = pd.concat(symbol_dfs, ignore_index=True).sort_values(by=["available_time", "symbol"])
        records = combined.to_dict(orient="records")
        
        # Group by time
        grouped = {}
        for r in records:
            t = r["available_time"]
            if t not in grouped:
                grouped[t] = []
            grouped[t].append(r)
            
        sorted_times = sorted(grouped.keys())
        portfolio = V9VirtualPortfolio(initial_balance)
        
        # Rolling history container: symbol -> list of dicts
        history_records: Dict[str, List[Dict[str, Any]]] = {s: [] for s in symbols}
        
        print(f"Running chronological simulation on {len(records)} bars across {len(sorted_times)} time steps...")
        
        last_date = None
        day_drawdown_locked = False
        
        for step_idx, t_stamp in enumerate(sorted_times):
            current_time = t_stamp.to_pydatetime().replace(tzinfo=timezone.utc) if hasattr(t_stamp, "to_pydatetime") else t_stamp
            current_date = current_time.strftime("%Y-%m-%d")
            
            # Reset daily variables on day change
            if last_date is None or current_date != last_date:
                portfolio.start_of_day_balance = portfolio.balance
                day_drawdown_locked = False
                last_date = current_date

            step_data = grouped[t_stamp]
            current_prices = {r["symbol"]: r["close"] for r in step_data}
            indicators_map = {r["symbol"]: r for r in step_data}
            
            # Update rolling history
            for r in step_data:
                sym = r["symbol"]
                history_records[sym].append(r)
                if len(history_records[sym]) > 100:
                    history_records[sym].pop(0)

            # Update Kalman filters on each step
            z_scores_map = {}
            for r in step_data:
                sym = r["symbol"]
                if sym not in self.kalman_trackers:
                    self.kalman_trackers[sym] = KalmanFilterTracker()
                _, z_score = self.kalman_trackers[sym].update(r["close"])
                z_scores_map[sym] = z_score

            # Update portfolio equity
            portfolio.update_equity(current_prices, current_time)
            
            # Check Daily Drawdown limit (3%)
            if not day_drawdown_locked and portfolio.start_of_day_balance > 0.0:
                dd_pct = 100.0 * (portfolio.start_of_day_balance - portfolio.equity) / portfolio.start_of_day_balance
                if dd_pct >= matrix_config.max_daily_drawdown_percent:
                    day_drawdown_locked = True
                    # Close all positions immediately
                    active_keys = list(portfolio.active_cycles.keys())
                    for sym in active_keys:
                        close_price = current_prices.get(sym, portfolio.active_cycles[sym]["entry_price"])
                        self.close_position(sym, portfolio, close_price, current_time, "DAILY_DRAWDOWN_CUT")

            # ── 1. Manage Active Positions (TP, SL, 12H, 24H Exits & DCA) ──
            active_symbols = list(portfolio.active_cycles.keys())
            for sym in active_symbols:
                if sym not in current_prices:
                    continue
                    
                cycle = portfolio.active_cycles[sym]
                current_price = current_prices[sym]
                row = indicators_map[sym]
                
                # Elapsed holding time
                elapsed = current_time - cycle["entry_time"]
                cycle["holding_hours"] = elapsed.total_seconds() / 3600.0
                
                # Calculate average entry price and total lots across all DCA layers
                total_lots = cycle["base_lot"] + sum(l["lot"] for l in cycle["dca_layers"])
                total_cost = cycle["entry_price"] * cycle["base_lot"] + sum(l["price"] * l["lot"] for l in cycle["dca_layers"])
                avg_entry_price = total_cost / total_lots
                
                # Retrieve spread cost and commission based on total lots
                spread_pips = get_backtest_spread_pips(sym, current_time.hour)
                spread_usd, commission = self.get_costs(sym, total_lots, spread_pips, current_price)
                
                # Net take profit check
                net_tp_target = self.position_sizer.calculate_target_exit_price(
                    cycle["direction"],
                    avg_entry_price,
                    total_lots,
                    sym,
                    target_gross_usd=(15.0 if get_symbol_spec(sym).category == "INDEX" else self.base_target_usd) * (total_lots / cycle["base_lot"]),
                    spread_cost_realtime=spread_usd,
                    commission=commission
                )
                
                is_tp_hit = False
                if cycle["direction"] == "BUY" and row["high"] >= net_tp_target:
                    is_tp_hit = True
                elif cycle["direction"] == "SELL" and row["low"] <= net_tp_target:
                    is_tp_hit = True

                if is_tp_hit and cycle["holding_hours"] > 1.0:
                    self.close_position(sym, portfolio, net_tp_target, current_time, "TAKE_PROFIT")
                    continue

                # 12-Hour cognitive ML cutoff rule
                if cycle["holding_hours"] >= matrix_config.holding_reduce_hours:
                    # ML score features
                    session_map = {"ASIA": 0, "EUROPE": 1, "US": 2, "OVERLAP_ASIA_EU": 3, "OVERLAP_EU_US": 4, "OFF": -1}
                    feat = {
                        "RSI_M15": row.get("RSI_M15", 50.0),
                        "RSI_H1": row.get("RSI_H1", 50.0),
                        "RSI_H4": row.get("RSI_H4", 50.0),
                        "ADX": row.get("ADX", 20.0),
                        "ATR": cycle["atr"],
                        "RSI_Delta": row.get("RSI_Delta", 0.0),
                        "Volatility_Index": cycle["atr"] / current_price,
                        "hour": current_time.hour,
                        "Session_Code": session_map.get(session.value if hasattr(session, "value") else str(session), -1),
                        "RSI_H1_Div": abs(row.get("RSI_H1", 50.0) - 50.0),
                        "Trend_Vol_Ratio": row.get("ADX", 20.0) * cycle["atr"]
                    }
                    risk_score = self.ml_engine.predict_loss_probability(feat)
                    
                    max_hours = matrix_config.max_holding_hours if cycle["is_extended"] else matrix_config.holding_reduce_hours
                    
                    if cycle["holding_hours"] >= max_hours:
                        if not cycle["is_extended"] and risk_score < self.ml_extend_threshold:
                            cycle["is_extended"] = True
                        elif self.ml_extend_threshold <= risk_score <= self.ml_cut_threshold:
                            # Indecision: reduce DCA layers if any, otherwise cut
                            if cycle["dca_layers"]:
                                worst_layer = cycle["dca_layers"].pop(0) # close oldest dca layer
                                # realize partial loss
                                spec = get_symbol_spec(sym)
                                l_diff = (current_price - worst_layer["price"]) if cycle["direction"] == "BUY" else (worst_layer["price"] - current_price)
                                layer_loss = l_diff * worst_layer["lot"] * spec.contract_size
                                if sym.endswith("JPY") or sym.endswith("CHF") or sym.endswith("CAD"):
                                    layer_loss = layer_loss / current_price
                                portfolio.balance += layer_loss
                            else:
                                self.close_position(sym, portfolio, current_price, current_time, "12H_ML_CUT")
                        else:
                            # High risk or timeout: CUT ALL
                            self.close_position(sym, portfolio, current_price, current_time, "12H_ML_CUT")
                            continue

                # 24H Hard time stop
                if cycle["holding_hours"] >= 24.0:
                    self.close_position(sym, portfolio, current_price, current_time, "24H_HARD_CUT")
                    continue

                # DCA spacings check (widened for JPY and Indices to avoid premature filling)
                dca_multiplier = 1.0 * self.dca_multiplier_scale
                if "JPY" in sym or sym == "XAUUSD":
                    dca_multiplier = 1.8 * self.dca_multiplier_scale
                elif sym in ["US500", "US100", "BTCUSD"]:
                    dca_multiplier = 1.5 * self.dca_multiplier_scale
                spacing = cycle["atr"] * dca_multiplier
                should_dca = False
                
                if cycle["direction"] == "BUY" and current_price <= (cycle["entry_price"] - spacing * (len(cycle["dca_layers"]) + 1)):
                    should_dca = True
                elif cycle["direction"] == "SELL" and current_price >= (cycle["entry_price"] + spacing * (len(cycle["dca_layers"]) + 1)):
                    should_dca = True

                if should_dca and len(cycle["dca_layers"]) < 3 and not day_drawdown_locked:
                    # Place DCA order
                    dca_lot = cycle["base_lot"] # 1:1 lot multiplier
                    cycle["dca_layers"].append({
                        "price": current_price,
                        "lot": dca_lot,
                        "time": current_time
                    })

            # ── 2. Evaluate entries (only at the first bar of each hour) ──
            if not day_drawdown_locked and current_time.minute == 0 and not is_weekend(current_time):
                session = get_current_session(current_time)
                if session != Session.OFF:
                    candidate_tokens = []
                    
                    for row in step_data:
                        sym = row["symbol"]
                        if sym in portfolio.active_cycles:
                            continue
                            
                        # Need at least 50 historical bars to calculate KAMA / OU process
                        if len(history_records[sym]) < 50:
                            continue
                            
                        df_history = pd.DataFrame(history_records[sym])
                        close_prices = df_history["close"].values
                        
                        # Evaluate session-specific logic
                        sig_val = Signal.HOLD
                        reason = "No signal"
                        
                        adx_val = row.get("ADX", 20.0)
                        atr_val = row.get("ATR", 0.001)
                        spread = get_backtest_spread_pips(sym, current_time.hour)
                        
                        # 1. ASIA Session Mean Reversion (Ornstein-Uhlenbeck + Kalman Z-score)
                        if session in [Session.ASIA, Session.OVERLAP_ASIA_EU]:
                            theta, mu, sigma = fit_ou_process(close_prices)
                            if theta > 0:
                                z_score = z_scores_map[sym]
                                if z_score < -2.0:
                                    sig_val = Signal.BUY
                                    reason = f"Kalman Z-Score {z_score:.2f} < -2.0 (Oversold)"
                                elif z_score > 2.0:
                                    sig_val = Signal.SELL
                                    reason = f"Kalman Z-Score {z_score:.2f} > 2.0 (Overbought)"
                                
                        # 2. EUROPE Session HMM + SMC Structure (OB/FVG)
                        elif session in [Session.EUROPE, Session.OVERLAP_EU_US]:
                            returns = np.diff(close_prices) / close_prices[:-1]
                            regime = self.europe_detector.detect_regime(returns)
                            
                            # Only execute when Europe is in Trend/Expansion mode
                            if regime == MarketRegime.EXPANSION:
                                sig_val, reason = self.smc_engine.evaluate_smc_signal(df_history)
                                    
                        # 3. US Session Momentum (KAMA + Dynamic ADX)
                        elif session == Session.US:
                            kama_series = df_history["KAMA"]
                            if len(kama_series) >= 2:
                                kama_curr = kama_series.iloc[-1]
                                kama_prev = kama_series.iloc[-2]
                                
                                if adx_val >= 25.0:
                                    if kama_curr > kama_prev:
                                        sig_val = Signal.BUY
                                        reason = f"US Momentum: KAMA rising and ADX {adx_val:.1f}"
                                    elif kama_curr < kama_prev:
                                        sig_val = Signal.SELL
                                        reason = f"US Momentum: KAMA falling and ADX {adx_val:.1f}"

                        if sig_val != Signal.HOLD:
                            # XGBoost confirming filter
                            session_map = {"ASIA": 0, "EUROPE": 1, "US": 2, "OVERLAP_ASIA_EU": 3, "OVERLAP_EU_US": 4, "OFF": -1}
                            feat = {
                                "RSI_M15": row.get("RSI_M15", 50.0),
                                "RSI_H1": row.get("RSI_H1", 50.0),
                                "RSI_H4": row.get("RSI_H4", 50.0),
                                "ADX": adx_val,
                                "ATR": atr_val,
                                "RSI_Delta": row.get("RSI_Delta", 0.0),
                                "Volatility_Index": atr_val / row["close"],
                                "hour": current_time.hour,
                                "Session_Code": session_map.get(session.value if hasattr(session, "value") else str(session), -1),
                                "RSI_H1_Div": abs(row.get("RSI_H1", 50.0) - 50.0),
                                "Trend_Vol_Ratio": adx_val * atr_val
                            }
                            loss_prob = self.ml_engine.predict_loss_probability(feat)
                            if loss_prob > self.ml_veto_threshold:
                                # Vetoed
                                continue

                            token = {
                                "symbol": sym,
                                "direction": sig_val.value,
                                "adx": adx_val,
                                "spread": spread,
                                "atr": atr_val,
                                "reason": reason,
                                "price": row["close"]
                            }
                            candidate_tokens.append(token)

                    # Governor async token queue resolution
                    winner = self.governor.process_token_queue(candidate_tokens)
                    if winner:
                        sym = winner["symbol"]
                        
                        # Governor portfolio checks
                        active_list = [{"symbol": k} for k in portfolio.active_cycles.keys()]
                        approved, _ = self.governor.evaluate_risk_matrix(
                            sym,
                            active_list,
                            portfolio.equity,
                            portfolio.start_of_day_balance,
                            current_time.timestamp()
                        )
                        
                        if approved:
                            # Sizer - reduced risk_percent from 0.5% to 0.15% to buffer the 3% drawdown limit
                            lot_size = self.position_sizer.calculate_lot_size(
                                portfolio.equity, winner["atr"], sym, risk_percent=self.risk_percent
                            )
                            # Normalization step simulated
                            lot_size = max(0.01, round(lot_size, 2))
                            
                            portfolio.active_cycles[sym] = {
                                "symbol": sym,
                                "direction": winner["direction"],
                                "entry_price": winner["price"],
                                "base_lot": lot_size,
                                "entry_time": current_time,
                                "dca_layers": [],
                                "holding_hours": 0.0,
                                "atr": winner["atr"],
                                "is_extended": False,
                                "floating_pnl": 0.0
                            }

        # Calculate final metrics
        metrics = self._calculate_metrics(portfolio)
        return portfolio, metrics

    def get_costs(self, symbol: str, lot: float, spread_pips: float, price: float) -> Tuple[float, float]:
        spec = get_symbol_spec(symbol)
        pip_val_usd = spec.pip_size * spec.contract_size
        if symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD"):
            pip_val_usd = pip_val_usd / price
        spread_usd = spread_pips * pip_val_usd * lot
        commission = 7.0 * lot # raw spread Exness commission
        return spread_usd, commission

    def close_position(self, symbol: str, portfolio: V9VirtualPortfolio, exit_price: float, time: datetime, reason: str):
        cycle = portfolio.active_cycles.pop(symbol, None)
        if not cycle:
            return
            
        spec = get_symbol_spec(symbol)
        diff = (exit_price - cycle["entry_price"]) if cycle["direction"] == "BUY" else (cycle["entry_price"] - exit_price)
        
        total_lots = cycle["base_lot"]
        layer_pnl = 0.0
        for layer in cycle["dca_layers"]:
            total_lots += layer["lot"]
            l_diff = (exit_price - layer["price"]) if cycle["direction"] == "BUY" else (layer["price"] - exit_price)
            layer_pnl += l_diff * layer["lot"] * spec.contract_size

        base_pnl = diff * cycle["base_lot"] * spec.contract_size
        total_pnl = base_pnl + layer_pnl
        
        if symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD"):
            total_pnl = total_pnl / exit_price

        # Realize commissions and slippage/spread costs
        spread_pips = get_backtest_spread_pips(symbol, time.hour)
        spread_usd, commission = self.get_costs(symbol, total_lots, spread_pips, exit_price)
        
        final_pnl = total_pnl - spread_usd - commission
        portfolio.balance += final_pnl
        
        cycle["exit_price"] = exit_price
        cycle["exit_time"] = time
        cycle["close_reason"] = reason
        cycle["final_pnl"] = final_pnl
        cycle["num_dca_layers"] = len(cycle["dca_layers"])
        
        portfolio.closed_cycles.append(cycle)

    def _calculate_metrics(self, portfolio: V9VirtualPortfolio) -> Dict[str, Any]:
        closed = portfolio.closed_cycles
        total_cycles = len(closed)
        
        if total_cycles == 0:
            return {
                "initial_balance": portfolio.initial_balance,
                "final_balance": portfolio.balance,
                "total_profit_usd": 0.0,
                "profit_percent": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_usd": portfolio.max_drawdown_usd,
                "max_drawdown_percent": portfolio.max_drawdown_pct,
                "total_cycles": 0,
                "avg_holding_hours": 0.0,
                "avg_dca_layers": 0.0,
                "max_dca_reached": 0,
                "reasons": {}
            }

        wins = [c for c in closed if c["final_pnl"] > 0]
        losses = [c for c in closed if c["final_pnl"] <= 0]
        
        win_rate = (len(wins) / total_cycles) * 100.0
        
        gross_profit = sum(c["final_pnl"] for c in wins)
        gross_loss = abs(sum(c["final_pnl"] for c in losses))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        
        avg_holding = np.mean([c["holding_hours"] for c in closed])
        avg_dca = np.mean([c["num_dca_layers"] for c in closed])
        max_dca = max([c["num_dca_layers"] for c in closed]) if closed else 0
        
        reasons = {}
        for c in closed:
            r = c["close_reason"]
            reasons[r] = reasons.get(r, 0) + 1
            
        total_profit = portfolio.balance - portfolio.initial_balance
        profit_pct = (total_profit / portfolio.initial_balance) * 100.0
        
        return {
            "initial_balance": portfolio.initial_balance,
            "final_balance": portfolio.balance,
            "total_profit_usd": total_profit,
            "profit_percent": profit_pct,
            "win_rate": win_rate,
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 99.9,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "max_drawdown_usd": portfolio.max_drawdown_usd,
            "max_drawdown_percent": portfolio.max_drawdown_pct,
            "total_cycles": total_cycles,
            "avg_holding_hours": round(float(avg_holding), 1),
            "avg_dca_layers": round(float(avg_dca), 2),
            "max_dca_reached": max_dca,
            "reasons": reasons
        }


def run_1y_backtest():
    tester = V9ContinuumBacktester()
    
    # 1 Year range
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)
    start_date = end_date - timedelta(days=365)
    
    symbols_to_test = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US100", "US500", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
    available_symbols = []
    for s in symbols_to_test:
        if (Path("data/historical") / f"{s}_M15.csv").exists():
            available_symbols.append(s)
            
    print(f"Backtesting V9 Continuum Strategy for {available_symbols}")
    print(f"Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    portfolio, metrics = tester.run(available_symbols, start_date, end_date, initial_balance=10000.0)
    
    print("\n" + "="*60)
    print("                 V9 CONTINUUM BACKTEST SUMMARY")
    print("="*60)
    print(f" Initial Balance  : ${metrics['initial_balance']:,.2f}")
    print(f" Final Balance    : ${metrics['final_balance']:,.2f}")
    print(f" Net Profit       : ${metrics['total_profit_usd']:+,.2f} ({metrics['profit_percent']:+,.2f}%)")
    print(f" Win Rate         : {metrics['win_rate']:.2f}%")
    print(f" Profit Factor    : {metrics['profit_factor']}")
    print(f" Max Drawdown     : ${metrics['max_drawdown_usd']:,.2f} ({metrics['max_drawdown_percent']:.2f}%)")
    print(f" Avg Cycle Length : {metrics['avg_holding_hours']} hours")
    print(f" Avg DCA Layers   : {metrics['avg_dca_layers']}")
    print(f" Max DCA Reached  : {metrics['max_dca_reached']} / 3")
    print("-" * 60)
    print(" Close Reasons Breakdown:")
    for reason, count in metrics["reasons"].items():
        print(f"   - {reason:<20}: {count} ({count/metrics['total_cycles']*100:.1f}%)")
    print("=" * 60 + "\n")

    # Save Markdown report
    report_file = PROJECT_ROOT / "v9_continuum_backtest_report.md"
    reasons_table = "| Reason | Count | Percentage |\n| :--- | :--- | :--- |\n"
    for reason, count in metrics["reasons"].items():
        reasons_table += f"| {reason} | {count} | {count/metrics['total_cycles']*100:.1f}% |\n"

    trades_table = "| Time | Symbol | Direction | Entry Px | Exit Px | DCA | Holding | Net P&L | Reason |\n"
    trades_table += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    for c in reversed(portfolio.closed_cycles[-50:]):
        trades_table += (
            f"| {c['entry_time'].strftime('%m-%d %H:%M')} | {c['symbol']} | {c['direction']} | "
            f"{c['entry_price']:.5f} | {c.get('exit_price', 0.0):.5f} | {c['num_dca_layers']} | "
            f"{c['holding_hours']:.1f}h | {c['final_pnl']:+.2f} USD | {c['close_reason']} |\n"
        )

    content = f"""# V9 Continuum 1-Year Backtest Report

Generated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")} UTC

## Simulation Settings
* **Start Date**: {start_date.strftime('%Y-%m-%d')}
* **End Date**: {end_date.strftime('%Y-%m-%d')}
* **Symbols Evaluated**: `{available_symbols}`
* **Initial Balance**: $10,000.00

## Performance Summary
| Metric | Value |
| :--- | :--- |
| **Initial Balance** | ${metrics['initial_balance']:,.2f} |
| **Final Balance** | ${metrics['final_balance']:,.2f} |
| **Net Profit** | **${metrics['total_profit_usd']:+,.2f} ({metrics['profit_percent']:+,.2f}%)** |
| **Win Rate** | {metrics['win_rate']:.2f}% |
| **Gross Profit** | ${metrics['gross_profit']:,.2f} |
| **Gross Loss** | ${metrics['gross_loss']:,.2f} |
| **Profit Factor** | {metrics['profit_factor']} |
| **Max Drawdown (Equity)** | ${metrics['max_drawdown_usd']:,.2f} ({metrics['max_drawdown_percent']:.2f}%) |
| **Avg Cycle Length** | {metrics['avg_holding_hours']} hours |
| **Avg DCA Layers** | {metrics['avg_dca_layers']} |
| **Max DCA Layers Reached** | {metrics['max_dca_reached']} / 3 |

## Close Reasons
{reasons_table}

## Last 50 Closed Cycles
{trades_table}
"""
    report_file.write_text(content, encoding="utf-8")
    print(f"Detailed report saved successfully to {report_file.absolute()}")


if __name__ == "__main__":
    run_1y_backtest()
