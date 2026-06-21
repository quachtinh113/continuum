import pandas as pd
import numpy as np
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple

try:
    import xgboost as xgb
except ImportError:
    xgb = None


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# ── SMC (Smart Money Concepts) Engine ─────────────────────────────

class SMCEngine:
    """
    Identifies institutional order flow dynamics:
    - Swing Highs / Lows (Market Structure)
    - Break of Structure (BOS) & Market Structure Shift (MSS)
    - Order Blocks (OB)
    - Fair Value Gaps (FVG)
    """
    def __init__(self, swing_window: int = 5):
        self.swing_window = swing_window

    def find_swings(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Locates local swing highs and swing lows.
        A swing high is higher than `swing_window` neighbors on both sides.
        """
        highs = df["high"].values
        lows = df["low"].values
        n = len(df)
        
        sh_arr = np.full(n, np.nan)
        sl_arr = np.full(n, np.nan)
        
        w = self.swing_window
        for i in range(w, n - w):
            val_h = highs[i]
            val_l = lows[i]
            
            win_h = highs[i - w : i + w + 1]
            win_l = lows[i - w : i + w + 1]
            
            if val_h == np.max(win_h):
                sh_arr[i] = val_h
            if val_l == np.min(win_l):
                sl_arr[i] = val_l
                
        swing_highs = pd.Series(sh_arr, index=df.index).ffill()
        swing_lows = pd.Series(sl_arr, index=df.index).ffill()
        return swing_highs, swing_lows

    def detect_fvgs(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Finds Fair Value Gaps (FVGs) in the last 20 candles.
        - Bullish FVG: Low(i) > High(i-2)
        - Bearish FVG: High(i) < Low(i-2)
        """
        fvgs = []
        n = len(df)
        if n < 3:
            return fvgs

        low_vals = df["low"].values
        high_vals = df["high"].values
        df_index = df.index

        start_idx = max(2, n - 20)
        for i in range(start_idx, n):
            low_0 = low_vals[i]
            high_0 = high_vals[i]
            
            low_2 = low_vals[i - 2]
            high_2 = high_vals[i - 2]
            
            # Bullish FVG
            if low_0 > high_2:
                fvgs.append({
                    "type": "BULLISH",
                    "top": low_0,
                    "bottom": high_2,
                    "index": df_index[i - 1],
                    "mitigated": False
                })
            # Bearish FVG
            elif high_0 < low_2:
                fvgs.append({
                    "type": "BEARISH",
                    "top": low_2,
                    "bottom": high_0,
                    "index": df_index[i - 1],
                    "mitigated": False
                })
        return fvgs

    def detect_order_blocks(self, df: pd.DataFrame, swing_highs: pd.Series, swing_lows: pd.Series) -> List[Dict[str, Any]]:
        """
        Finds active Order Blocks (OB).
        - Bullish OB: The last bearish candle before a strong upmove that breaks a swing high.
        - Bearish OB: The last bullish candle before a strong downmove that breaks a swing low.
        """
        obs = []
        n = len(df)
        if n < 5:
            return obs

        close_vals = df["close"].values
        open_vals = df["open"].values
        high_vals = df["high"].values
        low_vals = df["low"].values
        sh_vals = swing_highs.values
        sl_vals = swing_lows.values
        df_index = df.index

        for i in range(2, n - 1):
            close_prev = close_vals[i - 1]
            open_prev = open_vals[i - 1]
            close_curr = close_vals[i]
            
            # Bullish Breakout
            if close_curr > sh_vals[i - 1] and close_prev < open_prev:
                obs.append({
                    "type": "BULLISH",
                    "top": max(open_prev, close_prev),
                    "bottom": low_vals[i - 1],
                    "ticket_index": df_index[i - 1]
                })
            # Bearish Breakout
            elif close_curr < sl_vals[i - 1] and close_prev > open_prev:
                obs.append({
                    "type": "BEARISH",
                    "top": high_vals[i - 1],
                    "bottom": min(open_prev, close_prev),
                    "ticket_index": df_index[i - 1]
                })
        return obs

    def evaluate_smc_signal(self, df: pd.DataFrame) -> Tuple[Signal, str]:
        """
        Combines BOS, MSS, Order Blocks, and FVGs to yield a trading direction.
        """
        if len(df) < 20:
            return Signal.HOLD, "Insufficient history for SMC"
            
        swing_highs, swing_lows = self.find_swings(df)
        fvgs = self.detect_fvgs(df)
        obs = self.detect_order_blocks(df, swing_highs, swing_lows)
        
        current_price = df["close"].iloc[-1]
        
        # Test for Bullish Mitigations / Order Blocks
        bullish_ob_active = any(ob["type"] == "BULLISH" and ob["bottom"] <= current_price <= ob["top"] for ob in obs)
        bullish_fvg_active = any(fvg["type"] == "BULLISH" and fvg["bottom"] <= current_price <= fvg["top"] for fvg in fvgs)
        
        # Test for Bearish Mitigations / Order Blocks
        bearish_ob_active = any(ob["type"] == "BEARISH" and ob["bottom"] <= current_price <= ob["top"] for ob in obs)
        bearish_fvg_active = any(fvg["type"] == "BEARISH" and fvg["bottom"] <= current_price <= fvg["top"] for fvg in fvgs)
        
        # Check current trend via swing highs/lows
        is_uptrend = swing_highs.iloc[-1] > swing_highs.shift(10).iloc[-1] if len(swing_highs) > 10 else True
        
        if (bullish_ob_active or bullish_fvg_active) and is_uptrend:
            return Signal.BUY, "Bullish SMC zone detected (OB/FVG) in uptrend"
        elif (bearish_ob_active or bearish_fvg_active) and not is_uptrend:
            return Signal.SELL, "Bearish SMC zone detected (OB/FVG) in downtrend"
            
        return Signal.HOLD, "No active SMC zones intersected"


# ── ML Signal Confirmations ───────────────────────────────────────

import os

class MLSignalEngine:
    """
    Evaluates risk and enhances SMC signals using ML models.
    """
    def __init__(self, model_path: str = "src/ml/gatekeeper_v1.model"):
        self.model_path = model_path
        self.model = None
        self.is_ready = False
        self.last_mtime = 0.0
        self._load_model()

    def _load_model(self):
        if xgb is not None:
            try:
                self.model = xgb.Booster()
                self.model.load_model(self.model_path)
                self.is_ready = True
                if os.path.exists(self.model_path):
                    self.last_mtime = os.path.getmtime(self.model_path)
            except Exception:
                self.is_ready = False

    def reload_if_modified(self):
        """Checks if the model file has been updated and hot-reloads it."""
        if not os.path.exists(self.model_path):
            return
        try:
            mtime = os.path.getmtime(self.model_path)
            if mtime > self.last_mtime:
                from src.audit_logger import log_info
                log_info(f"🔄 Detecting updated ML model file on disk. Hot-reloading model...")
                self._load_model()
        except Exception:
            pass

    def predict_loss_probability(self, features: Dict[str, float]) -> float:
        """
        Predicts loss threat score.
        Falls back to an academic risk metric (incorporating trend volatility ratio, 
        H1 RSI divergence, and session effects) if XGBoost booster is unavailable.
        """
        if self.is_ready and self.model is not None and xgb is not None:
            try:
                cols = ['RSI_Delta', 'Volatility_Index', 'Session_Code', 'RSI_H1_Div', 'Trend_Vol_Ratio', 'RSI_M15', 'RSI_H1', 'RSI_H4', 'ADX', 'ATR', 'hour']
                row = [features.get(col, 0.0) for col in cols]
                dtest = xgb.DMatrix([row], feature_names=cols)
                prob = self.model.predict(dtest)[0]
                return float(prob)
            except Exception:
                pass
        
        # Volatility & Trend Divergence Fallback
        vol_idx = features.get("Volatility_Index", 0.0)
        rsi_delta = abs(features.get("RSI_Delta", 0.0))
        rsi_h1_div = abs(features.get("RSI_H1_Div", features.get("RSI_H1", 50.0) - 50.0))
        trend_vol = features.get("Trend_Vol_Ratio", features.get("ADX", 25.0) * features.get("ATR", 0.001))
        
        # Enhanced quant risk proxy
        base_threat = (vol_idx * 80.0) + (rsi_delta / 120.0) + (rsi_h1_div / 60.0) + (trend_vol * 1.5)
        prob = 1.0 / (1.0 + np.exp(-(-2.0 + 2.5 * base_threat)))
        return float(np.clip(prob, 0.0, 1.0))
