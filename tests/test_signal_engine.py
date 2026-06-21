"""
Tests for Signal Engine (v2.1).
Constitution §5, §6 (BUY/SELL rules with Regime and Pullback).
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signal_engine import SignalEngine, Signal
from src.regime_engine import RegimeEngine


@pytest.fixture
def engine():
    """Create a SignalEngine with RegimeEngine."""
    regime = RegimeEngine()
    eng = SignalEngine(regime)
    eng.strict_pullback = True
    return eng


def get_bullish_indicators():
    return {
        "RSI_H4": 60.0,
        "RSI_H1": 60.0,
        "RSI_M15": 55.0,
        "ADX": 30.0,  # TRENDING
        "ATR": 0.0015,
        "M15_RSI_RISING": True,
        "M15_CLOSE_RISING": True,
        "M15_FRESH_LOCAL_LOW": False,
    }


def get_bearish_indicators():
    return {
        "RSI_H4": 40.0,
        "RSI_H1": 40.0,
        "RSI_M15": 45.0,
        "ADX": 30.0,  # TRENDING
        "ATR": 0.0015,
        "M15_RSI_FALLING": True,
        "M15_CLOSE_FALLING": True,
        "M15_FRESH_LOCAL_HIGH": False,
    }


class TestBuySignal:
    def test_strong_buy(self, engine):
        inds = get_bullish_indicators()
        assert engine.evaluate(inds) == Signal.BUY

    def test_no_buy_pullback_not_exhausted(self, engine):
        inds = get_bullish_indicators()
        inds["M15_RSI_RISING"] = False
        assert engine.evaluate(inds) == Signal.HOLD
        
    def test_no_buy_regime_blocked(self, engine):
        inds = get_bullish_indicators()
        inds["ADX"] = 15.0  # RANGE -> Blocked? Actually RegimeEngine might allow RANGE, but let's check transition.
        # RegimeEngine blocks TRANSITION (20-25).
        inds["ADX"] = 22.0  # TRANSITION
        assert engine.evaluate(inds) == Signal.HOLD


class TestSellSignal:
    def test_strong_sell(self, engine):
        inds = get_bearish_indicators()
        assert engine.evaluate(inds) == Signal.SELL

    def test_no_sell_pullback_not_exhausted(self, engine):
        inds = get_bearish_indicators()
        inds["M15_CLOSE_FALLING"] = False
        assert engine.evaluate(inds) == Signal.HOLD


class TestHoldSignal:
    def test_hold_missing_indicator(self, engine):
        inds = get_bullish_indicators()
        inds["RSI_H1"] = None
        assert engine.evaluate(inds) == Signal.HOLD


class TestDCAValidity:
    def test_buy_dca_valid(self, engine):
        inds = get_bullish_indicators()
        assert engine.check_dca_validity("BUY", inds) is True

    def test_buy_dca_invalid_rsi_reversed(self, engine):
        inds = get_bullish_indicators()
        inds["RSI_H4"] = 40.0  # Reversed
        assert engine.check_dca_validity("BUY", inds) is False

    def test_dca_invalid_adx_collapse(self, engine):
        inds = get_bullish_indicators()
        inds["ADX"] = 15.0  # Collapsed below range threshold (20)
        assert engine.check_dca_validity("BUY", inds) is False


class TestLoosePullbackSignal:
    def test_loose_buy_without_close_rising(self, engine):
        engine.strict_pullback = False
        try:
            inds = get_bullish_indicators()
            inds["M15_CLOSE_RISING"] = False  # Not rising
            assert engine.evaluate(inds) == Signal.BUY
        finally:
            engine.strict_pullback = True

    def test_loose_sell_without_close_falling(self, engine):
        engine.strict_pullback = False
        try:
            inds = get_bearish_indicators()
            inds["M15_CLOSE_FALLING"] = False  # Not falling
            assert engine.evaluate(inds) == Signal.SELL
        finally:
            engine.strict_pullback = True
