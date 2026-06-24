"""
NowTrading 2.1 — Symbol Definitions
Defines all tradeable symbols with their specifications.
"""

from dataclasses import dataclass
from typing import Dict
from config import settings


@dataclass(frozen=True)
class SymbolSpec:
    """Specification for a tradeable symbol."""
    name: str               # MT5 symbol name
    category: str           # "FX", "INDEX", "GOLD", "CRYPTO"
    pip_size: float         # Size of 1 pip in price terms
    default_lot: float      # Default lot size
    spread_limit: float     # Max allowed spread (pips or points)
    contract_size: float    # Contract size (units per lot)
    description: str        # Human-readable description


# ── Symbol Registry ─────────────────────────────────────────

SYMBOLS: Dict[str, SymbolSpec] = {
    # ── FX Majors ──
    "EURUSD": SymbolSpec(
        name="EURUSDm", category="FX",
        pip_size=0.0001, default_lot=settings.FX_BASE_LOT,
        spread_limit=settings.SPREAD_LIMIT_FX,
        contract_size=100_000, description="Euro / US Dollar"
    ),
    "GBPUSD": SymbolSpec(
        name="GBPUSDm", category="FX",
        pip_size=0.0001, default_lot=settings.FX_BASE_LOT,
        spread_limit=settings.SPREAD_LIMIT_FX,
        contract_size=100_000, description="British Pound / US Dollar"
    ),
    "USDJPY": SymbolSpec(
        name="USDJPYm", category="FX",
        pip_size=0.01, default_lot=settings.FX_BASE_LOT,
        spread_limit=settings.SPREAD_LIMIT_FX,
        contract_size=100_000, description="US Dollar / Japanese Yen"
    ),
    "AUDUSD": SymbolSpec(
        name="AUDUSDm", category="FX",
        pip_size=0.0001, default_lot=settings.FX_BASE_LOT,
        spread_limit=settings.SPREAD_LIMIT_FX,
        contract_size=100_000, description="Australian Dollar / US Dollar"
    ),
    "USDCHF": SymbolSpec(
        name="USDCHFm", category="FX",
        pip_size=0.0001, default_lot=settings.FX_BASE_LOT,
        spread_limit=settings.SPREAD_LIMIT_FX,
        contract_size=100_000, description="US Dollar / Swiss Franc"
    ),
    "USDCAD": SymbolSpec(
        name="USDCADm", category="FX",
        pip_size=0.0001, default_lot=settings.FX_BASE_LOT,
        spread_limit=settings.SPREAD_LIMIT_FX,
        contract_size=100_000, description="US Dollar / Canadian Dollar"
    ),
    "NZDUSD": SymbolSpec(
        name="NZDUSDm", category="FX",
        pip_size=0.0001, default_lot=settings.FX_BASE_LOT,
        spread_limit=settings.SPREAD_LIMIT_FX,
        contract_size=100_000, description="New Zealand Dollar / US Dollar"
    ),

    # ── US Indices ──
    "US30": SymbolSpec(
        name="US30m", category="INDEX",
        pip_size=0.01, default_lot=settings.MAX_LOT_SIZE,
        spread_limit=settings.SPREAD_LIMIT_INDEX,
        contract_size=1, description="Dow Jones 30"
    ),
    "US100": SymbolSpec(
        name="USTECm", category="INDEX",
        pip_size=0.01, default_lot=settings.MAX_LOT_SIZE,
        spread_limit=settings.SPREAD_LIMIT_INDEX,
        contract_size=1, description="NASDAQ 100"
    ),
    "US500": SymbolSpec(
        name="US500m", category="INDEX",
        pip_size=0.01, default_lot=settings.MAX_LOT_SIZE,
        spread_limit=settings.SPREAD_LIMIT_INDEX,
        contract_size=1, description="S&P 500"
    ),

    # ── Gold ──
    "XAUUSD": SymbolSpec(
        name="XAUUSDm", category="GOLD",
        pip_size=0.01, default_lot=settings.COMMODITY_BASE_LOT,
        spread_limit=settings.SPREAD_LIMIT_GOLD,
        contract_size=100, description="Gold / US Dollar"
    ),

    # ── Crypto ──
    "BTCUSD": SymbolSpec(
        name="BTCUSDm", category="CRYPTO",
        pip_size=0.01, default_lot=settings.CRYPTO_BASE_LOT,
        spread_limit=settings.SPREAD_LIMIT_CRYPTO,
        contract_size=1, description="Bitcoin / US Dollar"
    ),
}


def get_symbol_spec(symbol: str) -> SymbolSpec:
    """Get symbol specification by key. Raises KeyError if not found."""
    if symbol not in SYMBOLS:
        raise KeyError(
            f"Symbol '{symbol}' not found. "
            f"Available: {list(SYMBOLS.keys())}"
        )
    return SYMBOLS[symbol]


def get_all_symbols() -> list:
    """Return list of all symbol keys."""
    return list(SYMBOLS.keys())


def get_spread_limit(symbol: str) -> float:
    """Get spread limit for a symbol in pips/points."""
    return get_symbol_spec(symbol).spread_limit


def get_mt5_name(symbol: str) -> str:
    """Get the MT5 terminal symbol name (may differ from key)."""
    return get_symbol_spec(symbol).name
