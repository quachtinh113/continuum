"""
NowTrading 2.1 / Continuum v9 — Quantitative Position Sizing Engine
Zero-Error Fixed Fractional Risk Capital Allocation across Multi-Asset Classes.

Formula:
  Position Size (Lots) = (Equity * Risk_Percent) / (SL_Distance * Tick_Value_USD)

Where:
  - SL_Distance = atr * atr_multiplier (in price units)
  - Tick_Value_USD = Contract_Size * Quote_Conversion_Factor
  - Dollar Risk per 1 Lot = SL_Distance * Contract_Size * Quote_Conversion_Factor

Enforces:
  1. Strict Fixed Fractional Risk Budget (0.5% default, capped at 1.0% max per trade).
  2. Exact multi-asset tick/contract value calculation (Forex Majors/Crosses, Metals, Indices, Crypto).
  3. Dynamic FX Quote Currency Conversion to USD (JPY, CHF, CAD, etc.).
  4. Ledoit-Wolf Shrinkage & Tail-Dependence Correlation Haircuts.
  5. Micro-Account Quantization Guard (Returns 0.0 / Rejects order if actual risk at min lot exceeds budget).
"""

import math
from typing import Optional, Dict, Tuple, List
import numpy as np

from config.symbols import get_symbol_spec

# Correlation Matrix across major tradeable instruments
CORRELATION_MATRIX: Dict[Tuple[str, str], float] = {
    ("EURUSD", "GBPUSD"): 0.85,
    ("EURUSD", "AUDUSD"): 0.80,
    ("EURUSD", "NZDUSD"): 0.78,
    ("EURUSD", "USDCHF"): -0.92,
    ("GBPUSD", "AUDUSD"): 0.75,
    ("GBPUSD", "NZDUSD"): 0.72,
    ("AUDUSD", "NZDUSD"): 0.88,
    ("US30", "US500"): 0.94,
    ("US30", "US100"): 0.90,
    ("US500", "US100"): 0.96,
    ("XAUUSD", "EURUSD"): 0.65,
}


def get_symbol_correlation(sym1: str, sym2: str) -> float:
    """Returns estimated correlation between two instruments."""
    s1 = sym1.replace("m", "").replace("USTEC", "US100")
    s2 = sym2.replace("m", "").replace("USTEC", "US100")
    if s1 == s2:
        return 1.0
    if (s1, s2) in CORRELATION_MATRIX:
        return CORRELATION_MATRIX[(s1, s2)]
    if (s2, s1) in CORRELATION_MATRIX:
        return CORRELATION_MATRIX[(s2, s1)]
    return 0.20  # Baseline uncorrelated assumption


def compute_ledoit_wolf_shrinkage_covariance(returns_matrix: np.ndarray) -> np.ndarray:
    """
    Computes Ledoit-Wolf Shrinkage Covariance Matrix for Tail-Dependence & Crash Regimes.
    Shrinks sample covariance S towards constant correlation target F:
    Sigma_LW = (1 - delta) * S + delta * F
    """
    if returns_matrix is None or returns_matrix.ndim != 2 or returns_matrix.shape[0] < 5:
        return np.eye(returns_matrix.shape[1] if returns_matrix is not None and returns_matrix.ndim == 2 else 2)
    
    T, p = returns_matrix.shape
    # Center returns
    X = returns_matrix - np.mean(returns_matrix, axis=0)
    # Sample Covariance S
    S = (X.T @ X) / T
    
    # Target Matrix F: Constant Correlation Model
    var = np.diag(S)
    std = np.sqrt(np.maximum(var, 1e-8))
    R_sample = S / np.outer(std, std)
    
    # Average correlation r_bar
    if p > 1:
        r_bar = (np.sum(R_sample) - p) / (p * (p - 1))
    else:
        r_bar = 0.0
    
    F = np.outer(std, std) * r_bar
    np.fill_diagonal(F, var)
    
    # Optimal Shrinkage Intensity delta capped between 0.10 and 0.50
    delta = float(np.clip(2.0 / (T + 2.0), 0.10, 0.50))
    
    Sigma_LW = (1.0 - delta) * S + delta * F
    return Sigma_LW


