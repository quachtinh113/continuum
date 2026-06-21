"""
NowTrading 2.1 — MTF RSI Builder (Build Step 1)
Builds multi-timeframe RSI, ADX, ATR indicators for a given symbol.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

import pandas as pd
import pandas_ta as ta

from src.mt5_connector import MT5Connector
from src.audit_logger import log_error
from config import settings


from typing import Optional, Dict, Any

# Indicator result type
IndicatorData = Dict[str, Any]


class MTFRSIBuilder:
    """
    Multi-Timeframe RSI Builder.

    Fetches candle data from H4, H1, M15 timeframes and computes:
    - RSI on each timeframe
    - ADX from H1 (primary trend strength)
    - ATR from H1 (primary DCA spacing)
    - ATR from M15 (fine-grained DCA spacing)
    """

    # Minimum bars required per timeframe
    MIN_BARS = 50

    # Maximum data age before considered stale (minutes)
    MAX_DATA_AGE_MINUTES = 5

    def __init__(self, connector: MT5Connector):
        self._connector = connector

    def build_indicators(self, symbol: str) -> Optional[IndicatorData]:
        """
        Build all indicators for a symbol across multiple timeframes.

        Args:
            symbol: Symbol key (e.g. "EURUSD")

        Returns:
            Dict with RSI_H4, RSI_H1, RSI_M15, ADX, ATR, ATR_M15
            or None if data is insufficient or stale.
        """
        # Fetch candle data for each timeframe
        df_h4 = self._connector.get_rates(symbol, "H4", count=self.MIN_BARS)
        df_h1 = self._connector.get_rates(symbol, "H1", count=self.MIN_BARS)
        df_m15 = self._connector.get_rates(symbol, "M15", count=self.MIN_BARS)

        # Validate data availability
        if df_h4 is None or df_h1 is None or df_m15 is None:
            log_error(
                f"Missing MTF data for {symbol}",
                H4=df_h4 is not None,
                H1=df_h1 is not None,
                M15=df_m15 is not None,
            )
            return None

        # Validate minimum bar count
        for label, df in [("H4", df_h4), ("H1", df_h1), ("M15", df_m15)]:
            if len(df) < self.MIN_BARS:
                log_error(
                    f"Insufficient bars for {symbol} {label}: "
                    f"got {len(df)}, need {self.MIN_BARS}"
                )
                return None

        # Check data freshness (M15 is the fastest timeframe)
        if not self._is_fresh(df_m15):
            log_error(f"Stale data for {symbol} M15")
            return None

        # Compute indicators
        rsi_h4 = self._compute_rsi(df_h4)
        rsi_h1 = self._compute_rsi(df_h1)
        rsi_m15, rsi_m15_series = self._compute_rsi_with_series(df_m15)
        adx = self._compute_adx(df_h1)
        atr_h1 = self._compute_atr(df_h1)
        atr_m15 = self._compute_atr(df_m15)

        # Compute Pullback Exhaustion Features (M15)
        pullback = self._compute_pullback_features(df_m15, rsi_m15_series)

        # Validate all indicators computed successfully
        indicators: IndicatorData = {
            "RSI_H4": rsi_h4,
            "RSI_H1": rsi_h1,
            "RSI_M15": rsi_m15,
            "ADX": adx,
            "ATR": atr_h1,
            "ATR_M15": atr_m15,
        }

        # Merge pullback features
        indicators.update(pullback)

        # Check for None or NaN values (Data Quality Constitution §16)
        missing = [k for k, v in indicators.items() if v is None or (isinstance(v, float) and pd.isna(v))]
        if missing:
            log_error(
                f"Failed to compute indicators or NaN found for {symbol}",
                missing=missing,
            )
            return None

        return indicators

    # ── Indicator Computation ───────────────────────────────

    def _compute_rsi(self, df: pd.DataFrame) -> Optional[float]:
        """Compute RSI from close prices. Returns latest value."""
        val, _ = self._compute_rsi_with_series(df)
        return val

    def _compute_rsi_with_series(self, df: pd.DataFrame) -> tuple[Optional[float], Optional[pd.Series]]:
        """Compute RSI and return both latest value and the full series (needed for pullback)."""
        try:
            rsi = ta.rsi(df["close"], length=settings.RSI_PERIOD)
            if rsi is None or rsi.empty:
                return None, None
            value = rsi.iloc[-1]
            return (float(value) if pd.notna(value) else None), rsi
        except Exception as e:
            log_error(f"RSI computation error: {e}")
            return None, None

    def _compute_adx(self, df: pd.DataFrame) -> Optional[float]:
        """Compute ADX from OHLC data. Returns latest value."""
        try:
            adx_df = ta.adx(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                length=settings.ADX_PERIOD,
            )
            if adx_df is None or adx_df.empty:
                return None
            # ADX column name is typically "ADX_14"
            adx_col = f"ADX_{settings.ADX_PERIOD}"
            if adx_col not in adx_df.columns:
                # Fallback: take the first column that contains "ADX"
                adx_cols = [c for c in adx_df.columns if "ADX" in c]
                if not adx_cols:
                    return None
                adx_col = adx_cols[0]

            value = adx_df[adx_col].iloc[-1]
            return float(value) if pd.notna(value) else None
        except Exception as e:
            log_error(f"ADX computation error: {e}")
            return None

    def _compute_atr(self, df: pd.DataFrame) -> Optional[float]:
        """Compute ATR from OHLC data. Returns latest value."""
        try:
            atr = ta.atr(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                length=settings.ATR_PERIOD,
            )
            if atr is None or atr.empty:
                return None
            value = atr.iloc[-1]
            return float(value) if pd.notna(value) else None
        except Exception as e:
            log_error(f"ATR computation error: {e}")
            return None

    def _compute_pullback_features(self, df: pd.DataFrame, rsi: Optional[pd.Series]) -> Dict[str, Any]:
        """
        Compute Pullback Exhaustion Confirmation features (Constitution §7).
        """
        features = {
            "M15_RSI_RISING": False,
            "M15_RSI_FALLING": False,
            "M15_CLOSE_RISING": False,
            "M15_CLOSE_FALLING": False,
            "M15_FRESH_LOCAL_LOW": True,
            "M15_FRESH_LOCAL_HIGH": True,
        }
        
        if rsi is None or len(rsi) < 2 or len(df) < settings.PULLBACK_LOOKBACK_BARS + 2:
            return features
            
        # RSI Slope
        features["M15_RSI_RISING"] = bool(rsi.iloc[-1] > rsi.iloc[-2])
        features["M15_RSI_FALLING"] = bool(rsi.iloc[-1] < rsi.iloc[-2])
        
        # Close comparison
        features["M15_CLOSE_RISING"] = bool(df["close"].iloc[-1] > df["close"].iloc[-2])
        features["M15_CLOSE_FALLING"] = bool(df["close"].iloc[-1] < df["close"].iloc[-2])
        
        # Fresh Local Low/High check
        lb = settings.PULLBACK_LOOKBACK_BARS
        current_low = df["low"].iloc[-1]
        current_high = df["high"].iloc[-1]
        
        # local window excludes the current bar
        local_lows = df["low"].iloc[-1 - lb : -1]
        local_highs = df["high"].iloc[-1 - lb : -1]
        
        features["M15_FRESH_LOCAL_LOW"] = bool(current_low < local_lows.min())
        features["M15_FRESH_LOCAL_HIGH"] = bool(current_high > local_highs.max())
        
        return features

    # ── Data Freshness ──────────────────────────────────────

    def _is_fresh(self, df: pd.DataFrame) -> bool:
        """Check if the latest bar is recent enough (not stale)."""
        try:
            latest_time = df["time"].iloc[-1]
            if isinstance(latest_time, pd.Timestamp):
                latest_time = latest_time.to_pydatetime()

            now = datetime.now(timezone.utc)
            age = now - latest_time.replace(tzinfo=timezone.utc)

            return age < timedelta(minutes=self.MAX_DATA_AGE_MINUTES * 4)
        except Exception:
            return False
