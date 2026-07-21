from typing import Optional
from config.symbols import get_symbol_spec

class PositionSizer:
    """
    Manages volatility-adjusted capital allocation and calculates 
    precise, risk-managed lot sizes and target net profits.
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
        ml_score: Optional[float] = None
    ) -> float:
        """
        Calculates a volatility-adjusted lot size based on ATR and equity risk,
        incorporating 3-tier ML dynamic scaling for FX and INDEX symbols.
        Formula:
          Risk USD = Equity * Risk Percent
          SL Distance = ATR * ATR Multiplier
          Lots = Risk USD / (SL Distance * Contract Size)
        """
        if atr <= 0.0 or equity <= 0.0:
            return 0.01  # Minimum fallback

        spec = get_symbol_spec(symbol)
        sl_distance = atr * atr_multiplier
        risk_usd = equity * (risk_percent / 100.0) * self.risk_multiplier

        # Lot calculation based on contract specifications
        raw_lot = risk_usd / (sl_distance * spec.contract_size)

        # Apply ML scaling for INDEX or FX if ml_score is provided
        from config import settings
        if ml_score is not None and spec.category in ["FX", "INDEX"]:
            if ml_score < getattr(settings, "ML_LOT_BOOST_THRESHOLD", 0.25):
                raw_lot = raw_lot * getattr(settings, "ML_LOT_BOOST_MULTIPLIER", 1.5)
            elif ml_score > getattr(settings, "ML_LOT_REDUCE_THRESHOLD", 0.45):
                raw_lot = raw_lot * getattr(settings, "ML_LOT_REDUCE_MULTIPLIER", 0.7)

        # Giới hạn Lot size trần (Cap logic) theo nhóm tài sản trên mỗi $1000 Equity
        # Nhằm bảo vệ tài khoản khi biến động ATR quá hẹp (sideway tích lũy)
        category_caps = {
            "FX": 0.10,      # Tối đa 0.10 lots / $1000 equity
            "INDEX": 0.05,   # Tối đa 0.05 lots / $1000 equity (Ngăn chặn sự cố US500)
            "GOLD": 0.02,    # Tối đa 0.02 lots / $1000 equity
            "CRYPTO": 0.05   # Tối đa 0.05 lots / $1000 equity
        }
        
        category = spec.category
        base_cap = category_caps.get(category, 0.05)
        scaled_cap = base_cap * (equity / 1000.0)
        
        # Đồng thời tuân thủ cấu hình MAX_LOT_SIZE toàn hệ thống
        global_max_lot = getattr(settings, "MAX_LOT_SIZE", 0.10)
        
        final_cap = min(scaled_cap, global_max_lot)
        final_lot = min(raw_lot, final_cap)

        return max(0.01, float(final_lot))

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
