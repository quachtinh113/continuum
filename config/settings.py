"""
NowTrading 2.1 — Settings Module
Loads all configuration from .env file with safe defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ───────────────────────────────────────────────
_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / ".env"

if _env_path.exists():
    load_dotenv(_env_path)
else:
    # Fallback to .env.example for reference
    _example = _project_root / ".env.example"
    if _example.exists():
        load_dotenv(_example)


# ── Helper ──────────────────────────────────────────────────
def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _int(key: str, default: int = 0) -> int:
    return int(_get(key, str(default)))


def _float(key: str, default: float = 0.0) -> float:
    return float(_get(key, str(default)))


def _bool(key: str, default: bool = False) -> bool:
    return _get(key, str(default)).lower() in ("true", "1", "yes")


# ── MT5 Credentials ────────────────────────────────────────
MT5_ACCOUNT: int = _int("MT5_ACCOUNT", 0)
MT5_PASSWORD: str = _get("MT5_PASSWORD", "")
MT5_SERVER: str = _get("MT5_SERVER", "Exness-MT5Trial7")
MT5_PATH: str = _get("MT5_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe")

# ── Trading Mode ────────────────────────────────────────────
LIVE_TRADING: bool = _bool("LIVE_TRADING", False)

# ── Risk Parameters ────────────────────────────────────────
FX_BASE_LOT: float = _float("FX_BASE_LOT", 0.02)
COMMODITY_BASE_LOT: float = _float("COMMODITY_BASE_LOT", 0.01)
CRYPTO_BASE_LOT: float = _float("CRYPTO_BASE_LOT", 0.01)
MAX_LOT_SIZE: float = _float("MAX_LOT_SIZE", 0.01)
RISK_PER_TRADE_PERCENT: float = _float("RISK_PER_TRADE_PERCENT", 0.1)
MAX_DCA_LAYERS: int = _int("MAX_DCA_LAYERS", 3)
DCA_LOT_STYLE: str = _get("DCA_LOT_STYLE", "DYNAMIC")
DCA_LOTS_STR: str = _get("DCA_LOTS", "")
DCA_LOTS: list = [float(x.strip()) for x in DCA_LOTS_STR.split(",") if x.strip()] if DCA_LOTS_STR else []
DCA_STEP_PIPS: float = _float("DCA_STEP_PIPS", 0.0)
TAKE_PROFIT_PIPS: float = _float("TAKE_PROFIT_PIPS", 0.0)
HARD_STOP_LOSS_PIPS: float = _float("HARD_STOP_LOSS_PIPS", 0.0)
MAX_DAILY_DRAWDOWN_USD: float = _float("MAX_DAILY_DRAWDOWN_USD", 50.0)
MAX_ACTIVE_CYCLES: int = _int("MAX_ACTIVE_CYCLES", 5)
PROFIT_TARGET_USD: float = _float("PROFIT_TARGET_USD", 5.0)
TAKE_PROFIT_ATR_MULTIPLIER: float = _float("TAKE_PROFIT_ATR_MULTIPLIER", 1.5)
BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER: float = _float("BREAK_EVEN_ACTIVATION_ATR_MULTIPLIER", 1.25)
BREAK_EVEN_BUFFER_ATR_MULTIPLIER: float = _float("BREAK_EVEN_BUFFER_ATR_MULTIPLIER", -0.05)

# ── Indicator Parameters ───────────────────────────────────
RSI_PERIOD: int = _int("RSI_PERIOD", 14)
RSI_BUY_THRESHOLD: float = _float("RSI_BUY_THRESHOLD", 55.0)
RSI_SELL_THRESHOLD: float = _float("RSI_SELL_THRESHOLD", 45.0)
RSI_PULLBACK_THRESHOLD: float = _float("RSI_PULLBACK_THRESHOLD", 50.0)
STRICT_PULLBACK_EXHAUSTION: bool = _bool("STRICT_PULLBACK_EXHAUSTION", True)
ADX_PERIOD: int = _int("ADX_PERIOD", 14)
ADX_RANGE_THRESHOLD: float = _float("ADX_RANGE_THRESHOLD", 18.0)
ADX_TREND_THRESHOLD: float = _float("ADX_TREND_THRESHOLD", 25.0)
ATR_PERIOD: int = _int("ATR_PERIOD", 14)

# ── DCA Parameters ─────────────────────────────────────────
DCA_LAYER_1_ATR: float = _float("DCA_LAYER_1_ATR", 2.0)
DCA_LAYER_2_ATR: float = _float("DCA_LAYER_2_ATR", 3.0)
DCA_LAYER_3_ATR: float = _float("DCA_LAYER_3_ATR", 4.0)

# ── Strategy Parameters ────────────────────────────────────
PULLBACK_LOOKBACK_BARS: int = _int("PULLBACK_LOOKBACK_BARS", 5)
EMERGENCY_EVENT_MODE: bool = _bool("EMERGENCY_EVENT_MODE", False)
MAX_TICK_AGE_SECONDS: int = _int("MAX_TICK_AGE_SECONDS", 120)

# ── Time Rules ──────────────────────────────────────────────
HOLDING_REDUCE_HOURS: int = _int("HOLDING_REDUCE_HOURS", 24)
HOLDING_MAX_HOURS: int = _int("HOLDING_MAX_HOURS", 48)
HOURLY_GATE_WINDOW_MINUTES: int = _int("HOURLY_GATE_WINDOW_MINUTES", 5)

# ── Spread Limits ──────────────────────────────────────────
SPREAD_LIMIT_FX: float = _float("SPREAD_LIMIT_FX", 5.0)
SPREAD_LIMIT_INDEX: float = _float("SPREAD_LIMIT_INDEX", 50.0)
SPREAD_LIMIT_GOLD: float = _float("SPREAD_LIMIT_GOLD", 50.0)
SPREAD_LIMIT_CRYPTO: float = _float("SPREAD_LIMIT_CRYPTO", 100.0)

# ── Resilience & Recovery ──────────────────────────────────
MT5_RECONNECT_MAX_RETRIES: int = _int("MT5_RECONNECT_MAX_RETRIES", 3)
MT5_RECONNECT_BACKOFF: str = _get("MT5_RECONNECT_BACKOFF", "5,10,30")
MT5_HEALTH_CHECK_INTERVAL: int = _int("MT5_HEALTH_CHECK_INTERVAL", 5)
CIRCUIT_BREAKER_THRESHOLD: int = _int("CIRCUIT_BREAKER_THRESHOLD", 5)
WEEKEND_SLEEP_SECONDS: int = _int("WEEKEND_SLEEP_SECONDS", 300)
DATA_SYNC_WAIT_SECONDS: int = _int("DATA_SYNC_WAIT_SECONDS", 30)
ERROR_LOG_THROTTLE_SECONDS: int = _int("ERROR_LOG_THROTTLE_SECONDS", 300)

# ── Dynamic Exit Thresholds ──────────────────────────────
ATR_DCA_CHECK_MULTIPLIER: float = _float("ATR_DCA_CHECK_MULTIPLIER", 2.0)
RSI_OVEREXTENDED_LOW: float = _float("RSI_OVEREXTENDED_LOW", 30.0)
RSI_OVEREXTENDED_HIGH: float = _float("RSI_OVEREXTENDED_HIGH", 70.0)

# ── ML Gatekeeper Parameters ─────────────────────────────────
ML_GATEKEEPER_ACTIVE: bool = _bool("ML_GATEKEEPER_ACTIVE", True)
ML_VETO_THRESHOLD: float = _float("ML_VETO_THRESHOLD", 0.85)
ML_ENTRY_SAFE_THRESHOLD: float = _float("ML_ENTRY_SAFE_THRESHOLD", 0.35)
ML_VETO_THRESHOLD_L0: float = _float("ML_VETO_THRESHOLD_L0", 0.75)
ML_VETO_THRESHOLD_L1: float = _float("ML_VETO_THRESHOLD_L1", 0.68)
ML_VETO_THRESHOLD_L2: float = _float("ML_VETO_THRESHOLD_L2", 0.58)
ML_VETO_THRESHOLD_L3: float = _float("ML_VETO_THRESHOLD_L3", 0.50)
ML_MODE: str = _get("ML_MODE", "AUDIT_ENABLED")
# Dynamic lot scaling based on ML confidence score (3-tier system)
ML_LOT_BOOST_THRESHOLD: float = _float("ML_LOT_BOOST_THRESHOLD", 0.25)   # Score < this → lot ×BOOST
ML_LOT_REDUCE_THRESHOLD: float = _float("ML_LOT_REDUCE_THRESHOLD", 0.45) # Score > this → lot ×REDUCE
ML_LOT_BOOST_MULTIPLIER: float = _float("ML_LOT_BOOST_MULTIPLIER", 1.5)  # ×1.5 when high confidence
ML_LOT_REDUCE_MULTIPLIER: float = _float("ML_LOT_REDUCE_MULTIPLIER", 0.7) # ×0.7 when caution

# ── Logging ─────────────────────────────────────────────────
LOG_DIR: str = _get("LOG_DIR", "logs")
LOG_LEVEL: str = _get("LOG_LEVEL", "INFO")

# ── Derived Paths ──────────────────────────────────────────
PROJECT_ROOT: Path = _project_root
LOG_PATH: Path = _project_root / LOG_DIR

# Ensure log dir exists
LOG_PATH.mkdir(parents=True, exist_ok=True)
