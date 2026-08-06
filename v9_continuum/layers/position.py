from typing import Optional, Dict, Tuple, List
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

class PositionSizer:
    """
    Manages volatility-adjusted capital allocation, Volatility-Scaled Fractional Kelly,
    Risk Parity ATR Sizing, and Covariance/Correlation Risk Alignment.
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
        open_symbols: Optional[List[str]] = None
    ) -> float:
        """
        Calculates a Volatility-Scaled Fractional Kelly / Risk Parity ATR lot size.
        Enforces Correlation Matrix Scaling (> 0.7 corr -> scale down) and
        Total Portfolio Risk Constraint (<= 1.5% Equity across active positions).
        """
        if atr <= 0.0 or equity <= 0.0:
            return 0.01  # Minimum fallback

        spec = get_symbol_spec(symbol)
        sl_distance = atr * atr_multiplier
        # Fixed 0.02 lot size for Phase 1 Live Deployment (Equity < 1000.0)
        if equity < 1000.0:
            return 0.02

        # Enforce strict 1.0% risk per trade cap for equity >= 1000.0
        effective_risk_pct = min(risk_percent, 1.0)
        risk_usd = equity * (effective_risk_pct / 100.0) * self.risk_multiplier

        # 1. Equal Risk Parity Lot Calculation (Dollar ATR Risk)
        raw_lot = risk_usd / (sl_distance * spec.contract_size)

        # 2. Apply Dynamic ML Score Scaling (LOCKED if equity < 1000.0)
        from config import settings
        if equity >= 1000.0 and ml_score is not None and spec.category in ["FX", "INDEX"]:
            if ml_score < getattr(settings, "ML_LOT_BOOST_THRESHOLD", 0.25):
                raw_lot = raw_lot * getattr(settings, "ML_LOT_BOOST_MULTIPLIER", 1.5)
            elif ml_score > getattr(settings, "ML_LOT_REDUCE_THRESHOLD", 0.45):
                raw_lot = raw_lot * getattr(settings, "ML_LOT_REDUCE_MULTIPLIER", 0.7)

        # 3. Covariance & Correlation Risk Alignment
        # Scale down lot size if new trade is highly correlated (> 0.7) with active positions
        corr_scale_factor = 1.0
        if open_symbols:
            max_corr = 0.0
            for active_sym in open_symbols:
                corr = abs(get_symbol_correlation(symbol, active_sym))
                if corr > max_corr:
                    max_corr = corr
            if max_corr > 0.70:
                # Scale down proportionally: 0.70 -> 1.0, 0.95 -> 0.625
                corr_scale_factor = max(0.40, 1.0 - (max_corr - 0.70) * 1.5)

        raw_lot = raw_lot * corr_scale_factor

        # 4. Total Portfolio Risk Constraint (Max 1.5% Equity across open positions)
        max_portfolio_risk_pct = getattr(settings, "MAX_PORTFOLIO_RISK_PCT", 1.5)
        max_lot_portfolio = (equity * (max_portfolio_risk_pct / 100.0)) / (sl_distance * spec.contract_size)
        
        # 5. Global Max Lot Cap
        global_max_lot = getattr(settings, "MAX_LOT_SIZE", 0.10)
        
        final_lot = min(raw_lot, max_lot_portfolio, global_max_lot)
        return max(0.01, float(round(final_lot, 4)))

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
          For BUY: Target Price = Avg Entry + Target Profit Net / (Contract Size * Lots)
          For SELL: Target Price = Avg Entry - Target Profit Net / (Contract Size * Lots)
          Note: If quote currency is not USD (ends with JPY/CHF/CAD), we scale target_profit_net
          by average_entry_price to convert the USD target to the quote currency.
        """
        if total_lots <= 0.0:
            return average_entry_price

        spec = get_symbol_spec(symbol)
        target_profit_net = target_gross_usd + spread_cost_realtime + commission
        
        if symbol.endswith("JPY") or symbol.endswith("CHF") or symbol.endswith("CAD"):
            price_delta = (target_profit_net * average_entry_price) / (spec.contract_size * total_lots)
        else:
            price_delta = target_profit_net / (spec.contract_size * total_lots)
        
        if direction == "BUY":
            target_price = average_entry_price + price_delta
        else:
            target_price = average_entry_price - price_delta

        return float(target_price)
