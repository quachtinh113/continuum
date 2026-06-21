"""
NowTrading 2.1 — Risk Engine (Build Step 6)
Final veto authority on all trading decisions. Includes Portfolio Governance.

Constitution §15:
Risk Engine has final technical authority.
Mandatory veto: Missing data, Data stale, Spread high, Max DD, Symbol exposure, Portfolio exposure, Duplicate trade.
"""

from datetime import datetime, timezone
from typing import Optional, Dict

from config import settings
from config.symbols import get_symbol_spec
from src.trade_cycle_manager import TradeCycleManager
from src.hourly_gate import HourlyGate
from src.portfolio_engine import PortfolioEngine


class RiskDecision:
    """Result of a risk check."""

    def __init__(self, approved: bool, reason: str, veto_code: str = "", severity: str = "INFO"):
        self.approved = approved
        self.reason = reason
        self.veto_code = veto_code
        self.severity = severity

    def __repr__(self):
        status = "APPROVED" if self.approved else f"VETOED({self.veto_code})"
        return f"RiskDecision({status}: {self.reason} [{self.severity}])"

    @property
    def status_str(self) -> str:
        return "APPROVED" if self.approved else "VETOED"


class RiskEngine:
    """
    Risk Engine with final veto authority.
    """

    def __init__(
        self,
        cycle_manager: TradeCycleManager,
        hourly_gate: HourlyGate,
        portfolio_engine: PortfolioEngine,
    ):
        self._cycle_manager = cycle_manager
        self._hourly_gate = hourly_gate
        self._portfolio_engine = portfolio_engine
        self._daily_loss: float = 0.0
        self._daily_date: Optional[str] = None

    def can_trade(
        self,
        symbol: str,
        signal: str,
        indicators: Optional[Dict] = None,
        spread_pips: Optional[float] = None,
        data_age_seconds: Optional[float] = None,
        current_time: Optional[datetime] = None,
        balance: float = 10000.0,
        equity: float = 10000.0,
    ) -> RiskDecision:
        """
        Run all risk checks and return decision.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        drawdown = 0.0
        if balance > 0:
            drawdown = (balance - equity) / balance

        # ── Check 0: Circuit Breaker (Drawdown > 8%) ──
        if drawdown > 0.08:
            return RiskDecision(
                False,
                f"Circuit Breaker: Drawdown {drawdown*100:.1f}% > 8%",
                "CIRCUIT_BREAKER",
                severity="CRITICAL"
            )

        # ── Check 0.5: Rollover hour block (Server hour 21:00 - 22:00) ──
        year = current_time.year
        from datetime import timedelta
        # Last Sunday of March
        dst_start = datetime(year, 3, 31, 1, tzinfo=timezone.utc)
        dst_start = dst_start - timedelta(days=(dst_start.weekday() + 1) % 7)
        # Last Sunday of October
        dst_end = datetime(year, 10, 31, 1, tzinfo=timezone.utc)
        dst_end = dst_end - timedelta(days=(dst_end.weekday() + 1) % 7)
        
        if dst_start <= current_time < dst_end:
            server_offset = 3
        else:
            server_offset = 2
            
        server_hour = (current_time + timedelta(hours=server_offset)).hour
        if 21 <= server_hour < 22:
            return RiskDecision(
                False,
                f"Rollover hour block (Server hour {server_hour}:00, high spread risk)",
                "ROLLOVER_BLOCK",
                severity="WARNING"
            )

        # ── Check 1: Data staleness (§16) ──
        if data_age_seconds is not None and data_age_seconds > settings.MAX_TICK_AGE_SECONDS:
            return RiskDecision(
                False,
                f"Data stale: {data_age_seconds:.1f}s > {settings.MAX_TICK_AGE_SECONDS}s limit",
                "DATA_STALE",
                severity="WARNING"
            )

        # ── Check 2: Missing indicator data ──
        if indicators is None:
            return RiskDecision(
                False,
                "Missing indicator data (None)",
                "NO_INDICATORS",
                severity="WARNING"
            )

        required_keys = ["RSI_H4", "RSI_H1", "RSI_M15", "ADX", "ATR"]
        missing = [k for k in required_keys if indicators.get(k) is None]
        if missing:
            return RiskDecision(
                False,
                f"Missing indicators: {missing}",
                "MISSING_INDICATORS",
                severity="WARNING"
            )

        # ── Check 3: Spread too high ──
        if spread_pips is not None:
            spec = get_symbol_spec(symbol)
            if spread_pips > spec.spread_limit:
                return RiskDecision(
                    False,
                    f"Spread {spread_pips:.1f} > limit {spec.spread_limit} pips",
                    "SPREAD_HIGH",
                    severity="CRITICAL"
                )

        # ── Check 4: Max daily drawdown ──
        if self._check_daily_drawdown() or self.check_daily_drawdown_limit(equity):
            return RiskDecision(
                False,
                f"Daily drawdown limit reached: ${settings.MAX_DAILY_DRAWDOWN_USD}",
                "MAX_DRAWDOWN",
                severity="CRITICAL"
            )

        # ── Check 5: Symbol exposure limit (1 active cycle per symbol) ──
        if self._cycle_manager.has_active_cycle(symbol):
            return RiskDecision(
                False,
                f"Symbol {symbol} already has active cycle",
                "SYMBOL_EXPOSURE",
                severity="INFO" # Not critical, just a normal rule
            )

        # ── Check 6: Portfolio Governance (§17) ──
        portfolio_ok, portfolio_reason = self._portfolio_engine.can_open_trade(symbol, signal)
        if not portfolio_ok:
            return RiskDecision(
                False,
                portfolio_reason,
                "PORTFOLIO_EXPOSURE",
                severity="CRITICAL"
            )

        # ── Check 7: Hourly gate (no duplicate trade in same hour, 60s cooldown) ──
        gate_ok, gate_reason = self._hourly_gate.can_trade(symbol, current_time)
        if not gate_ok:
            return RiskDecision(
                False,
                f"Hourly gate blocked: {gate_reason}",
                "HOURLY_GATE",
                severity="INFO"
            )

        # ── All checks passed ──
        return RiskDecision(
            True,
            f"All risk checks passed for {symbol} {signal}",
            severity="INFO"
        )

    def can_dca(
        self,
        symbol: str,
        indicators: Optional[Dict] = None,
        spread_pips: Optional[float] = None,
        data_age_seconds: Optional[float] = None,
        equity: float = 10000.0,
        current_time: Optional[datetime] = None,
    ) -> RiskDecision:
        """
        Check if DCA is allowed from risk perspective.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Check rollover hour
        year = current_time.year
        from datetime import timedelta
        # Last Sunday of March
        dst_start = datetime(year, 3, 31, 1, tzinfo=timezone.utc)
        dst_start = dst_start - timedelta(days=(dst_start.weekday() + 1) % 7)
        # Last Sunday of October
        dst_end = datetime(year, 10, 31, 1, tzinfo=timezone.utc)
        dst_end = dst_end - timedelta(days=(dst_end.weekday() + 1) % 7)
        
        if dst_start <= current_time < dst_end:
            server_offset = 3
        else:
            server_offset = 2
            
        server_hour = (current_time + timedelta(hours=server_offset)).hour
        if 21 <= server_hour < 22:
            return RiskDecision(
                False,
                f"Rollover hour block (Server hour {server_hour}:00, high spread risk)",
                "ROLLOVER_BLOCK",
                severity="WARNING"
            )

        # Check staleness
        if data_age_seconds is not None and data_age_seconds > settings.MAX_TICK_AGE_SECONDS:
            return RiskDecision(
                False, 
                f"Data stale: {data_age_seconds:.1f}s > {settings.MAX_TICK_AGE_SECONDS}s", 
                "DATA_STALE",
                severity="WARNING"
            )

        # Check indicators
        if indicators is None:
            return RiskDecision(False, "No indicators for DCA check", "NO_INDICATORS", severity="WARNING")

        required_keys = ["RSI_H4", "RSI_H1", "RSI_M15", "ADX", "ATR"]
        missing = [k for k in required_keys if indicators.get(k) is None]
        if missing:
            return RiskDecision(False, f"Missing indicators for DCA: {missing}", "MISSING_INDICATORS", severity="WARNING")

        # Check spread
        if spread_pips is not None:
            spec = get_symbol_spec(symbol)
            if spread_pips > spec.spread_limit:
                return RiskDecision(
                    False,
                    f"Spread too high for DCA: {spread_pips:.1f} > {spec.spread_limit}",
                    "SPREAD_HIGH",
                    severity="CRITICAL"
                )

        # Check drawdown
        if self._check_daily_drawdown() or self.check_daily_drawdown_limit(equity):
            return RiskDecision(
                False,
                "Daily drawdown limit — DCA blocked",
                "MAX_DRAWDOWN",
                severity="CRITICAL"
            )

        return RiskDecision(True, "DCA risk checks passed", severity="INFO")

    # ── Daily Drawdown Tracking ─────────────────────────────

    def update_daily_loss(self, loss: float):
        """Update daily loss tracker."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._daily_date != today:
            self._daily_loss = 0.0
            self._daily_date = today

        self._daily_loss += loss

    def update_start_of_day_balance(self, current_balance: float):
        """Update the start-of-day balance and daily date tracking."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if getattr(self, "_daily_date", None) != today or getattr(self, "_start_of_day_balance", 0.0) == 0.0:
            self._start_of_day_balance = current_balance
            self._daily_loss = 0.0
            self._daily_date = today

    def check_daily_drawdown_limit(self, current_equity: float) -> bool:
        """Check if daily drawdown from start of day exceeds the limit."""
        if getattr(self, "_start_of_day_balance", 0.0) <= 0.0:
            return False
            
        drawdown_usd = self._start_of_day_balance - current_equity
        return drawdown_usd >= settings.MAX_DAILY_DRAWDOWN_USD

    def _check_daily_drawdown(self) -> bool:
        """Check if daily drawdown limit has been reached."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._daily_date != today:
            self._daily_loss = 0.0
            self._daily_date = today
            return False

        return self._daily_loss >= settings.MAX_DAILY_DRAWDOWN_USD

    def get_daily_loss(self) -> float:
        """Get current daily loss total."""
        return self._daily_loss

    def reset_daily(self):
        """Reset daily loss tracking (for new trading day)."""
        self._daily_loss = 0.0
        self._daily_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def get_dynamic_lot_size(
        self, 
        base_lot: float, 
        balance: float, 
        equity: float,
        symbol: str = "",
        atr: Optional[float] = None,
        current_price: Optional[float] = None,
        ml_score: Optional[float] = None,
    ) -> float:
        """
        Computes final lot size with 3-tier ML dynamic scaling:

        Tier 1 — DD Protection: reduce by 50% if drawdown > 5%
        Tier 2 — ML Confidence Scaling:
            - ml_score < ML_LOT_BOOST_THRESHOLD  → lot × ML_LOT_BOOST_MULTIPLIER (e.g. ×1.5)
            - ml_score > ML_LOT_REDUCE_THRESHOLD → lot × ML_LOT_REDUCE_MULTIPLIER (e.g. ×0.7)
            - otherwise                           → lot × 1.0 (unchanged)
        Tier 3 — Hard Cap: lot capped at MAX_LOT_SIZE

        ml_score is the XGBoost LOSS_THREAT probability (0=safe, 1=risky).
        """
        if balance <= 0:
            return base_lot

        calculated_lot = base_lot

        # ── Tier 1: Drawdown protection ──────────────────────────────
        drawdown = (balance - equity) / balance
        if drawdown > 0.05:
            calculated_lot = max(0.01, round(calculated_lot * 0.5, 2))

        # ── Tier 2: ML Dynamic Lot Scaling ───────────────────────────
        if ml_score is not None:
            if ml_score < settings.ML_LOT_BOOST_THRESHOLD:
                # High confidence (low loss threat) → boost lot
                calculated_lot = calculated_lot * settings.ML_LOT_BOOST_MULTIPLIER
            elif ml_score > settings.ML_LOT_REDUCE_THRESHOLD:
                # Caution zone → reduce lot (but don't veto — gatekeeper already handles that)
                calculated_lot = calculated_lot * settings.ML_LOT_REDUCE_MULTIPLIER

        # ── Tier 3: Hard cap at MAX_LOT_SIZE ─────────────────────────
        calculated_lot = min(calculated_lot, settings.MAX_LOT_SIZE)

        return max(0.01, round(calculated_lot, 2))