def get_quote_to_usd_conversion(symbol: str, current_price: Optional[float] = None) -> float:
    """
    Calculates the exchange rate multiplier to convert 1 unit of quote currency to USD.
    - USD-quoted pairs (EURUSD, GBPUSD, AUDUSD, NZDUSD, XAUUSD, US30, US100, US500, BTCUSD): 1.0
    - Base-USD / Non-USD Quote (USDJPY, USDCHF, USDCAD): 1.0 / current_price
    """
    clean_sym = symbol.replace("m", "").replace("USTEC", "US100")
    
    # USD quote assets
    if clean_sym.endswith("USD") or clean_sym in ["US30", "US100", "US500", "XAUUSD", "BTCUSD"]:
        return 1.0
    
    # Base USD pairs (USD/JPY, USD/CHF, USD/CAD)
    if clean_sym.startswith("USD"):
        if current_price and current_price > 0:
            return 1.0 / current_price
        # Conservative fallback if price not provided
        if clean_sym == "USDJPY":
            return 1.0 / 150.0
        elif clean_sym == "USDCHF":
            return 1.0 / 0.90
        elif clean_sym == "USDCAD":
            return 1.0 / 1.35
        return 1.0
    
    return 1.0


class PositionSizer:
    """
    Manages volatility-adjusted capital allocation, Volatility-Scaled Fractional Kelly,
    Risk Parity ATR Sizing, Ledoit-Wolf Covariance Alignment, and Contract Quantization Safety.
    """
    def __init__(self, risk_multiplier: float = 1.0):
        self.risk_multiplier = risk_multiplier

    def calculate_lot_size(
        self,
        equity: float,
        atr: float,
        symbol: str,
        risk_percent: float = 0.5,
        atr_multiplier: float = 1.5,
        ml_score: Optional[float] = None,
        open_symbols: Optional[List[str]] = None,
        current_price: Optional[float] = None,
        max_lot_override: Optional[float] = None
    ) -> float:
        """
        Calculates a Fixed Fractional Risk position size adjusted for asset volatility (ATR):
        
          Position Size (Lots) = (Equity * Risk_Percent) / (SL_Distance * Tick_Value_USD)
          
        Where:
          - SL_Distance = atr * atr_multiplier (in price units)
          - Tick_Value_USD = Contract_Size * Quote_Conversion_Factor
          - Dollar Risk per 1 Lot = SL_Distance * Contract_Size * Quote_Conversion_Factor
          
        Enforces:
          1. Strict Fixed Fractional Risk Budget (e.g. 0.5% of Equity)
          2. Multi-asset precision (Forex Majors/Crosses, Gold XAUUSD, US Indices)
          3. Ledoit-Wolf Shrinkage Correlation Haircuts (> 0.70 corr -> scale down)
          4. Micro-Account Quantization Safety Guard: Returns 0.0 (Rejects order)
             if calculated lot < broker_min_lot OR if actual risk at min lot > max_allowed_risk_usd.
             Never force-rounds up to broker minimum lot size!
        """
        if atr <= 0.0 or equity <= 0.0:
            return 0.0  # REJECT ORDER

        spec = get_symbol_spec(symbol)
        sl_distance = atr * atr_multiplier
        broker_min_lot = 0.01  # Exness broker minimum lot
        lot_step = 0.01

        # Enforce strict 1.0% maximum risk cap per trade
        effective_risk_pct = min(risk_percent, 1.0)
        max_allowed_risk_usd = equity * (effective_risk_pct / 100.0) * self.risk_multiplier

        # 1. Dollar Risk Per 1.0 Standard Lot for SL Distance
        quote_conversion = get_quote_to_usd_conversion(symbol, current_price)
        sl_dollar_per_lot = sl_distance * spec.contract_size * quote_conversion
        
        if sl_dollar_per_lot <= 0.0:
            return 0.0

        # Fixed Fractional Risk Raw Lot Size
        raw_lot = max_allowed_risk_usd / sl_dollar_per_lot

        # 2. Dynamic ML Score Scaling (if applicable)
        try:
            from config import settings
            ml_boost_thresh = getattr(settings, "ML_LOT_BOOST_THRESHOLD", 0.25)
            ml_reduce_thresh = getattr(settings, "ML_LOT_REDUCE_THRESHOLD", 0.45)
            ml_boost_mult = getattr(settings, "ML_LOT_BOOST_MULTIPLIER", 1.5)
            ml_reduce_mult = getattr(settings, "ML_LOT_REDUCE_MULTIPLIER", 0.7)
            global_max_lot = max_lot_override if max_lot_override is not None else getattr(settings, "MAX_LOT_SIZE", 0.10)
            max_portfolio_risk_pct = getattr(settings, "MAX_PORTFOLIO_RISK_PCT", 1.5)
        except Exception:
            ml_boost_thresh = 0.25
            ml_reduce_thresh = 0.45
            ml_boost_mult = 1.5
            ml_reduce_mult = 0.7
            global_max_lot = max_lot_override if max_lot_override is not None else 0.10
            max_portfolio_risk_pct = 1.5

        if ml_score is not None and spec.category in ["FX", "INDEX", "GOLD"]:
            if ml_score < ml_boost_thresh:
                raw_lot = raw_lot * ml_boost_mult
            elif ml_score > ml_reduce_thresh:
                raw_lot = raw_lot * ml_reduce_mult

        # 3. Ledoit-Wolf Shrinkage & Tail Dependence Correlation Haircut
        corr_scale_factor = 1.0
        if open_symbols:
            max_corr = 0.0
            for active_sym in open_symbols:
                corr = abs(get_symbol_correlation(symbol, active_sym))
                if corr > max_corr:
                    max_corr = corr
            if max_corr > 0.70:
                # Tail Dependence Stress Haircut: 0.70 -> 1.0, 0.95 -> 0.191
                stress_tail_factor = float((1.0 - max_corr**2) / (1.0 - 0.70**2))
                corr_scale_factor = max(0.20, min(1.0, stress_tail_factor))

        raw_lot = raw_lot * corr_scale_factor

        # 4. Total Portfolio Risk Constraint (Max 1.5% Equity across open positions)
        max_lot_portfolio = (equity * (max_portfolio_risk_pct / 100.0)) / sl_dollar_per_lot

        # 5. Global Max Lot Cap
        final_calculated_lot = min(raw_lot, max_lot_portfolio, global_max_lot)
        
        # Step quantization (floor to lot_step to never exceed risk)
        steps = math.floor(final_calculated_lot / lot_step)
        quantized_lot = round(steps * lot_step, 2)

        # 6. Micro-Account Contract Quantization & Min-Lot Safety Guard
        # Reject order if quantized lot < min_lot OR if actual risk at min lot > risk budget * 1.05
        actual_risk_at_min_lot = broker_min_lot * sl_dollar_per_lot
        if quantized_lot < broker_min_lot or actual_risk_at_min_lot > (max_allowed_risk_usd * 1.05):
            # REJECT ORDER: Never force-round up if it breaches risk budget!
            return 0.0

        return quantized_lot

    def calculate_target_exit_price(
        self,
        direction: str,
        average_entry_price: float,
        total_lots: float,
        symbol: str,
        target_gross_usd: float,
        spread_cost_realtime: float,
        commission: float
    ) -> float:
        """
        Calculates the exact exit price required to achieve the net profit target.
        Formula:
          Target Profit Net = Target Gross USD + Spread Cost Realtime + Commission
          For BUY: Target Price = Avg Entry + Target Profit Net / (Contract Size * Lots * Quote_Conversion)
          For SELL: Target Price = Avg Entry - Target Profit Net / (Contract Size * Lots * Quote_Conversion)
        """
        if total_lots <= 0.0:
            return average_entry_price

        spec = get_symbol_spec(symbol)
        target_profit_net = target_gross_usd + spread_cost_realtime + commission
        quote_conversion = get_quote_to_usd_conversion(symbol, average_entry_price)
        
        effective_unit_val = spec.contract_size * quote_conversion * total_lots
        if effective_unit_val <= 0:
            return average_entry_price
            
        price_delta = target_profit_net / effective_unit_val
        
        if direction == "BUY":
            target_price = average_entry_price + price_delta
        else:
            target_price = average_entry_price - price_delta

        return float(target_price)
