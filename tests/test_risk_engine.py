"""
Tests for Risk Engine (v2.1).
Constitution §15: Risk Engine has final veto authority.
"""

import pytest
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.risk_engine import RiskEngine
from src.trade_cycle_manager import TradeCycleManager
from src.hourly_gate import HourlyGate
from src.portfolio_engine import PortfolioEngine


@pytest.fixture
def components():
    """Create Risk Engine with dependencies."""
    cycle_manager = TradeCycleManager()
    hourly_gate = HourlyGate(window_minutes=5)
    portfolio_engine = PortfolioEngine(cycle_manager)
    risk_engine = RiskEngine(cycle_manager, hourly_gate, portfolio_engine)
    return risk_engine, cycle_manager, hourly_gate


def _valid_indicators():
    """Return a valid indicator set."""
    return {
        "RSI_H4": 60.0,
        "RSI_H1": 58.0,
        "RSI_M15": 56.0,
        "ADX": 30.0,
        "ATR": 0.0015,
    }


class TestDataStaleness:
    def test_stale_data_blocked(self, components):
        """Data > 120s → VETOED (WARNING)."""
        risk_engine, _, _ = components
        decision = risk_engine.can_trade(
            "EURUSD", "BUY",
            indicators=_valid_indicators(),
            data_age_seconds=150.0,
        )
        assert not decision.approved
        assert decision.veto_code == "DATA_STALE"
        assert decision.severity == "WARNING"

    def test_fresh_data_allowed(self, components):
        risk_engine, _, _ = components
        t = datetime(2025, 1, 15, 14, 1, tzinfo=timezone.utc)
        decision = risk_engine.can_trade(
            "EURUSD", "BUY",
            indicators=_valid_indicators(),
            data_age_seconds=30.0,
            spread_pips=1.0,
            current_time=t,
        )
        assert decision.approved


class TestMissingIndicators:
    def test_no_indicators(self, components):
        risk_engine, _, _ = components
        decision = risk_engine.can_trade("EURUSD", "BUY", indicators=None)
        assert not decision.approved
        assert decision.veto_code == "NO_INDICATORS"

    def test_missing_rsi(self, components):
        risk_engine, _, _ = components
        indicators = _valid_indicators()
        indicators["RSI_H1"] = None
        decision = risk_engine.can_trade("EURUSD", "BUY", indicators=indicators)
        assert not decision.approved
        assert decision.veto_code == "MISSING_INDICATORS"

    def test_missing_adx(self, components):
        risk_engine, _, _ = components
        indicators = _valid_indicators()
        indicators["ADX"] = None
        decision = risk_engine.can_trade("EURUSD", "BUY", indicators=indicators)
        assert not decision.approved
        assert decision.veto_code == "MISSING_INDICATORS"


class TestSpreadLimit:
    def test_high_spread_blocked(self, components):
        risk_engine, _, _ = components
        t = datetime(2025, 1, 15, 14, 1, tzinfo=timezone.utc)
        decision = risk_engine.can_trade(
            "EURUSD", "BUY",
            indicators=_valid_indicators(),
            spread_pips=10.0,  # > 5 pip limit for FX
            current_time=t,
        )
        assert not decision.approved
        assert decision.veto_code == "SPREAD_HIGH"

    def test_normal_spread_allowed(self, components):
        risk_engine, _, _ = components
        t = datetime(2025, 1, 15, 14, 1, tzinfo=timezone.utc)
        decision = risk_engine.can_trade(
            "EURUSD", "BUY",
            indicators=_valid_indicators(),
            spread_pips=2.0,
            current_time=t,
        )
        assert decision.approved


class TestDailyDrawdown:
    def test_drawdown_exceeded(self, components):
        risk_engine, _, _ = components
        risk_engine.update_daily_loss(55.0)  # > $50 limit

        t = datetime(2025, 1, 15, 14, 1, tzinfo=timezone.utc)
        decision = risk_engine.can_trade(
            "EURUSD", "BUY",
            indicators=_valid_indicators(),
            spread_pips=1.0,
            current_time=t,
        )
        assert not decision.approved
        assert decision.veto_code == "MAX_DRAWDOWN"

    def test_drawdown_within_limit(self, components):
        risk_engine, _, _ = components
        risk_engine.update_daily_loss(20.0)

        t = datetime(2025, 1, 15, 14, 1, tzinfo=timezone.utc)
        decision = risk_engine.can_trade(
            "EURUSD", "BUY",
            indicators=_valid_indicators(),
            spread_pips=1.0,
            current_time=t,
        )
        assert decision.approved


class TestSymbolExposure:
    def test_duplicate_symbol_blocked(self, components):
        risk_engine, cycle_manager, _ = components
        cycle_manager.open_cycle("EURUSD", "BUY", 1.1050, "EUROPE", 111)

        t = datetime(2025, 1, 15, 14, 1, tzinfo=timezone.utc)
        decision = risk_engine.can_trade(
            "EURUSD", "SELL",
            indicators=_valid_indicators(),
            spread_pips=1.0,
            current_time=t,
        )
        assert not decision.approved
        assert decision.veto_code == "SYMBOL_EXPOSURE"


class TestPortfolioLimit:
    def test_portfolio_full(self, components):
        risk_engine, cycle_manager, _ = components

        # Open 5 cycles (default max)
        for i, sym in enumerate(["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]):
            cycle_manager.open_cycle(sym, "BUY", 1.0 + i * 0.01, "EUROPE", 100 + i)

        t = datetime(2025, 1, 15, 14, 1, tzinfo=timezone.utc)
        decision = risk_engine.can_trade(
            "NZDUSD", "BUY",
            indicators=_valid_indicators(),
            spread_pips=1.0,
            current_time=t,
        )
        assert not decision.approved
        assert decision.veto_code == "PORTFOLIO_EXPOSURE"


class TestHourlyGateIntegration:
    def test_duplicate_in_same_hour(self, components):
        risk_engine, _, hourly_gate = components

        t = datetime(2025, 1, 15, 14, 1, tzinfo=timezone.utc)
        hourly_gate.record_trade("EURUSD", t)

        t2 = datetime(2025, 1, 15, 14, 3, tzinfo=timezone.utc)
        decision = risk_engine.can_trade(
            "EURUSD", "BUY",
            indicators=_valid_indicators(),
            spread_pips=1.0,
            current_time=t2,
        )
        assert not decision.approved
        assert decision.veto_code == "HOURLY_GATE"


class TestAllPass:
    def test_all_checks_pass(self, components):
        risk_engine, _, _ = components
        t = datetime(2025, 1, 15, 14, 1, tzinfo=timezone.utc)

        decision = risk_engine.can_trade(
            "EURUSD", "BUY",
            indicators=_valid_indicators(),
            spread_pips=1.0,
            data_age_seconds=10.0,
            current_time=t,
        )
        assert decision.approved
        assert decision.status_str == "APPROVED"
