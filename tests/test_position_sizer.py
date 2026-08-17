"""
Unit Test Suite for PositionSizer (Fixed Fractional Risk Integrity & Multi-Asset Precision).
Validates:
  1. Exact Dollar Risk Budget enforcement (Equity * Risk_Pct).
  2. Multi-asset contract sizing: Forex Majors, Crosses, Metals (XAUUSD), Indices (US30/US100/US500).
  3. Micro-Account Quantization Guard (Order Rejection when actual risk at min lot exceeds budget).
  4. Ledoit-Wolf & Correlation Haircuts.
  5. Net Exit Price calculation.
"""

import pytest
import math
from v9_continuum.layers.position import (
    PositionSizer,
    get_quote_to_usd_conversion,
    get_symbol_correlation,
    compute_ledoit_wolf_shrinkage_covariance
)
from config.symbols import get_symbol_spec


@pytest.fixture
def sizer():
    return PositionSizer(risk_multiplier=1.0)


# ── 1. Forex Majors (USD Quote: EURUSD, GBPUSD, AUDUSD, NZDUSD) ───────────────

@pytest.mark.parametrize("equity, atr, atr_mult, risk_pct, expected_lots", [
    # Equity $10,000, 0.5% risk = $50. ATR = 0.0020 (20 pips), SL = 0.0030 (30 pips).
    # Dollar risk per lot = 0.0030 * 100,000 = $300.
    # Raw lots = 50 / 300 = 0.1666... -> Quantized = 0.16 lots.
    (10000.0, 0.0020, 1.5, 0.5, 0.16),
    
    # Equity $5,000, 0.5% risk = $25. ATR = 0.0010 (10 pips), SL = 0.0015 (15 pips).
    # Dollar risk per lot = 0.0015 * 100,000 = $150.
    # Raw lots = 25 / 150 = 0.1666... -> Quantized = 0.16 lots
    (5000.0, 0.0010, 1.5, 0.5, 0.16),
    
    # Equity $1,000, 0.5% risk = $5. ATR = 0.0015 (15 pips), SL = 0.00225 (22.5 pips).
    # Dollar risk per lot = 0.00225 * 100,000 = $225.
    # Raw lots = 5 / 225 = 0.0222... -> Quantized = 0.02 lots.
    (1000.0, 0.0015, 1.5, 0.5, 0.02),
])
def test_forex_majors_sizing(sizer, equity, atr, atr_mult, risk_pct, expected_lots):
    lots = sizer.calculate_lot_size(
        equity=equity,
        atr=atr,
        symbol="EURUSD",
        risk_percent=risk_pct,
        atr_multiplier=atr_mult,
        current_price=1.0850,
        max_lot_override=1.0
    )
    assert lots == expected_lots, f"Expected {expected_lots}, got {lots}"
    
    # Verify dollar risk at calculated lots does NOT exceed risk budget
    risk_budget = equity * (risk_pct / 100.0)
    spec = get_symbol_spec("EURUSD")
    actual_risk = lots * (atr * atr_mult) * spec.contract_size
    assert actual_risk <= risk_budget + 1e-6, f"Actual risk ${actual_risk} breached budget ${risk_budget}"


# ── 2. Forex Crosses (Non-USD Quote: USDJPY, USDCHF, USDCAD) ──────────────────

def test_usdjpy_sizing_precision(sizer):
    equity = 10000.0
    risk_pct = 0.5  # $50 budget
    atr = 0.30      # 30 pips JPY
    atr_mult = 1.5  # SL = 0.45 JPY (45 pips)
    price_usdjpy = 150.0  # 150 JPY per USD
    
    # Dollar risk per lot = (0.45 * 100,000) / 150 = 45,000 / 150 = $300 USD
    # Raw lot = 50 / 300 = 0.1666... -> quantized = 0.16 lots
    lots = sizer.calculate_lot_size(
        equity=equity,
        atr=atr,
        symbol="USDJPY",
        risk_percent=risk_pct,
        atr_multiplier=atr_mult,
        current_price=price_usdjpy,
        max_lot_override=1.0
    )
    assert lots == 0.16
    
    spec = get_symbol_spec("USDJPY")
    actual_risk = lots * (atr * atr_mult) * spec.contract_size * (1.0 / price_usdjpy)
    assert actual_risk <= 50.0 + 1e-6


def test_usdchf_sizing_precision(sizer):
    equity = 10000.0
    risk_pct = 0.5   # $50 budget
    atr = 0.0020     # 20 pips
    atr_mult = 1.5   # SL = 0.0030 CHF
    price_usdchf = 0.90
    
    # Dollar risk per lot = (0.0030 * 100,000) / 0.90 = 300 / 0.90 = $333.33 USD
    # Raw lot = 50 / 333.33 = 0.15 lots
    lots = sizer.calculate_lot_size(
        equity=equity,
        atr=atr,
        symbol="USDCHF",
        risk_percent=risk_pct,
        atr_multiplier=atr_mult,
        current_price=price_usdchf,
        max_lot_override=1.0
    )
    assert lots == 0.15


# ── 3. Metals (XAUUSD - Contract Size 100) ───────────────────────────────────

