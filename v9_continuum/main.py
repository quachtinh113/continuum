import os
import sys
import time
import signal as sig
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

# Add workspace to path to allow importing from workspace root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from src.mt5_connector import MT5Connector
from src.session_manager import get_current_session, is_weekend, is_market_closing_soon, Session
from src.audit_logger import log_info, log_error, log_decision, log_cycle_event

class RiskDecision:
    def __init__(self, approved: bool, reason: str, severity: str = "INFO"):
        self.approved = approved
        self.reason = reason
        self.severity = severity
        self.status_str = "APPROVED" if approved else "VETOED"


from v9_continuum.config import matrix_config
from v9_continuum.core.governor import PortfolioGovernor
from v9_continuum.layers.regime import (
    fit_ou_process, KalmanFilterTracker, EuropeRegimeDetector,
    calculate_kama, calculate_adx, MarketRegime, calculate_rsi
)
from v9_continuum.layers.execution import ExecutionEngine
from v9_continuum.layers.position import PositionSizer
from v9_continuum.layers.signal import SMCEngine, MLSignalEngine, Signal

# ── Graceful Shutdown Handler ──────────────────────────────────────
_running = True


def _shutdown_handler(signum, frame):
    global _running
    log_info("⛔ Shutdown signal received in V9 Continuum. Exiting loop...")
    _running = False


