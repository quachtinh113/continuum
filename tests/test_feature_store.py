import pytest
import pandas as pd
import numpy as np
from v9_continuum.feature_store import V9FeatureStore

def test_feature_store_transform():
    # Construct mock raw data
    data = {
        'close': np.linspace(100.0, 110.0, 50),
        'ATR': np.linspace(1.5, 2.5, 50),
        'RSI': np.linspace(30.0, 70.0, 50),
        'RSI_M15': np.linspace(30.0, 70.0, 50),
        'ADX': np.linspace(20.0, 40.0, 50),
        'RSI_Delta': np.linspace(-2.0, 2.0, 50),
        'hour': np.arange(50) % 24
    }
    df = pd.DataFrame(data)
    
    fs = V9FeatureStore(rolling_window=10)
    transformed = fs.transform(df)
    
    # Assert output structure
    assert not transformed.empty
    assert len(transformed) == 41 # 50 - 9 (rolling window of 10 drops first 9 NaNs)
    
    expected_cols = [
        'feature_atr_zscore',
        'feature_rsi_centered',
        'feature_rsi_m15_centered',
        'feature_adx_norm',
        'feature_volatility_idx',
        'feature_rsi_delta',
        'feature_hour'
    ]
    for col in expected_cols:
        assert col in transformed.columns
        assert not transformed[col].isnull().any()
        
    # ADX norm should be between 0.0 and 1.0
    assert (transformed['feature_adx_norm'] >= 0.0).all()
    assert (transformed['feature_adx_norm'] <= 1.0).all()
