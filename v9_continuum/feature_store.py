import pandas as pd
import numpy as np

class V9FeatureStore:
    """
    Stationary Feature Store for V9 Continuum.
    Converts raw, non-stationary indicators into bounded, normalized values.
    """
    def __init__(self, rolling_window: int = 20):
        self.window = rolling_window

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        fts = pd.DataFrame(index=df.index)
        
        # 1. ATR Volatility Z-score
        if 'ATR' in df.columns:
            mean_atr = df['ATR'].rolling(window=self.window).mean()
            std_atr = df['ATR'].rolling(window=self.window).std().replace(0, 1e-6)
            fts['feature_atr_zscore'] = (df['ATR'] - mean_atr) / std_atr
            
        # 2. Centered RSI
        for rsi_col in ['RSI', 'RSI_M15', 'RSI_H1', 'RSI_H4']:
            if rsi_col in df.columns:
                fts[f'feature_{rsi_col.lower()}_centered'] = df[rsi_col] - 50.0
                
        # 3. Normalized ADX
        if 'ADX' in df.columns:
            fts['feature_adx_norm'] = df['ADX'] / 100.0

        # 4. Volatility Index
        if 'ATR' in df.columns and 'close' in df.columns:
            fts['feature_volatility_idx'] = df['ATR'] / df['close']
            
        # 5. RSI Delta
        if 'RSI_Delta' in df.columns:
            fts['feature_rsi_delta'] = df['RSI_Delta']
            
        # 6. Session Code & Hour (already stationary/discrete)
        if 'hour' in df.columns:
            fts['feature_hour'] = df['hour']

        fts.dropna(inplace=True)
        return fts