class V9ContinuumBot:
    """
    Main V9 Continuum Trading Loop Orchestrator.
    """
    def __init__(self):
        self.connector = MT5Connector()
        self.execution = ExecutionEngine(self.connector)
        self.position_sizer = PositionSizer()
        self.governor = PortfolioGovernor()
        
        self.smc_engine = SMCEngine()
        self.ml_engine = MLSignalEngine()
        self.europe_detector = EuropeRegimeDetector()
        
        # State tracking
        self.active_cycles: Dict[str, Dict[str, Any]] = {}
        self.start_of_day_balance = 0.0
        self.last_balance_update_day = None
        
        # Kalman filter instances for Asia Session: symbol -> tracker
        self.kalman_trackers: Dict[str, KalmanFilterTracker] = {}
        
        # Symbol list
        from config.symbols import get_all_symbols
        self.symbols = get_all_symbols()
        # Fallback to a core set if empty
        if not self.symbols:
            self.symbols = ["XAUUSD", "EURUSD", "GBPUSD", "US30", "US100"]

    def get_hard_sl_multiplier(self, category: str) -> float:
        """Get Hard SL multiplier based on symbol's category."""
        if category == "FX":
            return settings.SL_MULTIPLIER_FX
        elif category == "GOLD":
            return settings.SL_MULTIPLIER_GOLD
        elif category == "CRYPTO":
            return settings.SL_MULTIPLIER_CRYPTO
        elif category == "INDEX":
            return settings.SL_MULTIPLIER_INDEX
        return 4.0

    def update_daily_balance(self, current_balance: float):
        """Resets the start of day balance on day changes."""
        today = datetime.now(timezone.utc).date()
        if self.last_balance_update_day != today:
            self.start_of_day_balance = current_balance
            self.last_balance_update_day = today
            # Reset Governor to OPERATIONAL when day changes
            self.governor.system_status = "OPERATIONAL"
            log_info(f"📅 Daily reset: Start of Day Balance set to ${self.start_of_day_balance:.2f}. Governor status reset to OPERATIONAL")

    def evaluate_symbol_signal(
        self,
        symbol: str,
        session: Session,
        rates_m15: pd.DataFrame,
        rates_h1: pd.DataFrame
    ) -> Tuple[Signal, str, float, float]:
        """
        Determines the entry signal based on the active session's regime model.
        Returns: (Signal, Reason, ADX_value, Spread_value)
        """
        tick = self.connector.get_tick(symbol)
        spread = tick["spread_pips"] if tick else 2.0
        
        # Calculate standard ADX for scoring
        adx_series = calculate_adx(rates_h1["high"], rates_h1["low"], rates_h1["close"])
        adx_val = float(adx_series.iloc[-1]) if not adx_series.empty else 20.0

        close_prices = rates_m15["close"].values
        current_price = close_prices[-1]

        # ── 1. ASIA SESSION: OU Process + Kalman Filter Mean Reversion ──
        if session in [Session.ASIA, Session.OVERLAP_ASIA_EU]:
            theta, mu, sigma = fit_ou_process(close_prices)
            
            # If theta > 0, the price dynamics show mean-reverting behavior
            if theta > 0:
                if symbol not in self.kalman_trackers:
                    self.kalman_trackers[symbol] = KalmanFilterTracker()
                
                kf = self.kalman_trackers[symbol]
                # Update Kalman Filter with closing prices to get Z-score
                for p in close_prices[:-1]:
                    kf.update(p)
                state_est, z_score = kf.update(current_price)
                
                # Mean reversion logic: Buy oversold, Sell overbought
                if z_score < -2.0:
                    return Signal.BUY, f"Asia MR: Kalman Z-Score ({z_score:.2f}) < -2.0 (Oversold)", adx_val, spread
                elif z_score > 2.0:
                    return Signal.SELL, f"Asia MR: Kalman Z-Score ({z_score:.2f}) > 2.0 (Overbought)", adx_val, spread
                return Signal.HOLD, f"Asia MR: Kalman Z-Score ({z_score:.2f}) neutral", adx_val, spread
            else:
                return Signal.HOLD, "Asia MR: Market is not mean-reverting (theta <= 0)", adx_val, spread

        # ── 2. EUROPE SESSION: HMM + SMC ──
        elif session in [Session.EUROPE, Session.OVERLAP_EU_US]:
            returns = np.diff(close_prices) / close_prices[:-1]
            regime = self.europe_detector.detect_regime(returns)
            
            if regime == MarketRegime.EXPANSION:
                # Impulsive expansion - follow trend SMC
                sig_val, reason = self.smc_engine.evaluate_smc_signal(rates_m15)
                return sig_val, f"Europe Expansion: {reason}", adx_val, spread
            else:
                # Accumulation / low-volatility consolidation
                return Signal.HOLD, "Europe Accumulation: Range mode entries disabled", adx_val, spread

        # ── 3. US SESSION: KAMA + ADX Momentum Trend Following ──
        elif session == Session.US:
            kama_series = calculate_kama(rates_h1["close"])
            if len(kama_series) >= 2:
                kama_curr = kama_series.iloc[-1]
                kama_prev = kama_series.iloc[-2]
                
                # ADX trend confirmation
                if adx_val >= 25.0:
                    if kama_curr > kama_prev:
                        return Signal.BUY, f"US Momentum: KAMA rising and ADX ({adx_val:.1f}) >= 25", adx_val, spread
                    elif kama_curr < kama_prev:
                        return Signal.SELL, f"US Momentum: KAMA falling and ADX ({adx_val:.1f}) >= 25", adx_val, spread
                return Signal.HOLD, f"US Session: Trend weak (ADX {adx_val:.1f} < 25)", adx_val, spread

        return Signal.HOLD, "Session is OFF or unrecognized", adx_val, spread

    def process_signals(self, session: Session):
        """
        Scans symbols for signals, routes them to Portfolio Governor queue, and executes trades.
        """
        now_ts = time.time()
        candidate_tokens = []

        for symbol in self.symbols:
            # Skip if already has active position/cycle
            if symbol in self.active_cycles:
                continue

            # Fetch data (default count = 100)
            rates_m15 = self.connector.get_rates(symbol, "M15", 100)
            rates_h1 = self.connector.get_rates(symbol, "H1", 100)
            
            if rates_m15 is None or rates_m15.empty or rates_h1 is None or rates_h1.empty:
                continue

            sig_val, reason, adx_val, spread = self.evaluate_symbol_signal(symbol, session, rates_m15, rates_h1)
            
            if sig_val != Signal.HOLD:
                # Sizing indicators check
                atr_series = rates_h1["close"].diff().abs().rolling(14).mean() # simple ATR proxy
                atr_val = float(atr_series.iloc[-1]) if not atr_series.empty else 0.001
                
                # Fetch indicators for ML
                rates_h4 = self.connector.get_rates(symbol, "H4", 100)
                rsi_m15 = float(calculate_rsi(rates_m15["close"]).iloc[-1]) if rates_m15 is not None and not rates_m15.empty else 50.0
                rsi_h1 = float(calculate_rsi(rates_h1["close"]).iloc[-1]) if rates_h1 is not None and not rates_h1.empty else 50.0
                rsi_h4 = float(calculate_rsi(rates_h4["close"]).iloc[-1]) if rates_h4 is not None and not rates_h4.empty else 50.0
                
                # Check ML Confirmation Filter
                session_map = {"ASIA": 0, "EUROPE": 1, "US": 2, "OVERLAP_ASIA_EU": 3, "OVERLAP_EU_US": 4, "OFF": -1}
                # Normalize ATR by price to keep all assets on the same scale
                normalized_atr = atr_val / rates_m15["close"].iloc[-1]
                
                feat = {
                    "RSI_M15": rsi_m15,
                    "RSI_H1": rsi_h1,
                    "RSI_H4": rsi_h4,
                    "ADX": adx_val,
                    "ATR": normalized_atr, # scaled relative ATR
                    "RSI_Delta": rsi_h4 - rsi_m15,
                    "Volatility_Index": normalized_atr,
                    "hour": datetime.now(timezone.utc).hour,
                    "Session_Code": session_map.get(session.value if hasattr(session, "value") else str(session), -1),
                    "RSI_H1_Div": abs(rsi_h1 - 50.0),
                    "Trend_Vol_Ratio": adx_val * normalized_atr # scaled Trend-Vol Ratio
                }
                
                loss_prob = self.ml_engine.predict_loss_probability(feat)
                if loss_prob > 0.6:
                    log_info(f"🛡️ ML filter vetoed {sig_val.value} entry for {symbol} due to high loss risk ({loss_prob:.2f})")
                    log_decision(symbol, session.value if hasattr(session, "value") else str(session), feat, sig_val.value, RiskDecision(False, f"ML filter vetoed due to loss risk {loss_prob:.2f}"), "VETOED")
                    continue

                token = {
                    "symbol": symbol,
                    "direction": sig_val.value,
                    "adx": adx_val,
                    "spread": spread,
                    "atr": atr_val,
                    "reason": reason,
                    "price": rates_m15["close"].iloc[-1],
                    "loss_prob": loss_prob,
                    "features": feat
                }
                candidate_tokens.append(token)

        # Async Queue: Let the Governor pick the highest-priority signal (e.g. out of correlated entries)
        winner = self.governor.process_token_queue(candidate_tokens)
        if winner:
            symbol = winner["symbol"]
            session_str = session.value if hasattr(session, "value") else str(session)
            
            # Retrieve account status
            acc = self.connector.get_account_info()
            equity = acc["equity"] if acc else 10000.0
            
            # Governor matrix check
            approved, status_msg = self.governor.evaluate_risk_matrix(
                symbol,
                list(self.active_cycles.values()),
                equity,
                self.start_of_day_balance,
                now_ts
            )
            
            if not approved:
                log_info(f"🚫 Governor blocked {winner['direction']} for {symbol}: {status_msg}")
                log_decision(symbol, session_str, winner.get("features"), winner["direction"], RiskDecision(False, f"Governor blocked: {status_msg}"), "BLOCKED")
                return

            log_decision(symbol, session_str, winner.get("features"), winner["direction"], RiskDecision(True, "Approved by Governor"), "ROUTE")

            # Sizing and routing
            lot_size = self.position_sizer.calculate_lot_size(
                equity, winner["atr"], symbol, risk_percent=0.15, ml_score=winner.get("loss_prob")
            )
            
            # Hard-SL based on Asset Class multiplier for catastrophic VPS crash backup
            from config.symbols import get_symbol_spec
            spec = get_symbol_spec(symbol)
            multiplier = self.get_hard_sl_multiplier(spec.category)
            hard_sl_distance = multiplier * winner["atr"]
            hard_sl = winner["price"] - hard_sl_distance if winner["direction"] == "BUY" else winner["price"] + hard_sl_distance
            
            ticket = self.execution.route_order(
                symbol=symbol,
                order_type=winner["direction"],
                lot=lot_size,
                tp=None, 
                sl=hard_sl,
                comment="V9 Continuum Base"
            )
            
            if ticket and ticket != -1:
                self.active_cycles[symbol] = {
                    "symbol": symbol,
                    "direction": winner["direction"],
                    "entry_price": winner["price"],
                    "base_lot": lot_size,
                    "ticket": ticket,
                    "entry_time": datetime.now(timezone.utc),
                    "dca_layers": [],
                    "holding_hours": 0.0,
                    "atr": winner["atr"],
                    "is_extended": False,
                    "features": winner.get("features"),
                    "last_tick": {"spread_pips": winner["spread"]},
                    "trailing_active": False,
                    "extreme_price": winner["price"]
                }
                log_info(f"🚀 Base cycle opened for {symbol} ({winner['direction']}) at {winner['price']}")
                log_cycle_event("CYCLE_OPEN", symbol, winner["direction"], {"price": winner["price"], "lot": lot_size, "ticket": ticket})

    def manage_cycles(self):
        """
        Monitors active positions, checks profit targets, triggers 12H ML time-cutoffs or DCA layers.
        """
        acc = self.connector.get_account_info()
        equity = acc["equity"] if acc else 10000.0
        
        # Check global drawdown switch
        if self.start_of_day_balance > 0.0:
            drawdown = 100.0 * (self.start_of_day_balance - equity) / self.start_of_day_balance
            if drawdown >= matrix_config.max_daily_drawdown_percent:
                if self.active_cycles or self.governor.system_status != "LOCKED":
                    self.governor.system_status = "LOCKED"
                    log_error(f"🚨 Drawdown Limit Breached ({drawdown:.2f}%). Emergency closing all positions and locking system!")
                    self.close_all_positions()
                return
            
            if self.governor.system_status == "LOCKED":
                # If governor is locked but current drawdown is within limit, keep the lock to prevent revenge trading
                return

        now = datetime.now(timezone.utc)
        from src.session_manager import get_current_session
        session = get_current_session(now)
        symbols_to_delete = []

        # Gather real positions from MT5 if live
        positions_map = {pos["ticket"]: pos for pos in self.connector.get_positions()}

        for symbol, cycle in list(self.active_cycles.items()):
            # Calculate holding time
            elapsed = now - cycle["entry_time"]
            cycle["holding_hours"] = elapsed.total_seconds() / 3600.0

            # Get current prices
            tick = self.connector.get_tick(symbol)
            if not tick:
                continue
            
            current_price = tick["ask"] if cycle["direction"] == "BUY" else tick["bid"]
            
            # Sync with broker: if position is closed externally (SL/TP or manually)
            if cycle["ticket"] != -1 and cycle["ticket"] not in positions_map:
                log_info(f"🔄 Active cycle for {symbol} (ticket {cycle['ticket']}) was closed externally (SL/TP or manually). Cleaning up local state.")
                self.record_closed_cycle_to_training_data(cycle, current_price, now, "EXTERNAL_CLOSE")
                log_cycle_event("CYCLE_CLOSE", symbol, cycle["direction"], {"price": current_price, "reason": "EXTERNAL_CLOSE"})
                self.active_cycles.pop(symbol, None)
                continue
            
            # Update extreme price for trailing BE
            if cycle["direction"] == "BUY":
                cycle["extreme_price"] = max(cycle.get("extreme_price", current_price), current_price)
            else:
                cycle["extreme_price"] = min(cycle.get("extreme_price", current_price), current_price)
            
            # Fetch unrealized profit from broker
            # Fallback estimation if dry run
            if cycle["ticket"] == -1:
                from config.symbols import get_symbol_spec
                spec = get_symbol_spec(symbol)
                diff = (current_price - cycle["entry_price"]) if cycle["direction"] == "BUY" else (cycle["entry_price"] - current_price)
                unrealized_profit = diff * cycle["base_lot"] * spec.contract_size
            else:
                pos = positions_map.get(cycle["ticket"])
                unrealized_profit = pos["profit"] if pos else 0.0

            # Calculate average entry price and total lots across all DCA layers
            total_lots = cycle["base_lot"] + sum(l.get("lot", cycle["base_lot"]) for l in cycle["dca_layers"])
            total_cost = cycle["entry_price"] * cycle["base_lot"] + sum(l["entry_price"] * l.get("lot", cycle["base_lot"]) for l in cycle["dca_layers"])
            avg_entry_price = total_cost / total_lots

            # Calculate Spread Cost and Commission
            spread_cost, commission = self.execution.get_realtime_costs(symbol, total_lots, tick["spread_pips"])
            
            # ── 1. Target Profit Check (Net Profit Optimization) ──
            # Scale target profit based on asset class (FX vs Indices)
            from config.symbols import get_symbol_spec
            spec = get_symbol_spec(symbol)
            base_target = 15.0 if spec.category == "INDEX" else 180.0
            target_gross_usd = base_target * (total_lots / cycle["base_lot"])  # Optimized base gross target
            net_profit_target = self.position_sizer.calculate_target_exit_price(
                cycle["direction"],
                avg_entry_price,
                total_lots,
                symbol,
                target_gross_usd,
                spread_cost,
                commission
            )
            
            # Check price threshold triggers
            is_profit_hit = (cycle["direction"] == "BUY" and current_price >= net_profit_target) or \
                             (cycle["direction"] == "SELL" and current_price <= net_profit_target)

            if is_profit_hit and cycle["holding_hours"] > 1.0:
                log_info(f"💰 Net Profit Target met for {symbol}. Closing cycle!")
                self.execution.close_position(cycle["ticket"], symbol)
                for dca in cycle["dca_layers"]:
                    self.execution.close_position(dca["ticket"], symbol)
                self.record_closed_cycle_to_training_data(cycle, current_price, now, "TAKE_PROFIT")
                log_cycle_event("CYCLE_CLOSE", symbol, cycle["direction"], {"price": current_price, "reason": "TAKE_PROFIT"})
                symbols_to_delete.append(symbol)
                continue

            # ── 1.4. Soft ATR Stop Check (2.6 * ATR Dynamic Stop) ──
            rates_h1_sl = self.connector.get_rates(symbol, "H1", 100)
            if rates_h1_sl is not None and not rates_h1_sl.empty:
                atr_series_sl = rates_h1_sl["close"].diff().abs().rolling(14).mean()
                current_atr_sl = float(atr_series_sl.iloc[-1]) if not atr_series_sl.empty else cycle["atr"]
            else:
                current_atr_sl = cycle["atr"]

            soft_stop_distance = 2.6 * current_atr_sl
            is_sl_hit = False
            if cycle["direction"] == "BUY" and current_price <= (avg_entry_price - soft_stop_distance):
                is_sl_hit = True
            elif cycle["direction"] == "SELL" and current_price >= (avg_entry_price + soft_stop_distance):
                is_sl_hit = True

            if is_sl_hit:
                log_info(f"🚨 Soft ATR Stop triggered for {symbol} at {current_price:.5f} (Distance: {soft_stop_distance:.5f} from Avg Entry: {avg_entry_price:.5f}). Closing cycle!")
                self.execution.close_position(cycle["ticket"], symbol)
                for dca in cycle["dca_layers"]:
                    self.execution.close_position(dca["ticket"], symbol)
                self.record_closed_cycle_to_training_data(cycle, current_price, now, "SOFT_ATR_STOP")
                log_cycle_event("CYCLE_CLOSE", symbol, cycle["direction"], {"price": current_price, "reason": "SOFT_ATR_STOP"})
                symbols_to_delete.append(symbol)
                continue

            # ── 1.5. Trailing Break-Even Check ──
            # Fetch H1 indicators for current ATR
            rates_h1_be = self.connector.get_rates(symbol, "H1", 100)
            if rates_h1_be is not None and not rates_h1_be.empty:
                atr_series_be = rates_h1_be["close"].diff().abs().rolling(14).mean()
                current_atr_be = float(atr_series_be.iloc[-1]) if not atr_series_be.empty else cycle["atr"]
            else:
                current_atr_be = cycle["atr"]

            # Minor Liquidity check (Swing High/Low sweep)
            minor_liq_swept = False
            rates_m15_be = self.connector.get_rates(symbol, "M15", 100)
            if rates_m15_be is not None and not rates_m15_be.empty:
                swing_highs, swing_lows = self.smc_engine.find_swings(rates_m15_be)
                if not swing_highs.empty and not swing_lows.empty:
                    last_swing_high = float(swing_highs.iloc[-1])
                    last_swing_low = float(swing_lows.iloc[-1])
                    if cycle["direction"] == "BUY" and last_swing_high > avg_entry_price and current_price >= last_swing_high:
                        minor_liq_swept = True
                    elif cycle["direction"] == "SELL" and last_swing_low < avg_entry_price and current_price <= last_swing_low:
                        minor_liq_swept = True

            # Configuration from Backtest (Task-1096 Tuned)
            activation_distance = 2.5 * current_atr_be
            floor_offset = 0.5 * current_atr_be
            trail_gap = 1.2 * current_atr_be

            is_trailing_exit = False
            if cycle["direction"] == "BUY":
                if not cycle.get("trailing_active", False) and (current_price >= avg_entry_price + activation_distance or minor_liq_swept):
                    cycle["trailing_active"] = True
                    log_info(f"🛡️ Trailing BE Activated for BUY {symbol} (Price {current_price:.5f} >= {avg_entry_price + activation_distance:.5f} or Liq Swept)")
                
                if cycle.get("trailing_active", False):
                    computed_stop = cycle["extreme_price"] - trail_gap
                    floor_stop = avg_entry_price + floor_offset
                    final_trailing_stop = max(computed_stop, floor_stop)
                    if current_price <= final_trailing_stop:
                        is_trailing_exit = True
                        cycle["be_exit_price"] = final_trailing_stop
            else: # SELL
                if not cycle.get("trailing_active", False) and (current_price <= avg_entry_price - activation_distance or minor_liq_swept):
                    cycle["trailing_active"] = True
                    log_info(f"🛡️ Trailing BE Activated for SELL {symbol} (Price {current_price:.5f} <= {avg_entry_price - activation_distance:.5f} or Liq Swept)")
                
                if cycle.get("trailing_active", False):
                    computed_stop = cycle["extreme_price"] + trail_gap
                    floor_stop = avg_entry_price - floor_offset
                    final_trailing_stop = min(computed_stop, floor_stop)
                    if current_price >= final_trailing_stop:
                        is_trailing_exit = True
                        cycle["be_exit_price"] = final_trailing_stop

            if is_trailing_exit:
                be_fill = cycle.get("be_exit_price", avg_entry_price)
                log_info(f"🛡️ Trailing Break-Even exit triggered for {symbol} at {be_fill:.5f}. Closing cycle!")
                self.execution.close_position(cycle["ticket"], symbol)
                for dca in cycle["dca_layers"]:
                    self.execution.close_position(dca["ticket"], symbol)
                self.record_closed_cycle_to_training_data(cycle, current_price, now, "TRAILING_BE_EXIT")
                log_cycle_event("CYCLE_CLOSE", symbol, cycle["direction"], {"price": current_price, "reason": "TRAILING_BE_EXIT"})
                symbols_to_delete.append(symbol)
                continue

            # ── 1.5 High-Frequency ML Risk Check (Soft SL) ──
            if cycle["holding_hours"] >= 1.0:
                current_m5_bar = now.minute // 5
                if current_m5_bar != cycle.get("last_m5_bar"):
                    cycle["last_m5_bar"] = current_m5_bar
                    
                    # Fetch indicators for ML risk evaluation
                    rates_m15_ex = self.connector.get_rates(symbol, "M15", 100)
                    rates_h1_ex = self.connector.get_rates(symbol, "H1", 100)
                    rates_h4_ex = self.connector.get_rates(symbol, "H4", 100)
                    
                    rsi_m15_ex = float(calculate_rsi(rates_m15_ex["close"]).iloc[-1]) if rates_m15_ex is not None and not rates_m15_ex.empty else 50.0
                    rsi_h1_ex = float(calculate_rsi(rates_h1_ex["close"]).iloc[-1]) if rates_h1_ex is not None and not rates_h1_ex.empty else 50.0
                    rsi_h4_ex = float(calculate_rsi(rates_h4_ex["close"]).iloc[-1]) if rates_h4_ex is not None and not rates_h4_ex.empty else 50.0
                    
                    adx_series_ex = calculate_adx(rates_h1_ex["high"], rates_h1_ex["low"], rates_h1_ex["close"]) if rates_h1_ex is not None and not rates_h1_ex.empty else pd.Series()
                    adx_val_ex = float(adx_series_ex.iloc[-1]) if not adx_series_ex.empty else 25.0
                    
                    session_map = {"ASIA": 0, "EUROPE": 1, "US": 2, "OVERLAP_ASIA_EU": 3, "OVERLAP_EU_US": 4, "OFF": -1}
                    feat = {
                        "RSI_M15": rsi_m15_ex,
                        "RSI_H1": rsi_h1_ex,
                        "RSI_H4": rsi_h4_ex,
                        "ADX": adx_val_ex,
                        "ATR": cycle["atr"],
                        "RSI_Delta": rsi_h4_ex - rsi_m15_ex,
                        "Volatility_Index": cycle["atr"] / current_price,
                        "hour": now.hour,
                        "Session_Code": session_map.get(session.value if hasattr(session, "value") else str(session), -1),
                        "RSI_H1_Div": abs(rsi_h1_ex - 50.0),
                        "Trend_Vol_Ratio": adx_val_ex * cycle["atr"]
                    }
                    risk_score = self.ml_engine.predict_loss_probability(feat)
                    
                    if risk_score > 0.70:
                        cycle["high_risk_m5_count"] = cycle.get("high_risk_m5_count", 0) + 1
                        log_info(f"⚠️ {symbol} High Risk Detected ({risk_score:.2f}) - M5 Count: {cycle['high_risk_m5_count']}/3")
                    else:
                        cycle["high_risk_m5_count"] = 0
                        
                    if cycle.get("high_risk_m5_count", 0) >= 3:
                        log_info(f"🚨 Soft ML SL triggered for {symbol} after 3 consecutive high-risk M5 bars. Closing cycle!")
                        self.execution.close_position(cycle["ticket"], symbol)
                        for dca in cycle["dca_layers"]:
                            self.execution.close_position(dca["ticket"], symbol)
                        self.record_closed_cycle_to_training_data(cycle, current_price, now, "SOFT_ML_SL")
                        log_cycle_event("CYCLE_CLOSE", symbol, cycle["direction"], {"price": current_price, "reason": "SOFT_ML_SL"})
                        symbols_to_delete.append(symbol)
                        continue

            # ── 2. Cognitive ML Time-Cutoff (12H Rule Upgrade) ──
            if cycle["holding_hours"] >= matrix_config.holding_reduce_hours:
                # Fetch indicators for ML cutoff evaluation
                rates_m15_ex = self.connector.get_rates(symbol, "M15", 100)
                rates_h1_ex = self.connector.get_rates(symbol, "H1", 100)
                rates_h4_ex = self.connector.get_rates(symbol, "H4", 100)
                
                rsi_m15_ex = float(calculate_rsi(rates_m15_ex["close"]).iloc[-1]) if rates_m15_ex is not None and not rates_m15_ex.empty else 50.0
                rsi_h1_ex = float(calculate_rsi(rates_h1_ex["close"]).iloc[-1]) if rates_h1_ex is not None and not rates_h1_ex.empty else 50.0
                rsi_h4_ex = float(calculate_rsi(rates_h4_ex["close"]).iloc[-1]) if rates_h4_ex is not None and not rates_h4_ex.empty else 50.0
                
                adx_series_ex = calculate_adx(rates_h1_ex["high"], rates_h1_ex["low"], rates_h1_ex["close"]) if rates_h1_ex is not None and not rates_h1_ex.empty else pd.Series()
                adx_val_ex = float(adx_series_ex.iloc[-1]) if not adx_series_ex.empty else 25.0
                
                # Predict risk score
                session_map = {"ASIA": 0, "EUROPE": 1, "US": 2, "OVERLAP_ASIA_EU": 3, "OVERLAP_EU_US": 4, "OFF": -1}
                feat = {
                    "RSI_M15": rsi_m15_ex,
                    "RSI_H1": rsi_h1_ex,
                    "RSI_H4": rsi_h4_ex,
                    "ADX": adx_val_ex,
                    "ATR": cycle["atr"],
                    "RSI_Delta": rsi_h4_ex - rsi_m15_ex,
                    "Volatility_Index": cycle["atr"] / current_price,
                    "hour": now.hour,
                    "Session_Code": session_map.get(session.value if hasattr(session, "value") else str(session), -1),
                    "RSI_H1_Div": abs(rsi_h1_ex - 50.0),
                    "Trend_Vol_Ratio": adx_val_ex * cycle["atr"]
                }
                risk_score = self.ml_engine.predict_loss_probability(feat)

                # Extended time boundary check
                max_hours = matrix_config.max_holding_hours if cycle["is_extended"] else matrix_config.holding_reduce_hours
                
                if cycle["holding_hours"] >= max_hours:
                    if not cycle["is_extended"] and risk_score < 0.4:
                        # Low risk - extend hold by 6h
                        cycle["is_extended"] = True
                        log_info(f"⏰ 12H Cutoff: Low risk ({risk_score:.2f}) for {symbol}. Extending hold by 6 hours.")
                    elif 0.4 <= risk_score <= 0.65:
                        # Indecision - trigger REDUCE_DCA (remove worst DCA layer)
                        # In this simple implementation, we reduce position or close oldest DCA layer
                        if cycle["dca_layers"]:
                            worst_layer = cycle["dca_layers"].pop(0) # close one layer
                            self.execution.close_position(worst_layer["ticket"], symbol)
                            log_info(f"📉 12H Cutoff: Indecision ({risk_score:.2f}) for {symbol}. Removing DCA layer ticket {worst_layer['ticket']}.")
                            log_cycle_event("DCA_CLOSE", symbol, cycle["direction"], {"price": current_price, "ticket": worst_layer["ticket"], "reason": "12H_INDECISION"})
                        else:
                            # No DCA layer, cut whole cycle
                            log_info(f"✂️ 12H Cutoff: Indecision ({risk_score:.2f}) with no DCA layers for {symbol}. Cutting position.")
                            self.execution.close_position(cycle["ticket"], symbol)
                            self.record_closed_cycle_to_training_data(cycle, current_price, now, "12H_INDECISION")
                            log_cycle_event("CYCLE_CLOSE", symbol, cycle["direction"], {"price": current_price, "reason": "12H_INDECISION"})
                            symbols_to_delete.append(symbol)
                    else:
                        # High risk or limit reached - cut position immediately
                        log_info(f"✂️ Time limit exceeded ({cycle['holding_hours']:.1f}h) or high risk ({risk_score:.2f}) for {symbol}. Closing all.")
                        self.execution.close_position(cycle["ticket"], symbol)
                        for dca in cycle["dca_layers"]:
                            self.execution.close_position(dca["ticket"], symbol)
                        self.record_closed_cycle_to_training_data(cycle, current_price, now, "12H_HIGH_RISK")
                        log_cycle_event("CYCLE_CLOSE", symbol, cycle["direction"], {"price": current_price, "reason": "12H_HIGH_RISK"})
                        symbols_to_delete.append(symbol)
                        continue

            # ── 3. DCA Layer spacing management (Dynamic Progressive Step) ──
            rates_h1_dca = self.connector.get_rates(symbol, "H1", 100)
            if rates_h1_dca is not None and not rates_h1_dca.empty:
                atr_series_dca = rates_h1_dca["close"].diff().abs().rolling(14).mean()
                current_atr_dca = float(atr_series_dca.iloc[-1]) if not atr_series_dca.empty else cycle["atr"]
            else:
                current_atr_dca = cycle["atr"]

            # Space out DCA layers using ATR (widened for JPY and Indices to avoid premature filling)
            dca_multiplier = 1.0
            if "JPY" in symbol or symbol == "XAUUSD":
                dca_multiplier = 1.8
            elif symbol in ["US500", "US100", "BTCUSD"]:
                dca_multiplier = 1.5

            # Progressive steps: Layer 1 = 1.5 * ATR, Layer 2 = 2.5 * ATR
            step_multipliers = [1.5, 2.5]
            current_layer_idx = len(cycle["dca_layers"])
            should_dca = False
            spacing_price = 0.0

            if current_layer_idx < 2:
                # Layers 1-2: Passive distance-based DCA
                spacing_price = current_atr_dca * step_multipliers[current_layer_idx] * dca_multiplier
                entry_price = cycle["entry_price"]
                if cycle["direction"] == "BUY" and current_price <= (entry_price - spacing_price):
                    should_dca = True
                elif cycle["direction"] == "SELL" and current_price >= (entry_price + spacing_price):
                    should_dca = True
            elif current_layer_idx == 2:
                # Layer 3: Regime-driven (Requires 3.0 * ATR distance AND Liquidity Sweep)
                l3_min_dist = 3.0 * current_atr_dca * dca_multiplier
                price_dist_from_entry = abs(current_price - cycle["entry_price"])
                if price_dist_from_entry >= l3_min_dist and minor_liq_swept:
                    should_dca = True

            if should_dca and len(cycle["dca_layers"]) < 3:  # Hard limit 3 layers
                # Check weekend liquidation phase 2
                from src.session_manager import get_weekend_liquidation_phase
                dca_phase = get_weekend_liquidation_phase(now, settings.LIQUIDATION_HOUR_UTC) if settings.ENABLE_WEEKEND_LIQUIDATION else 0
                if dca_phase >= 2:
                    log_info(f"🔒 Weekend Liquidation Phase 2 Active: DCA layer blocked for {symbol}.")
                    continue

                # Place DCA order
                dca_lot = self.execution.normalize_lot(symbol, cycle["base_lot"])
                
                # Hard-SL based on Asset Class multiplier for DCA backup
                from config.symbols import get_symbol_spec
                spec = get_symbol_spec(symbol)
                multiplier = self.get_hard_sl_multiplier(spec.category)
                hard_sl_distance = multiplier * cycle["atr"]
                hard_sl = current_price - hard_sl_distance if cycle["direction"] == "BUY" else current_price + hard_sl_distance
                
                dca_ticket = self.execution.route_order(
                    symbol=symbol,
                    order_type=cycle["direction"],
                    lot=dca_lot,
                    tp=None,
                    sl=hard_sl,
                    comment=f"V9 Continuum DCA L{len(cycle['dca_layers']) + 1}"
                )
                
                if dca_ticket:
                    cycle["dca_layers"].append({
                        "ticket": dca_ticket,
                        "entry_price": current_price,
                        "lot": dca_lot,
                        "entry_time": now
                    })
                    log_info(f"➕ DCA Layer {len(cycle['dca_layers'])} added for {symbol} at {current_price}")
                    log_cycle_event("DCA_OPEN", symbol, cycle["direction"], {"price": current_price, "lot": dca_lot, "ticket": dca_ticket, "layer": len(cycle["dca_layers"])})

            # ── 4. 24H Absolute Time Cutoff ──
            if cycle["holding_hours"] >= 24.0:
                log_info(f"⏰ 24H Hard Stop reached for {symbol}. Cutting cycle.")
                self.execution.close_position(cycle["ticket"], symbol)
                for dca in cycle["dca_layers"]:
                    self.execution.close_position(dca["ticket"], symbol)
                self.record_closed_cycle_to_training_data(cycle, current_price, now, "24H_HARD_CUT")
                log_cycle_event("CYCLE_CLOSE", symbol, cycle["direction"], {"price": current_price, "reason": "24H_HARD_CUT"})
                symbols_to_delete.append(symbol)

        for symbol in symbols_to_delete:
            self.active_cycles.pop(symbol, None)

    def recover_active_cycles(self):
        """
        Queries MT5 for open positions and reconstructs the active_cycles dictionary.
        """
        from config.symbols import get_mt5_name
        mt5_to_internal = {get_mt5_name(s): s for s in self.symbols}
        
        positions = self.connector.get_positions()
        if not positions:
            return

        # Sort positions by time so we process the base position first
        positions_sorted = sorted(positions, key=lambda x: x.get("time", 0))
        
        for pos in positions_sorted:
            mt5_name = pos.get("symbol")
            internal_symbol = mt5_to_internal.get(mt5_name)
            if not internal_symbol:
                continue  # Skip symbols not in our trading list
            
            direction = pos.get("type")
            if not isinstance(direction, str):
                direction = "BUY" if direction == 0 else "SELL"
            entry_price = pos.get("price_open", pos.get("price"))
            ticket = pos.get("ticket")
            volume = pos.get("volume")
            
            entry_time = pos.get("time")
            if entry_time is None:
                entry_time = datetime.now(timezone.utc)
            elif not isinstance(entry_time, datetime):
                entry_time = datetime.fromtimestamp(entry_time, tz=timezone.utc)
            
            if internal_symbol in self.active_cycles:
                # Add as DCA layer
                cycle = self.active_cycles[internal_symbol]
                cycle["dca_layers"].append({
                    "ticket": ticket,
                    "entry_price": entry_price,
                    "lot": volume,
                    "entry_time": entry_time
                })
                log_info(f"🔄 Recovered DCA L{len(cycle['dca_layers'])} for {internal_symbol} (Ticket: {ticket})")
            else:
                # Calculate simple ATR proxy on H1 for recovery
                rates_h1 = self.connector.get_rates(internal_symbol, "H1", 100)
                if rates_h1 is not None and not rates_h1.empty:
                    atr_series = rates_h1["close"].diff().abs().rolling(14).mean()
                    atr_val = float(atr_series.iloc[-1]) if not atr_series.empty else 0.001
                else:
                    atr_val = 0.001
                
                # State Hydration: Reconstruct extreme_price from history
                extreme_p = entry_price
                rates_recovery = self.connector.get_rates(internal_symbol, "M15", 500)
                if rates_recovery is not None and not rates_recovery.empty:
                    try:
                        # Filter candles after entry time
                        entry_ts = entry_time.replace(tzinfo=None)
                        post_entry = rates_recovery[rates_recovery.index >= entry_ts]
                        if not post_entry.empty:
                            if direction == "BUY":
                                extreme_p = max(entry_price, float(post_entry['high'].max()))
                            else:
                                extreme_p = min(entry_price, float(post_entry['low'].min()))
                    except Exception:
                        pass # Fallback to entry_price

                # Open base cycle
                self.active_cycles[internal_symbol] = {
                    "symbol": internal_symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "base_lot": volume,
                    "ticket": ticket,
                    "entry_time": entry_time,
                    "dca_layers": [],
                    "holding_hours": (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600.0,
                    "atr": atr_val,
                    "is_extended": False,
                    "trailing_active": False,
                    "extreme_price": extreme_p
                }
                log_info(f"🔄 Recovered Base Cycle for {internal_symbol} (Direction: {direction}, Ticket: {ticket}, Extreme: {extreme_p:.5f})")

    def record_closed_cycle_to_training_data(self, cycle: Dict[str, Any], exit_price: float, current_time: datetime, reason: str):
        """
        Appends a closed trade cycle to logs/training_data.csv for ML self-learning.
        """
        if "features" not in cycle or not cycle["features"]:
            return # Skip if no features (e.g. recovered positions without indicators context)

        symbol = cycle["symbol"]
        direction = cycle["direction"]
        entry_time = cycle["entry_time"]
        
        # Calculate P&L
        from config.symbols import get_symbol_spec
        spec = get_symbol_spec(symbol)
        diff = (exit_price - cycle["entry_price"]) if direction == "BUY" else (cycle["entry_price"] - exit_price)
        
        total_lots = cycle["base_lot"]
        layer_pnl = 0.0
        for layer in cycle["dca_layers"]:
            total_lots += layer["lot"]
            l_diff = (exit_price - layer["entry_price"]) if direction == "BUY" else (layer["entry_price"] - exit_price)
            layer_pnl += l_diff * layer["lot"] * spec.contract_size

        base_pnl = diff * cycle["base_lot"] * spec.contract_size
        total_pnl = base_pnl + layer_pnl
        
        if symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD"):
            total_pnl = total_pnl / exit_price

        # Realize commissions and slippage/spread costs
        tick = cycle.get("last_tick")
        spread_pips = tick["spread_pips"] if tick and "spread_pips" in tick else 2.0
        
        pip_val_usd = spec.pip_size * spec.contract_size
        if symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD"):
            pip_val_usd = pip_val_usd / exit_price
        spread_usd = spread_pips * pip_val_usd * total_lots
        commission = 7.0 * total_lots
        
        final_pnl = total_pnl - spread_usd - commission
        is_win = 1 if final_pnl > 0 else 0
            
        from src.session_manager import get_current_session
        session = get_current_session(entry_time).value

        # Build row
        row = {
            "symbol": symbol,
            "direction": direction,
            "entry_time": entry_time.isoformat(),
            "session": session,
            "profit_usd": final_pnl,
            "is_win": is_win,
            **cycle["features"]
        }
        
        from pathlib import Path
        csv_path = Path("logs/training_data.csv")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        df_new = pd.DataFrame([row])
        if csv_path.exists():
            try:
                df_new.to_csv(csv_path, mode="a", header=False, index=False)
            except Exception as e:
                log_error(f"Error saving to training_data.csv: {e}")
        else:
            df_new.to_csv(csv_path, index=False)

    def close_all_positions(self) -> int:
        """
        Close all active positions with result tracking.
        
        Only removes successfully closed cycles from active_cycles.
        Positions that fail to close remain tracked so the bot can retry later.

        Returns:
            Number of positions that failed to close (0 = all closed).
        """
        if not self.active_cycles:
            return 0

        closed_symbols = []
        failed_count = 0
        total_tickets = 0

        for symbol, cycle in list(self.active_cycles.items()):
            all_closed = True
            total_tickets += 1

            # Close base position
            if not self.execution.close_position(cycle["ticket"], symbol):
                log_error(f"❌ Failed to close base ticket {cycle['ticket']} for {symbol}")
                all_closed = False
                failed_count += 1

            # Close DCA layers
            for dca in cycle["dca_layers"]:
                total_tickets += 1
                if not self.execution.close_position(dca["ticket"], symbol):
                    log_error(f"❌ Failed to close DCA ticket {dca['ticket']} for {symbol}")
                    all_closed = False
                    failed_count += 1

            if all_closed:
                closed_symbols.append(symbol)

        # Only remove successfully closed cycles
        for symbol in closed_symbols:
            self.active_cycles.pop(symbol, None)

        if failed_count == 0:
            log_info(f"🚨 All {total_tickets} position(s) closed successfully.")
        else:
            log_error(
                f"⚠️ Close summary: {total_tickets - failed_count}/{total_tickets} closed, "
                f"{failed_count} FAILED (still tracked for retry)."
            )

        return failed_count

    def run(self):
        """Starts the main trading loop."""
        # Write PID to file for watchdog tracking
        import os
        from pathlib import Path
        pid_file = Path("logs/bot.pid")
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            pid_file.write_text(str(os.getpid()), encoding="utf-8")
        except Exception as e:
            log_error(f"Failed to write PID file: {e}")

        sig.signal(sig.SIGINT, _shutdown_handler)
        sig.signal(sig.SIGTERM, _shutdown_handler)
        
        log_info("🤖 V9 Continuum Bot Initialized and Running...")
        
        # Connect to MT5
        if not self.connector.connect():
            log_error("Failed to connect to MT5. Exiting bot.")
            return

        # Fetch initial balance
        acc = self.connector.get_account_info()
        initial_balance = acc["balance"] if acc else 10000.0
        self.update_daily_balance(initial_balance)
        
        # Recover active cycles from broker
        self.recover_active_cycles()

        while _running:
            try:
                # ── Heartbeat Monitor ──
                import time
                from pathlib import Path
                prefix = f"bot_{settings.MAGIC_NUMBER}_" if getattr(settings, "MAGIC_NUMBER", 202500) != 202500 else ""
                heartbeat_file = Path("logs") / f"{prefix}heartbeat.txt"
                heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
                with open(heartbeat_file, "w", encoding="utf-8") as f:
                    f.write(str(int(time.time())))
                    
                now_utc = datetime.now(timezone.utc)
                
                # ── Weekend Liquidation Engine (3-Phase Risk Mitigation) ──
                liquidation_phase = 0
                if settings.ENABLE_WEEKEND_LIQUIDATION:
                    from src.session_manager import get_weekend_liquidation_phase
                    liquidation_phase = get_weekend_liquidation_phase(now_utc, settings.LIQUIDATION_HOUR_UTC)
                
                if liquidation_phase > 0:
                    log_info(f"⏳ Weekend Liquidation Active: Phase {liquidation_phase}")
                    
                    # Phase 2: Cancel pending orders
                    if liquidation_phase >= 2:
                        cancelled = self.connector.cancel_all_pending_orders()
                        if cancelled > 0:
                            log_info(f"Phase 2 Liquidation: Cancelled {cancelled} pending orders on broker.")
                            
                    # Phase 3: Force close all positions
                    if liquidation_phase == 3:
                        if self.active_cycles:
                            log_info(
                                f"🚨 Weekend Liquidation Phase 3: Friday {now_utc.strftime('%H:%M')} UTC — "
                                f"Closing all {len(self.active_cycles)} active cycle(s) to avoid Weekend Gap risk."
                            )
                            failed = self.close_all_positions()
                            if failed > 0:
                                log_error(f"⚠️ {failed} position(s) failed to close. Retrying in 60s...")
                                time.sleep(60)
                            else:
                                log_info("✅ All positions closed successfully before weekend. Bot entering standby.")
                                time.sleep(300)
                        else:
                            time.sleep(300)
                        continue

                # Check for weekend closed market
                if is_weekend(now_utc):
                    time.sleep(30)
                    continue

                session = get_current_session(now_utc)
                if session == Session.OFF:
                    # Session Freezing: Do not manage cycles, avoid MARKET_CLOSED errors.
                    time.sleep(30)
                    continue

                # Ensure MT5 is connected
                if not self.connector.ensure_connected():
                    time.sleep(10)
                    continue

                # Update starting balance on day change
                acc = self.connector.get_account_info()
                if acc:
                    self.update_daily_balance(acc["balance"])

                # Run core steps
                self.ml_engine.reload_if_modified()
                if liquidation_phase < 1:
                    self.process_signals(session)
                else:
                    log_info("🔒 Weekend Liquidation Phase 1 Active: Signal processing suspended (New Entries Blocked).")
                self.manage_cycles()

                # High performance sleep interval (10 seconds) with random jitter to prevent loop synchronization collisions
                import random
                time.sleep(10 + random.uniform(0.1, 0.9))
            except Exception as e:
                log_error(f"Error in trading loop: {e}")
                import random
                time.sleep(10 + random.uniform(0.1, 0.9))

        # Shutdown
        self.close_all_positions()
        self.connector.disconnect()
        log_info("👋 Bot stopped gracefully.")


if __name__ == "__main__":
    try:
        bot = V9ContinuumBot()
        bot.run()
    except BaseException as e:
        import traceback
        err_msg = f"🔥 CRITICAL UNHANDLED BOT EXCEPTION: {e}\n{traceback.format_exc()}"
        print(err_msg, file=sys.stderr)
        try:
            log_error(err_msg)
        except Exception:
            pass
        sys.exit(1)
