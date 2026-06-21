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

from src.mt5_connector import MT5Connector
from src.session_manager import get_current_session, is_weekend, Session
from src.audit_logger import log_info, log_error, log_decision

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

    def update_daily_balance(self, current_balance: float):
        """Resets the start of day balance on day changes."""
        today = datetime.now(timezone.utc).date()
        if self.last_balance_update_day != today:
            self.start_of_day_balance = current_balance
            self.last_balance_update_day = today
            log_info(f"📅 Daily reset: Start of Day Balance set to ${self.start_of_day_balance:.2f}")

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
                feat = {
                    "RSI_M15": rsi_m15,
                    "RSI_H1": rsi_h1,
                    "RSI_H4": rsi_h4,
                    "ADX": adx_val,
                    "ATR": atr_val,
                    "RSI_Delta": rsi_h4 - rsi_m15,
                    "Volatility_Index": atr_val / rates_m15["close"].iloc[-1],
                    "hour": datetime.now(timezone.utc).hour,
                    "Session_Code": session_map.get(session.value if hasattr(session, "value") else str(session), -1),
                    "RSI_H1_Div": abs(rsi_h1 - 50.0),
                    "Trend_Vol_Ratio": adx_val * atr_val
                }
                
                loss_prob = self.ml_engine.predict_loss_probability(feat)
                if loss_prob > 0.6:
                    log_info(f"🛡️ ML filter vetoed {sig_val.value} entry for {symbol} due to high loss risk ({loss_prob:.2f})")
                    continue

                token = {
                    "symbol": symbol,
                    "direction": sig_val.value,
                    "adx": adx_val,
                    "spread": spread,
                    "atr": atr_val,
                    "reason": reason,
                    "price": rates_m15["close"].iloc[-1]
                }
                candidate_tokens.append(token)

        # Async Queue: Let the Governor pick the highest-priority signal (e.g. out of correlated entries)
        winner = self.governor.process_token_queue(candidate_tokens)
        if winner:
            symbol = winner["symbol"]
            
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
                return

            # Sizing and routing
            lot_size = self.position_sizer.calculate_lot_size(equity, winner["atr"], symbol, risk_percent=0.15)
            
            ticket = self.execution.route_order(
                symbol=symbol,
                order_type=winner["direction"],
                lot=lot_size,
                tp=None, # TP and SL handled dynamically by event loop target updates
                sl=None,
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
                    "is_extended": False
                }
                log_info(f"🚀 Base cycle opened for {symbol} ({winner['direction']}) at {winner['price']}")

    def manage_cycles(self):
        """
        Monitors active positions, checks profit targets, triggers 12H ML time-cutoffs or DCA layers.
        """
        acc = self.connector.get_account_info()
        equity = acc["equity"] if acc else 10000.0
        
        # Check global drawdown switch
        if self.start_of_day_balance > 0.0:
            drawdown = 100.0 * (self.start_of_day_balance - equity) / self.start_of_day_balance
            if drawdown >= matrix_config.max_daily_drawdown_percent or self.governor.system_status == "LOCKED":
                log_error(f"🚨 Drawdown Limit Breached ({drawdown:.2f}%). Emergency closing all positions!")
                self.close_all_positions()
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
                        else:
                            # No DCA layer, cut whole cycle
                            log_info(f"✂️ 12H Cutoff: Indecision ({risk_score:.2f}) with no DCA layers for {symbol}. Cutting position.")
                            self.execution.close_position(cycle["ticket"], symbol)
                            symbols_to_delete.append(symbol)
                    else:
                        # High risk or limit reached - cut position immediately
                        log_info(f"✂️ Time limit exceeded ({cycle['holding_hours']:.1f}h) or high risk ({risk_score:.2f}) for {symbol}. Closing all.")
                        self.execution.close_position(cycle["ticket"], symbol)
                        for dca in cycle["dca_layers"]:
                            self.execution.close_position(dca["ticket"], symbol)
                        symbols_to_delete.append(symbol)
                        continue

            # ── 3. DCA Layer spacing management ──
            # Space out DCA layers using ATR (widened for JPY and Indices to avoid premature filling)
            dca_multiplier = 1.0
            if "JPY" in symbol or symbol == "XAUUSD":
                dca_multiplier = 1.8
            elif symbol in ["US500", "US100", "BTCUSD"]:
                dca_multiplier = 1.5
            spacing_price = cycle["atr"] * dca_multiplier
            
            # Check if price moved against us by spacing distance
            entry_price = cycle["entry_price"]
            should_dca = False
            
            if cycle["direction"] == "BUY" and current_price <= (entry_price - spacing_price * (len(cycle["dca_layers"]) + 1)):
                should_dca = True
            elif cycle["direction"] == "SELL" and current_price >= (entry_price + spacing_price * (len(cycle["dca_layers"]) + 1)):
                should_dca = True

            if should_dca and len(cycle["dca_layers"]) < 3:  # Hard limit 3 layers
                # Place DCA order
                dca_lot = self.execution.normalize_lot(symbol, cycle["base_lot"])
                dca_ticket = self.execution.route_order(
                    symbol=symbol,
                    order_type=cycle["direction"],
                    lot=dca_lot,
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

            # ── 4. 24H Absolute Time Cutoff ──
            if cycle["holding_hours"] >= 24.0:
                log_info(f"⏰ 24H Hard Stop reached for {symbol}. Cutting cycle.")
                self.execution.close_position(cycle["ticket"], symbol)
                for dca in cycle["dca_layers"]:
                    self.execution.close_position(dca["ticket"], symbol)
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
                    "is_extended": False
                }
                log_info(f"🔄 Recovered Base Cycle for {internal_symbol} (Direction: {direction}, Ticket: {ticket})")

    def close_all_positions(self):
        """Emergency closes all positions."""
        for symbol, cycle in list(self.active_cycles.items()):
            self.execution.close_position(cycle["ticket"], symbol)
            for dca in cycle["dca_layers"]:
                self.execution.close_position(dca["ticket"], symbol)
        self.active_cycles.clear()
        log_info("🚨 All positions closed successfully.")

    def run(self):
        """Starts the main trading loop."""
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
                now_utc = datetime.now(timezone.utc)
                
                # Check for weekend closed market
                if is_weekend(now_utc):
                    time.sleep(30)
                    continue

                session = get_current_session(now_utc)
                if session == Session.OFF:
                    time.sleep(60)
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
                self.process_signals(session)
                self.manage_cycles()

                # High performance sleep interval (10 seconds)
                time.sleep(10)
            except Exception as e:
                log_error(f"Error in trading loop: {e}")
                time.sleep(10)

        # Shutdown
        self.close_all_positions()
        self.connector.disconnect()
        log_info("👋 Bot stopped gracefully.")


if __name__ == "__main__":
    bot = V9ContinuumBot()
    bot.run()