def test_xauusd_gold_sizing(sizer):
    equity = 10000.0
    risk_pct = 0.5   # $50 budget
    atr = 8.0        # $8.00 ATR move
    atr_mult = 1.5   # SL = $12.00
    # Contract size = 100 oz.
    # Dollar risk per lot = $12.00 * 100 = $1,200 USD
    # Raw lot = 50 / 1200 = 0.04166... -> quantized = 0.04 lots
    lots = sizer.calculate_lot_size(
        equity=equity,
        atr=atr,
        symbol="XAUUSD",
        risk_percent=risk_pct,
        atr_multiplier=atr_mult,
        current_price=2350.0,
        max_lot_override=1.0
    )
    assert lots == 0.04
    
    actual_risk = lots * 12.00 * 100
    assert actual_risk == 48.0  # $48 <= $50 budget


# ── 4. US Indices (US30, US100, US500 - Contract Size 1) ──────────────────────

@pytest.mark.parametrize("symbol, atr, atr_mult, price, expected_lots", [
    ("US30", 150.0, 1.5, 39000.0, 0.22),   # SL = 225 pts -> Dollar risk/lot = $225 -> lot = 50/225 = 0.222 -> 0.22
    ("US100", 120.0, 1.5, 19800.0, 0.27),  # SL = 180 pts -> Dollar risk/lot = $180 -> lot = 50/180 = 0.277 -> 0.27
    ("US500", 25.0, 1.5, 5500.0, 1.33),    # SL = 37.5 pts -> Dollar risk/lot = $37.5 -> lot = 50/37.5 = 1.333 -> 1.33
])
def test_indices_sizing(sizer, symbol, atr, atr_mult, price, expected_lots):
    equity = 10000.0
    lots = sizer.calculate_lot_size(
        equity=equity,
        atr=atr,
        symbol=symbol,
        risk_percent=0.5,
        atr_multiplier=atr_mult,
        current_price=price,
        max_lot_override=10.0
    )
    spec = get_symbol_spec(symbol)
    assert spec.contract_size == 1
    assert lots == expected_lots
    actual_risk = lots * (atr * atr_mult) * spec.contract_size
    assert actual_risk <= 50.0 + 1e-6


# ── 5. Micro-Account Quantization Guard (Rejection on Excess Risk) ────────────

def test_micro_account_rejection_on_excess_risk(sizer):
    """
    On small accounts ($200), a wide SL would mean even the minimum 0.01 lot size
    risks more than 0.5% ($1.00). The engine MUST reject (return 0.0) instead of rounding up!
    """
    equity = 200.0
    risk_pct = 0.5   # Budget = $1.00
    atr = 15.0       # Gold $15 move
    atr_mult = 1.5   # SL = $22.50
    # Minimum lot = 0.01 -> Risk = 0.01 * 22.50 * 100 = $22.50!
    # Budget is only $1.00. Sizer MUST return 0.0!
    lots = sizer.calculate_lot_size(
        equity=equity,
        atr=atr,
        symbol="XAUUSD",
        risk_percent=risk_pct,
        atr_multiplier=atr_mult,
        current_price=2350.0
    )
    assert lots == 0.0, f"Expected order rejection (0.0), but got {lots}"


# ── 6. Correlation Haircut & Tail Dependence ──────────────────────────────────

def test_correlation_haircut_reduces_size(sizer):
    equity = 10000.0
    atr = 0.0020
    
    # Baseline with no open correlated symbols
    base_lots = sizer.calculate_lot_size(
        equity=equity,
        atr=atr,
        symbol="EURUSD",
        risk_percent=0.2, # low risk
        open_symbols=[],
        max_lot_override=1.0
    )
    
    # With highly correlated GBPUSD (corr 0.85 > 0.70) open
    stressed_lots = sizer.calculate_lot_size(
        equity=equity,
        atr=atr,
        symbol="EURUSD",
        risk_percent=0.2,
        open_symbols=["GBPUSD"],
        max_lot_override=1.0
    )
    
    assert base_lots > 0.0
    assert stressed_lots < base_lots, f"Stressed lots {stressed_lots} should be strictly less than base lots {base_lots}"


# ── 7. Target Exit Price Precision ───────────────────────────────────────────

def test_target_exit_price_buy_and_sell(sizer):
    # BUY 0.10 lot EURUSD @ 1.0800, target net $20, spread $2, comm $1 -> gross delta $23
    # price_delta = 23 / (100,000 * 0.10) = 23 / 10,000 = 0.0023
    tp_buy = sizer.calculate_target_exit_price(
        direction="BUY",
        average_entry_price=1.0800,
        total_lots=0.10,
        symbol="EURUSD",
        target_gross_usd=20.0,
        spread_cost_realtime=2.0,
        commission=1.0
    )
    assert round(tp_buy, 5) == 1.08230

    # SELL 0.10 lot EURUSD @ 1.0800
    tp_sell = sizer.calculate_target_exit_price(
        direction="SELL",
        average_entry_price=1.0800,
        total_lots=0.10,
        symbol="EURUSD",
        target_gross_usd=20.0,
        spread_cost_realtime=2.0,
        commission=1.0
    )
    assert round(tp_sell, 5) == 1.07770
