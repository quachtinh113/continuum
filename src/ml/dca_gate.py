"""DCA ML-gate feature builder (live side).

Reproduces `V9ContinuumBacktester.build_context_features` semantics from closed
M15 / H1 / H4 frames so the live gate feeds gatekeeper_v2 the same feature
distribution it was trained and validated on (reports/backtest_36m §10).

Parity notes vs backtest:
  * ATR        : H1 true-range rolling(14), raw price units (NOT normalised).
  * ADX        : H1 ADX (same helper as backtest).
  * er_ratio   : last 11 closed M15 closes.
  * atr_ratio  : mean TR of last 14 closed M15 bars / mean(high-low) of last 100.
  * rsi_m15_delta : RSI_M15[-1] - RSI_M15[-4] (exact match).
  * rsi_h1_delta  : RSI_H1[-1] - RSI_H1[-2] (backtest uses H1 RSI ffilled onto
                    M15 rows 3 bars back; one H1 step is the closest live proxy).
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import numpy as np
import pandas as pd

from v9_continuum.layers.regime import calculate_adx, calculate_rsi

SESSION_MAP = {"ASIA": 0, "EUROPE": 1, "US": 2, "OVERLAP_ASIA_EU": 3, "OVERLAP_EU_US": 4, "OFF": -1}
ASSET_CLASS = {"XAUUSD": 0, "BTCUSD": 1, "US30": 2, "US500": 2, "US100": 2}


def _true_range_atr(df: pd.DataFrame, period: int = 14) -> float:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    val = tr.rolling(period).mean().iloc[-1]
    return float(val) if pd.notna(val) else float((df["high"] - df["low"]).mean())


def build_gate_features(symbol: str, direction: str, m15: pd.DataFrame, h1: pd.DataFrame,
                        h4: Optional[pd.DataFrame], now: datetime, session) -> Dict[str, float]:
    """All inputs must be CLOSED-bar frames (forming bar already dropped)."""
    m15 = m15.tail(100)
    closes = m15["close"].values

    # ---- higher-timeframe context ----
    adx_series = calculate_adx(h1["high"], h1["low"], h1["close"])
    adx_val = float(adx_series.iloc[-1]) if len(adx_series) and pd.notna(adx_series.iloc[-1]) else 20.0
    atr_val = _true_range_atr(h1)

    rsi_m15_s = calculate_rsi(m15["close"], period=14)
    rsi_h1_s = calculate_rsi(h1["close"], period=14)
    rsi_m15 = float(rsi_m15_s.iloc[-1]) if pd.notna(rsi_m15_s.iloc[-1]) else 50.0
    rsi_h1 = float(rsi_h1_s.iloc[-1]) if pd.notna(rsi_h1_s.iloc[-1]) else 50.0
    if h4 is not None and not h4.empty:
        rsi_h4_s = calculate_rsi(h4["close"], period=14)
        rsi_h4 = float(rsi_h4_s.iloc[-1]) if pd.notna(rsi_h4_s.iloc[-1]) else 50.0
    else:
        rsi_h4 = 50.0

    # ---- M15 micro-structure (mirrors backtest history_records maths) ----
    if len(closes) >= 11:
        ch = closes[-11:]
        change = abs(ch[-1] - ch[0])
        vol = np.sum(np.abs(np.diff(ch)))
        er_ratio = float(change / vol) if vol > 0 else 0.5
    else:
        er_ratio = 0.5

    if len(m15) >= 14:
        prev_close = m15["close"].shift(1)
        tr = pd.concat([m15["high"] - m15["low"], (m15["high"] - prev_close).abs(),
                        (m15["low"] - prev_close).abs()], axis=1).max(axis=1)
        atr_fast = float(tr.iloc[-14:].mean())
        atr_slow = float((m15["high"] - m15["low"]).clip(lower=1e-5).mean())
        atr_ratio = float(atr_fast / atr_slow) if atr_slow > 0 else 1.0
    else:
        atr_ratio = 1.0

    rsi_m15_delta = float(rsi_m15_s.iloc[-1] - rsi_m15_s.iloc[-4]) if len(rsi_m15_s) >= 4 and pd.notna(rsi_m15_s.iloc[-4]) else 0.0
    rsi_h1_delta = float(rsi_h1_s.iloc[-1] - rsi_h1_s.iloc[-2]) if len(rsi_h1_s) >= 2 and pd.notna(rsi_h1_s.iloc[-2]) else 0.0

    price = float(closes[-1])
    sess_key = session.value if hasattr(session, "value") else str(session)
    is_buy = 1 if direction == "BUY" else 0

    feat = {
        "er_ratio": er_ratio,
        "atr_ratio": atr_ratio,
        "rsi_h1_delta": rsi_h1_delta,
        "rsi_m15_delta": rsi_m15_delta,
        "adx": adx_val,
        "rsi_m15": rsi_m15,
        "RSI_M15": rsi_m15,
        "RSI_H1": rsi_h1,
        "RSI_H4": rsi_h4,
        "ADX": adx_val,
        "ATR": atr_val,
        "RSI_Delta": rsi_h4 - rsi_m15,
        "Volatility_Index": atr_val / price if price else 0.0,
        "hour": now.hour,
        "Session_Code": SESSION_MAP.get(sess_key, -1),
        "RSI_H1_Div": abs(rsi_h1 - 50.0),
        "Trend_Vol_Ratio": adx_val * atr_val,
        # engineered (gatekeeper_v2)
        "is_buy": float(is_buy),
        "hour_sin": float(np.sin(2 * np.pi * now.hour / 24.0)),
        "hour_cos": float(np.cos(2 * np.pi * now.hour / 24.0)),
        "adx_x_atrratio": float(adx_val * atr_ratio),
        "rsi_align": float(np.sign(rsi_m15 - 50.0) * np.sign(rsi_h1 - 50.0)),
        "rsi_extreme": float(abs(rsi_m15 - 50.0)),
        "trendiness": float(er_ratio * adx_val),
        "h4_bias_agree": float(1 if ((rsi_h4 > 50.0) == bool(is_buy)) else 0),
        "asset_class": float(ASSET_CLASS.get(symbol, 3)),
    }
    return feat
