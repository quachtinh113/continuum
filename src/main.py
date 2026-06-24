"""
NowTrading 2.1 — Main Trading Loop
Entry point for the trading bot. Orchestrates all modules.

Flow per iteration:
1. Weekend check → sleep long if market closed
2. Health check → auto-reconnect MT5 if needed
3. Check session → is trading hours?
4. For each symbol:
   a. Update existing cycles (profit, time rules)
   b. Hourly Gate → can trade?
   c. MTF RSI Builder → get indicators
   d. Signal Engine → evaluate signal
   e. Risk Engine → can trade? (veto check)
   f. ATR DCA Engine → should DCA existing cycle?
   g. Open new cycle if signal valid + no existing cycle
   h. Audit Logger → log decision
5. Circuit breaker → all symbols failed? reconnect + backoff
6. Sleep until next check (60 seconds)

v2.1.1: Added weekend detection, auto-reconnect, circuit breaker, smart logging.
"""

import sys
import time
import signal as sig
from datetime import datetime, timezone
from typing import Optional

from config import settings
from config.symbols import get_all_symbols, get_symbol_spec, get_mt5_name
from src.mt5_connector import MT5Connector, MT5_AVAILABLE
from src.session_manager import (
    get_current_session, is_trading_hours, is_weekend, Session,
)
from src.mtf_rsi_builder import MTFRSIBuilder
from src.signal_engine import SignalEngine, Signal
from src.hourly_gate import HourlyGate
from src.trade_cycle_manager import TradeCycleManager
from src.atr_dca_engine import ATRDCAEngine
from src.risk_engine import RiskEngine
from src.regime_engine import RegimeEngine
from src.portfolio_engine import PortfolioEngine
from src.audit_logger import log_decision, log_info, log_error, log_cycle_event
from src.xgboost_gatekeeper import MLGatekeeper


# ── Graceful Shutdown ───────────────────────────────────────
_running = True


def _signal_handler(signum, frame):
    global _running
    log_info("⛔ Shutdown signal received. Stopping after current iteration...")
    _running = False


import os
import threading

class Watchdog:
    """Monitors the main thread and force-kills the process if it hangs (e.g. MT5 deadlock)."""
    def __init__(self, timeout_seconds=180):
        self.timeout = timeout_seconds
        self.last_ping = time.time()
        self.running = True
        self.paused = False

    def ping(self):
        self.last_ping = time.time()

    def pause(self):
        self.paused = True
        
    def resume(self):
        self.paused = False
        self.ping()

    def stop(self):
        self.running = False

    def run(self):
        last_loop_time = time.time()
        while self.running and _running:
            time.sleep(10)
            now = time.time()
            elapsed_sleep = now - last_loop_time
            last_loop_time = now

            # If the actual sleep time was way longer than expected (e.g. > 30s instead of 10s),
            # it means the PC was asleep/hibernated. Reset ping to avoid false-positive kill.
            if elapsed_sleep > 30.0:
                log_info(f"⏰ Watchdog detected system sleep/resume (sleep took {elapsed_sleep:.1f}s). Resetting watchdog timers.")
                self.ping()
                continue

            if not self.paused and (now - self.last_ping > self.timeout):
                log_error(f"💀 WATCHDOG TIMEOUT: Main thread hung for > {self.timeout}s. Force killing process for auto-restart...")
                os._exit(1)


