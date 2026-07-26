import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

class InstitutionalFeatureEngine:
    """
    Contextual Feature Engineering for V9 Continuum MLOps Pipeline.
    Calculates Kaufman Efficiency Ratio (ER), ATR Expansion Ratio, and Momentum Deltas.
    """
    @staticmethod
    def build_institutional_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Builds contextual features for XGBoost Gatekeeper training and prediction.
        """
        data = df.copy()

        # 1. Kaufman Efficiency Ratio (ER)
        if 'close' in data.columns:
            change = (data['close'] - data['close'].shift(10)).abs()
            volatility = data['close'].diff().abs().rolling(10).sum()
            data['er_ratio'] = np.where(volatility != 0, change / volatility, 0.0)
        else:
            # Fallback if close price series is not rolling (e.g., in tabular trade log)
            data['er_ratio'] = data.get('er_ratio', 0.5)

        # 2. Volatility Ratio (ATR Expansion)
        if all(col in data.columns for col in ['high', 'low', 'close']):
            tr = np.maximum(
                data['high'] - data['low'],
                np.maximum(
                    (data['high'] - data['close'].shift(1)).abs(),
                    (data['low'] - data['close'].shift(1)).abs()
                )
            )
            atr_fast = tr.rolling(14).mean()
            atr_slow = atr_fast.rolling(100).mean()
            data['atr_ratio'] = np.where(atr_slow != 0, atr_fast / atr_slow, 1.0)
        elif 'ATR' in data.columns:
            # Fallback using available ATR column
            atr_fast = data['ATR']
            atr_slow = atr_fast.rolling(50, min_periods=1).mean()
            data['atr_ratio'] = np.where(atr_slow != 0, atr_fast / atr_slow, 1.0)
        else:
            data['atr_ratio'] = data.get('atr_ratio', 1.0)

        # 3. RSI Momentum Deltas
        if 'rsi_h1' in data.columns:
            data['rsi_h1_delta'] = data['rsi_h1'] - data['rsi_h1'].shift(3)
        elif 'RSI_H1' in data.columns:
            data['rsi_h1_delta'] = data['RSI_H1'] - data['RSI_H1'].shift(3)
        else:
            data['rsi_h1_delta'] = 0.0

        if 'rsi_m15' in data.columns:
            data['rsi_m15_delta'] = data['rsi_m15'] - data['rsi_m15'].shift(3)
        elif 'RSI_M15' in data.columns:
            data['rsi_m15_delta'] = data['RSI_M15'] - data['RSI_M15'].shift(3)
        else:
            data['rsi_m15_delta'] = 0.0

        # Fill ADX and RSI defaults if available with column aliases
        if 'ADX' in data.columns and 'adx' not in data.columns:
            data['adx'] = data['ADX']
        if 'RSI_M15' in data.columns and 'rsi_m15' not in data.columns:
            data['rsi_m15'] = data['RSI_M15']

        # Ensure target_is_loss exists if profit_usd / is_win is present
        if 'target_is_loss' not in data.columns:
            if 'profit_usd' in data.columns:
                data['target_is_loss'] = (data['profit_usd'] <= 0).astype(int)
            elif 'is_win' in data.columns:
                data['target_is_loss'] = (data['is_win'] == 0).astype(int)

        return data.fillna(0.0)

def build_institutional_features(df: pd.DataFrame) -> pd.DataFrame:
    """Wrapper function matching user requirement specification."""
    return InstitutionalFeatureEngine.build_institutional_features(df)
