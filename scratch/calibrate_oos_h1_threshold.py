import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xgboost import XGBClassifier

# Insert project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from v9_continuum.layers.position import PositionSizer
from config.symbols import get_symbol_spec

print("="*85)
print("THRESHOLD CALIBRATION & WALK-FORWARD OOS SANITY CHECK")
print("="*85)

SWAP_RATES_PER_LOT_DAY = {
    'XAUUSD': 3.50, 'EURUSD': 0.50, 'GBPUSD': 0.60, 'USDJPY': 0.55, 'US100': 1.20, 'US500': 1.10, 'BTCUSD': 2.50
}

def calculate_swap_cost(symbol: str, lot: float, entry_time: datetime, exit_time: datetime) -> float:
    base_sym = symbol.replace("m", "")
    rate_per_day = SWAP_RATES_PER_LOT_DAY.get(base_sym, 0.50)
    current = entry_time
    total_swap = 0.0
    while current < exit_time:
        if current.hour == 21:
            multiplier = 3.0 if current.weekday() == 2 else 1.0
            total_swap += rate_per_day * lot * multiplier
        current += timedelta(hours=1)
    return total_swap

df = pd.read_csv("logs/training_data.csv", on_bad_lines="skip")

df["RSI_M15"] = pd.to_numeric(df.get("RSI_M15"), errors="coerce").fillna(50.0)
df["RSI_H1"] = pd.to_numeric(df.get("RSI_H1"), errors="coerce").fillna(50.0)
df["RSI_H4"] = pd.to_numeric(df.get("RSI_H4"), errors="coerce").fillna(50.0)
df["ADX"] = pd.to_numeric(df.get("ADX"), errors="coerce").fillna(25.0)
df["ATR"] = pd.to_numeric(df.get("ATR"), errors="coerce").fillna(0.001)

df["rsi_h1_delta"] = (df["RSI_H1"] - df["RSI_M15"]) / 15.0
df["rsi_h4_delta"] = (df["RSI_H4"] - df["RSI_H1"]) / 15.0
raw_atr_ratio = df["ATR"] / df["ATR"].rolling(14, min_periods=1).mean()
df["atr_ratio"] = np.clip((raw_atr_ratio - 1.0) * 0.10, -0.3, 0.3)
df["er_ratio"] = (df["RSI_M15"] - 50.0).abs() / 15.0
df["adx_scaled"] = (df["ADX"] - 25.0) / 15.0
df["rsi_m15_scaled"] = (df["RSI_M15"] - 50.0) / 15.0

feature_cols = ["er_ratio", "atr_ratio", "rsi_h1_delta", "rsi_h4_delta", "adx_scaled", "rsi_m15_scaled"]

for col in feature_cols:
    df[f"{col}_lag1"] = df[col].shift(1)

df = df.dropna(subset=[f"{col}_lag1" for col in feature_cols]).reset_index(drop=True)
lagged_features = [f"{col}_lag1" for col in feature_cols]

df["target"] = (pd.to_numeric(df.get("profit_usd", df.get("is_win")), errors="coerce").fillna(0.0) > 0.0).astype(int)

# Split 70% IS / 30% OOS
split_idx = int(len(df) * 0.70)
df_is = df.iloc[:split_idx].copy().reset_index(drop=True)
df_oos = df.iloc[split_idx:].copy().reset_index(drop=True)

X_is = df_is[lagged_features]
y_is = df_is["target"]

model = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.04, random_state=42, eval_metric="logloss")
model.fit(X_is, y_is)

X_oos = df_oos[lagged_features]
probs_win_oos = model.predict_proba(X_oos)[:, 1]
probs_loss_oos = 1.0 - probs_win_oos

print(f"Sweep thresholds on OOS (Candidate count: {len(df_oos)})...")

for thresh in np.arange(0.70, 0.95, 0.02):
    approved_mask = probs_loss_oos < thresh
    df_sub = df_oos[approved_mask]
    n_app = len(df_sub)
    if n_app < 5:
        continue
    wins = df_sub[df_sub["target"] == 1]
    wr = len(wins) / n_app * 100.0
    print(f"Threshold: P(Loss) < {thresh:.2f} | Approved Trades: {n_app:3d} | Win Rate: {wr:.1f}%")

print("="*85)