class NowTradingBot:
    """
    Main NowTrading 2.1 Bot.

    Orchestrates all modules in the correct order per constitution.

    v2.1.1 Resilience Features:
    - Weekend detection: sleep long when market is closed
    - Auto-reconnect: health check + reconnect on MT5 disconnect
    - Circuit breaker: stop scanning if all symbols fail repeatedly
    - Smart logging: throttle repeated error messages
    """

    LOOP_INTERVAL_SECONDS = 60  # Check every 60 seconds

    def __init__(self):
        # Core components
        self.connector = MT5Connector()
        self.rsi_builder = MTFRSIBuilder(self.connector)
        
        self.regime_engine = RegimeEngine()
        self.signal_engine = SignalEngine(self.regime_engine)
        
        self.hourly_gate = HourlyGate()
        self.cycle_manager = TradeCycleManager()
        self.portfolio_engine = PortfolioEngine(self.cycle_manager)
        
        self.dca_engine = ATRDCAEngine(signal_engine=self.signal_engine)
        self.risk_engine = RiskEngine(self.cycle_manager, self.hourly_gate, self.portfolio_engine)

        # ML Gatekeeper
        self.ml_gatekeeper = MLGatekeeper()
        if settings.ML_GATEKEEPER_ACTIVE and not self.ml_gatekeeper.is_ready:
            log_error("⚠️ ML Gatekeeper active in settings but model not ready! Running without ML.")

        # Watchdog
        self.watchdog = Watchdog(timeout_seconds=180)

        # Symbols to trade
        self.symbols = get_all_symbols()

        # ── Resilience state ──
        self._weekend_logged = False           # Avoid spam "weekend" log
        self._last_no_data_log: float = 0      # Throttle "no data" decisions

    def recover_active_cycles(self):
        """Recover active trade cycles from existing MT5 positions.

        This method queries MT5 for open positions and reconstructs the in‑memory
        TradeCycle objects in `self.cycle_manager`. It maps MT5 symbols back to the
        internal symbol names, creates a base cycle for the first position of a
        symbol, and adds subsequent positions as DCA layers.
        """
        # Build mapping from MT5 symbol name to internal symbol
        mt5_to_internal = {get_mt5_name(s): s for s in self.symbols}
        positions = self.connector.get_positions()
        for pos in positions:
            mt5_name = pos["symbol"]
            internal_symbol = mt5_to_internal.get(mt5_name)
            if not internal_symbol:
                continue  # Skip symbols not in our trading list
            direction = pos["type"]  # "BUY" or "SELL"
            entry_price = pos["price_open"]
            ticket = pos["ticket"]
            volume = pos["volume"]
            entry_time = pos["time"]
            # If we already have a cycle, treat as an additional DCA layer
            if self.cycle_manager.has_active_cycle(internal_symbol):
                self.cycle_manager.add_dca_layer(
                    symbol=internal_symbol,
                    entry_price=entry_price,
                    lot_size=volume,
                    ticket=ticket,
                    entry_time=entry_time,
                )
            else:
                # Open a new cycle with the base lot equal to the position volume
                self.cycle_manager.open_cycle(
                    symbol=internal_symbol,
                    direction=direction,
                    entry_price=entry_price,
                    session=get_current_session(datetime.now(timezone.utc)).value,
                    ticket=ticket,
                    entry_time=entry_time,
                    base_lot=volume,
                )
        if positions:
            log_info(f"Recovered {len(positions)} open MT5 positions into active cycles")


    def start(self):
        """Start the trading bot main loop."""
        global _running

        # Register signal handlers for graceful shutdown
        sig.signal(sig.SIGINT, _signal_handler)
        sig.signal(sig.SIGTERM, _signal_handler)

        self._print_banner()

        # Start Watchdog
        t = threading.Thread(target=self.watchdog.run, daemon=True)
        t.start()

        # Connect to MT5
        if not self.connector.connect():
            log_error("Failed to connect to MT5. Exiting.")
            sys.exit(1)

        # Enable all trading symbols on MT5 terminal
        self._enable_symbols()
        self.recover_active_cycles()

        log_info(f"Trading {len(self.symbols)} symbols: {self.symbols}")
        log_info(
            f"Mode: {'🔴 LIVE' if settings.LIVE_TRADING else '🟡 DRY RUN'} │ "
            f"Base Lots (FX: {settings.FX_BASE_LOT}, Commodity/Gold: {settings.COMMODITY_BASE_LOT}, Crypto: {settings.CRYPTO_BASE_LOT}) │ "
            f"Max Lot: {settings.MAX_LOT_SIZE} │ "
            f"Max DCA: {settings.MAX_DCA_LAYERS} │ "
            f"Profit Target: ${settings.PROFIT_TARGET_USD}"
        )

        try:
            while _running:
                self._run_iteration()
                if _running:
                    time.sleep(self.LOOP_INTERVAL_SECONDS)
        except Exception as e:
            log_error(f"Unhandled exception in main loop: {e}")
            raise
        finally:
            self.watchdog.stop()
            self.connector.disconnect()
            log_info("Bot stopped.")

    def _run_iteration(self):
        """Run one iteration of the trading loop."""
        self.watchdog.ping()
        now = datetime.now(timezone.utc)

        # ── Step 0: Weekend check ──
        if is_weekend(now):
            if not self._weekend_logged:
                log_info(
                    f"🌙 Market closed (weekend). "
                    f"Sleeping {settings.WEEKEND_SLEEP_SECONDS}s until market reopens..."
                )
                self._weekend_logged = True
            self.watchdog.pause()
            time.sleep(settings.WEEKEND_SLEEP_SECONDS - self.LOOP_INTERVAL_SECONDS)
            self.watchdog.resume()
            return
        else:
            self._weekend_logged = False  # Reset for next weekend

        # ── Step 1: Health check + auto-reconnect ──
        if not self.connector.ensure_connected():
            log_error("MT5 connection unavailable. Skipping this iteration.")
            return

        session = get_current_session(now)

        # Check if within trading hours
        if session == Session.OFF:
            return  # Silent — no logging during off-hours

        # ── Step 1.5: Start of Day Drawdown Check & Force Close ──
        account_info = self.connector.get_account_info()
        balance = account_info["balance"] if account_info else 10000.0
        equity = account_info["equity"] if account_info else 10000.0
        
        self.risk_engine.update_start_of_day_balance(balance)
        if self.risk_engine.check_daily_drawdown_limit(equity):
            log_error(
                f"🚨 Daily Drawdown limit reached! Start of Day Balance: ${self.risk_engine._start_of_day_balance:.2f}, "
                f"Current Equity: ${equity:.2f}. Force closing all positions across all symbols."
            )
            self._force_close_all_symbols()
            return

        log_info(
            f"━━━ Iteration │ {now.strftime('%Y-%m-%d %H:%M:%S')} UTC │ "
            f"Session: {session.value} │ "
            f"Active Cycles: {self.cycle_manager.get_active_cycle_count()} ━━━"
        )

        # ── Step 2: Process each symbol ──
        symbols_failed = 0
        symbols_success = 0

        for symbol in self.symbols:
            try:
                data_ok = self._process_symbol(symbol, session, now)
                if data_ok:
                    symbols_success += 1
                else:
                    symbols_failed += 1
            except Exception as e:
                log_error(f"Error processing {symbol}: {e}")
                symbols_failed += 1

        # ── Step 3: Circuit breaker check ──
        if symbols_success == 0 and symbols_failed > 0:
            # ALL symbols failed this iteration
            self.connector.record_global_failure()
            threshold = settings.CIRCUIT_BREAKER_THRESHOLD

            if self.connector.global_consecutive_failures >= threshold:
                log_error(
                    f"🔌 CIRCUIT BREAKER │ All {symbols_failed} symbols failed "
                    f"for {self.connector.global_consecutive_failures} consecutive iterations. "
                    f"Attempting MT5 reconnect..."
                )

                # Force reconnect
                self.connector.disconnect()
                if self.connector.connect():
                    self._enable_symbols()
                    log_info("✅ Circuit breaker reset: MT5 reconnected")
                else:
                    log_error(
                        f"❌ Circuit breaker: MT5 reconnect failed. "
                        f"Sleeping {settings.WEEKEND_SLEEP_SECONDS}s before retry..."
                    )
                    self.watchdog.pause()
                    time.sleep(settings.WEEKEND_SLEEP_SECONDS - self.LOOP_INTERVAL_SECONDS)
                    self.watchdog.resume()

                # Reset counter after attempt
                self.connector.clear_global_failure()
        else:
            # At least one symbol succeeded — reset counter
            self.connector.clear_global_failure()

    def _process_symbol(self, symbol: str, session: Session, now: datetime) -> bool:
        """
        Process a single symbol: update cycles, check signals, manage trades.

        Returns:
            True if data was successfully retrieved (even if signal was HOLD).
            False if data retrieval failed.
        """

        # ── Step 1: Update existing cycle if any ──
        cycle = self.cycle_manager.get_cycle(symbol)
        if cycle is not None:
            self._manage_existing_cycle(symbol, cycle, now)
        else:
            # Only allow new cycles for XAUUSD (Gold) as requested by user
            if symbol != "XAUUSD":
                return True

            # OPTIMIZATION: If no active cycle and outside the hourly gate window (first 5 mins),
            # skip evaluating signals to save CPU, MT5 calls, and prevent log spam.
            if now.minute >= settings.HOURLY_GATE_WINDOW_MINUTES:
                return True  # Not a data failure, just optimization skip

        # ── Step 2: Get current indicators ──
        indicators = self.rsi_builder.build_indicators(symbol)

        if indicators is None:
            # Throttled logging: only log "no data" decision once per ERROR_LOG_THROTTLE_SECONDS
            now_ts = time.time()
            throttle = settings.ERROR_LOG_THROTTLE_SECONDS

            if now_ts - self._last_no_data_log >= throttle:
                from src.risk_engine import RiskDecision
                dummy_veto = RiskDecision(False, "No indicator data available", veto_code="NO_DATA", severity="WARNING")
                log_decision(
                    symbol=symbol,
                    session=session.value,
                    indicators={},
                    signal="HOLD",
                    risk_decision=dummy_veto,
                    execution_action="SKIP",
                )
                # Only update throttle timestamp after logging ALL symbols in this batch
                if symbol == self.symbols[-1]:
                    self._last_no_data_log = now_ts
            return False  # Data failure

        # ── Step 3: Evaluate signal ──
        signal = self.signal_engine.evaluate(indicators)

        # ── Step 4: DCA check for existing cycle ──
        if cycle is not None and cycle.status.value == "ACTIVE":
            self._try_dca(symbol, cycle, indicators, session, now)
            # Don't open new cycle if one exists
            return True

        # ── Step 5: Skip HOLD signals ──
        if signal == Signal.HOLD:
            # Only log HOLD at beginning of hour to avoid spam
            if now.minute < 5:
                from src.risk_engine import RiskDecision
                dummy_veto = RiskDecision(False, self.signal_engine.get_signal_reason(signal, indicators), veto_code="N/A", severity="INFO")
                log_decision(
                    symbol=symbol,
                    session=session.value,
                    indicators=indicators,
                    signal=signal.value,
                    risk_decision=dummy_veto,
                    execution_action="SKIP",
                )
            return True

        # ── Step 6: Risk check for new trade ──
        tick = self.connector.get_tick(symbol)
        if tick is None:
            return False
            
        spread = tick["spread_pips"]
        tick_age_seconds = (now - tick["time"]).total_seconds()

        account_info = self.connector.get_account_info()
        balance = account_info["balance"] if account_info else 10000.0
        equity = account_info["equity"] if account_info else 10000.0

        risk_decision = self.risk_engine.can_trade(
            symbol=symbol,
            signal=signal.value,
            indicators=indicators,
            spread_pips=spread,
            data_age_seconds=tick_age_seconds,
            current_time=now,
            balance=balance,
            equity=equity,
        )

        if not risk_decision.approved:
            log_decision(
                symbol=symbol,
                session=session.value,
                indicators=indicators,
                signal=signal.value,
                risk_decision=risk_decision,
                execution_action="BLOCKED",
            )
            return True

        # ── Step 6.5: ML Gatekeeper Veto ──
        ml_score = None  # will be used later for dynamic lot sizing
        if settings.ML_GATEKEEPER_ACTIVE and self.ml_gatekeeper.is_ready:
            current_price = tick["ask"] if signal.value == "BUY" else tick["bid"]
            # We must explicitly convert time.hour to int
            hour = now.hour
            score = self.ml_gatekeeper.score_trade(indicators, current_price, hour)
            ml_score = score  # capture for lot sizing below
            
            if score is not None:
                is_safe = self.ml_gatekeeper.is_entry_safe(score)
                if not is_safe:
                    if settings.ML_MODE == "AUDIT_ENABLED":
                        # Audit log it
                        import json
                        with open("logs/ml_veto_audit.jsonl", "a") as f:
                            f.write(json.dumps({
                                "timestamp": now.isoformat(),
                                "symbol": symbol,
                                "signal": signal.value,
                                "score": score,
                                "threshold": settings.ML_ENTRY_SAFE_THRESHOLD,
                                "action": "VETOED_ENTRY"
                            }) + "\n")
                        
                        # Apply Veto
                        from src.risk_engine import RiskDecision
                        ml_veto = RiskDecision(
                            False, 
                            f"ML Entry Unsafe (Score: {score:.4f} >= {settings.ML_ENTRY_SAFE_THRESHOLD})", 
                            veto_code="ML_ENTRY_UNSAFE", 
                            severity="CRITICAL"
                        )
                        log_decision(
                            symbol=symbol,
                            session=session.value,
                            indicators=indicators,
                            signal=signal.value,
                            risk_decision=ml_veto,
                            execution_action="ML_BLOCKED",
                        )
                        return True


        # ── Step 7: Execute trade ──
        current_price = tick["ask"] if signal.value == "BUY" else tick["bid"]
        
        # Select base lot size based on symbol category
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

        lot_size = self.risk_engine.get_dynamic_lot_size(
            base_lot=base_lot,
            balance=balance,
            equity=equity,
            symbol=symbol,
            atr=indicators.get("ATR") if indicators else None,
            current_price=current_price,
            ml_score=ml_score,
        )
        self._open_new_trade(symbol, signal, indicators, tick, session, now, lot_size)
        return True

    def _open_new_trade(
        self,
        symbol: str,
        signal: Signal,
        indicators: dict,
        tick: dict,
        session: Session,
        now: datetime,
        lot_size: float = settings.MAX_LOT_SIZE,
    ):
        """Open a new trade cycle."""
        direction = signal.value
        price = tick["ask"] if direction == "BUY" else tick["bid"]

        # Place order
        ticket = self.connector.place_order(
            symbol=symbol,
            order_type=direction,
            lot=lot_size,
            price=price,
        )

        if ticket is None:
            log_error(f"Order placement failed for {symbol} {direction}")
            return

        # Open cycle
        cycle = self.cycle_manager.open_cycle(
            symbol=symbol,
            direction=direction,
            entry_price=price,
            session=session.value,
            ticket=ticket,
            entry_time=now,
            base_lot=lot_size,
        )

        # Record in hourly gate
        self.hourly_gate.record_trade(symbol, now)

        # Log
        # We need a dummy RiskDecision for APPROVED to pass to log_decision
        from src.risk_engine import RiskDecision
        approved_decision = RiskDecision(True, self.signal_engine.get_signal_reason(signal, indicators))
        
        log_decision(
            symbol=symbol,
            session=session.value,
            indicators=indicators,
            signal=direction,
            risk_decision=approved_decision,
            execution_action=f"OPEN_{direction}",
        )

    def _manage_existing_cycle(
        self,
        symbol: str,
        cycle,
        now: datetime,
    ):
        """Manage an existing trade cycle: update and apply time rules."""

        # Get current price
        tick = self.connector.get_tick(symbol)
        if tick is None:
            return

        current_price = (tick["bid"] + tick["ask"]) / 2

        # Update cycle
        self.cycle_manager.update_cycle(symbol, current_price, now)

        # Get indicators for dynamic checks
        indicators = self.rsi_builder.build_indicators(symbol)
        adx = indicators.get("ADX") if indicators else None
        atr = indicators.get("ATR") if indicators else None
        rsi_h4 = indicators.get("RSI_H4") if indicators else None
        rsi_h1 = indicators.get("RSI_H1") if indicators else None

        # ── Profit Rule: dynamic target ──
        profit_action = self.cycle_manager.check_profit_rule(symbol, atr=atr, current_price=current_price)
        if profit_action == "CLOSE_PROFIT":
            self._close_cycle_orders(symbol, "PROFIT_TARGET")
            log_info(
                f"💰 Profit target hit for {symbol}: "
                f"${cycle.current_profit_usd:.2f} after {cycle.holding_hours:.1f}h"
            )
            return

        # ── Break-Even Rule ──
        minor_liquidity_swept = False
        if indicators:
            if cycle.direction == "BUY":
                minor_liquidity_swept = indicators.get("M15_FRESH_LOCAL_HIGH", False)
            else:
                minor_liquidity_swept = indicators.get("M15_FRESH_LOCAL_LOW", False)

        be_action = self.cycle_manager.check_break_even(
            symbol, current_price, atr, minor_liquidity_swept=minor_liquidity_swept
        )
        if be_action == "BREAK_EVEN":
            self._close_cycle_orders(symbol, "BREAK_EVEN")
            log_info(
                f"🛡️ Break-Even exit triggered for {symbol} after {cycle.holding_hours:.1f}h"
            )
            return

        # ── ML Gatekeeper Score (calculate once for rules) ──
        ml_score = None
        if getattr(self, 'ml_gatekeeper', None) and settings.ML_GATEKEEPER_ACTIVE and self.ml_gatekeeper.is_ready:
            if indicators:
                ml_score = self.ml_gatekeeper.score_trade(indicators, current_price, now.hour)

        # ── ML Veto Rule ──
        ml_action = self.cycle_manager.check_ml_veto(symbol, ml_score)
        if ml_action == "ML_VETO_CLOSE":
            self._close_cycle_orders(symbol, "ML_VETO_CLOSE")
            log_info(
                f"🚨 ML Veto triggered for {symbol}: "
                f"Score {ml_score:.2f} > dynamic threshold. Force closing."
            )
            return


        # ── Hard Stop R:R Rule ──
        hard_stop_action = self.cycle_manager.check_hard_stop_rule(symbol, atr, current_price)
        if hard_stop_action == "FORCE_CLOSE_RR_LIMIT":
            self._close_cycle_orders(symbol, "FORCE_CLOSE_RR_LIMIT")
            log_info(
                f"💥 Hard Stop R:R triggered for {symbol}: "
                f"Loss limit exceeded. Force closing."
            )
            return

        # ── Conditional Force Close Rule ── (check before 12h to give priority)
        force_action = self.cycle_manager.check_conditional_force_close(
            symbol,
            current_price=current_price,
            adx=adx,
            rsi_h4=rsi_h4,
            rsi_h1=rsi_h1,
        )
        if force_action == "FORCE_CLOSE":
            self._close_cycle_orders(symbol, "CONDITIONAL_FORCE_CLOSE")
            log_info(
                f"⏰ Conditional force close triggered for {symbol}: "
                f"Force closing after {cycle.holding_hours:.1f}h"
            )
            return

        # ── 12-Hour Rule: reduce or cut ──
        reduce_action = self.cycle_manager.check_12h_rule(
            symbol,
            current_price=current_price,
            adx=adx,
            atr=atr,
            ml_score=ml_score
        )
        if reduce_action == "REDUCE_DCA":
            worst = self.cycle_manager.remove_worst_dca(symbol)
            if worst and worst.ticket > 0:
                self.connector.close_order(worst.ticket, symbol)
            log_info(
                f"📉 12h rule: Reduced DCA for {symbol}, "
                f"removed layer at {worst.entry_price if worst else 'N/A'}"
            )
        elif reduce_action == "CUT_ALL":
            self._close_cycle_orders(symbol, "12H_RULE_CUT")
            log_info(
                f"✂️ 12h rule: Cut all for {symbol} after {cycle.holding_hours:.1f}h"
            )

    def _try_dca(
        self,
        symbol: str,
        cycle,
        indicators: dict,
        session: Session,
        now: datetime,
    ):
        """Try to DCA an existing cycle if conditions are met."""

        # Risk check for DCA
        tick = self.connector.get_tick(symbol)
        if tick is None:
            return

        spread = tick["spread_pips"]
        tick_age_seconds = (now - tick["time"]).total_seconds()
        
        account_info = self.connector.get_account_info()
        equity = account_info["equity"] if account_info else 10000.0
        
        risk_ok = self.risk_engine.can_dca(
            symbol=symbol,
            indicators=indicators,
            spread_pips=spread,
            data_age_seconds=tick_age_seconds,
            equity=equity,
            current_time=now,
        )
        if not risk_ok.approved:
            return

        current_price = tick["ask"] if cycle.direction == "BUY" else tick["bid"]

        # Calculate ML Score
        ml_score = None
        if getattr(self, 'ml_gatekeeper', None) and settings.ML_GATEKEEPER_ACTIVE and self.ml_gatekeeper.is_ready:
            if indicators:
                ml_score = self.ml_gatekeeper.score_trade(indicators, current_price, now.hour)

        # DCA engine check
        should_dca, reason = self.dca_engine.should_dca(
            cycle=cycle,
            current_price=current_price,
            indicators=indicators,
            ml_score=ml_score,
        )

        if not should_dca:
            return

        # Execute DCA
        lot = self.dca_engine.get_dca_lot_size(cycle)
        ticket = self.connector.place_order(
            symbol=symbol,
            order_type=cycle.direction,
            lot=lot,
            price=current_price,
            comment=f"NowTrading2.0 DCA L{cycle.num_dca_layers + 1}",
        )

        if ticket is None:
            return

        self.cycle_manager.add_dca_layer(
            symbol=symbol,
            entry_price=current_price,
            lot_size=lot,
            ticket=ticket,
        )

        from src.risk_engine import RiskDecision
        approved_decision = RiskDecision(True, reason)
        
        log_decision(
            symbol=symbol,
            session=session.value,
            indicators=indicators,
            signal=cycle.direction,
            risk_decision=approved_decision,
            execution_action=f"DCA_{cycle.direction}",
        )

    def _close_cycle_orders(self, symbol: str, reason: str):
        """Close all orders in a cycle and close the cycle."""
        cycle = self.cycle_manager.get_cycle(symbol)
        if cycle is None:
            return

        # Track loss for risk engine
        if cycle.current_profit_usd < 0:
            self.risk_engine.update_daily_loss(abs(cycle.current_profit_usd))

        # Close all MT5 orders
        for ticket in cycle.tickets:
            if ticket > 0:  # Skip dry run tickets (-1)
                self.connector.close_order(ticket, symbol)

        # Close cycle
        self.cycle_manager.close_cycle(symbol, reason)

    def _force_close_all_symbols(self):
        """Force close all open positions across all symbols."""
        active_symbols = list(self.cycle_manager.get_all_active_cycles().keys())
        for symbol in active_symbols:
            self._close_cycle_orders(symbol, "DAILY_DRAWDOWN_CUT")

    def _enable_symbols(self):
        """Enable (make visible) all trading symbols in MT5 terminal."""
        if not MT5_AVAILABLE:
            return

        import MetaTrader5 as mt5

        enabled = 0
        failed = []

        for symbol in self.symbols:
            mt5_name = get_mt5_name(symbol)
            info = mt5.symbol_info(mt5_name)

            if info is None:
                failed.append(f"{symbol}({mt5_name})")
                continue

            if not info.visible:
                if not mt5.symbol_select(mt5_name, True):
                    failed.append(f"{symbol}({mt5_name})")
                    continue

            enabled += 1

        log_info(f"Symbols enabled: {enabled}/{len(self.symbols)}")
        if failed:
            log_error(f"Failed to enable symbols: {failed}")
            # Remove failed symbols from trading list
            self.symbols = [s for s in self.symbols if f"{s}({get_mt5_name(s)})" not in failed]
            log_info(f"Trading reduced to {len(self.symbols)} symbols")

        # Wait for MT5 to download historical data for newly enabled symbols
        sync_wait = getattr(settings, "DATA_SYNC_WAIT_SECONDS", 30)
        log_info(f"Waiting {sync_wait}s for MT5 to sync symbol data...")
        self.watchdog.pause()
        time.sleep(sync_wait)
        self.watchdog.resume()

    def _print_banner(self):
        """Print startup banner."""
        banner = """
                ╔══════════════════════════════════════════════════════════════╗
                ║                                                              ║
                ║     ███╗   ██╗ ██████╗ ██╗    ██╗████████╗██████╗  █████╗    ║
                ║     ████╗  ██║██╔═══██╗██║    ██║╚══██╔══╝██╔══██╗██╔══██╗   ║
                ║     ██╔██╗ ██║██║   ██║██║ █╗ ██║   ██║   ██████╔╝███████║   ║
                ║     ██║╚██╗██║██║   ██║██║███╗██║   ██║   ██╔══██╗██╔══██║   ║
                ║     ██║ ╚████║╚██████╔╝╚███╔███╔╝   ██║   ██║  ██║██║  ██║   ║
                ║     ╚═╝  ╚═══╝ ╚═════╝  ╚══╝╚══╝    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝   ║
                ║                                                              ║
                ║         NowTrading 2.1 — Quantitative Trading Bot            ║
                ║         RSI × ADX × ATR  │  H4 × H1 × M15                    ║
                ║                                                              ║
                ╚══════════════════════════════════════════════════════════════╝
        """
        print(banner)


# ── Entry Point ─────────────────────────────────────────────

def main():
    """Main entry point."""
    bot = NowTradingBot()
    bot.start()


if __name__ == "__main__":
    main()
