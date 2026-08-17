import pandas as pd
import numpy as np

def calculate_daily_volatility(close_prices: pd.Series, lookback: int = 14) -> pd.Series:
    """
    Calculates rolling daily volatility as standard deviation of log returns.
    """
    log_ret = np.log(close_prices / close_prices.shift(1))
    vol = log_ret.rolling(window=lookback).std()
    # Fill leading NaNs with small default volatility (e.g. 0.002)
    return vol.fillna(0.002)

def apply_triple_barrier_labels(
    df: pd.DataFrame,
    pt_mult: float = 1.5,
    sl_mult: float = 1.0,
    max_holding_bars: int = 24
) -> pd.DataFrame:
    """
    De Prado's Triple-Barrier Labeling Method.
    
    Barriers:
    1. Upper Barrier (Take Profit): Price * (1 + pt_mult * Volatility)
    2. Lower Barrier (Stop Loss): Price * (1 - sl_mult * Volatility)
    3. Vertical Barrier (Time Limit): Expiration after max_holding_bars.
    
    Returns df with added columns:
    - 'volatility': Rolling volatility
    - 'barrier_hit': 'TP', 'SL', or 'TIME'
    - 'label': 1 for Win (TP hit first or positive time-out), 0 for Loss
    - 'tb_return': Realized barrier return
    """
    df = df.copy()
    volatility = calculate_daily_volatility(df['close'])
    df['volatility'] = volatility
    
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    vol = volatility.values
    n = len(df)
    
    barrier_hits = []
    labels = []
    tb_returns = []
    
    for i in range(n):
        if i + max_holding_bars >= n or np.isnan(vol[i]) or vol[i] <= 0:
            barrier_hits.append('NONE')
            labels.append(0)
            tb_returns.append(0.0)
            continue
            
        p_entry = close[i]
        sigma = vol[i]
        
        tp_price = p_entry * (1.0 + pt_mult * sigma)
        sl_price = p_entry * (1.0 - sl_mult * sigma)
        
        hit = 'TIME'
        final_ret = (close[i + max_holding_bars] - p_entry) / p_entry
        label = 1 if final_ret > 0 else 0
        
        for step in range(1, max_holding_bars + 1):
            curr_idx = i + step
            curr_high = high[curr_idx]
            curr_low = low[curr_idx]
            
            if curr_high >= tp_price:
                hit = 'TP'
                final_ret = pt_mult * sigma
                label = 1
                break
            elif curr_low <= sl_price:
                hit = 'SL'
                final_ret = -sl_mult * sigma
                label = 0
                break
                
        barrier_hits.append(hit)
        labels.append(label)
        tb_returns.append(final_ret)
        
    df['barrier_hit'] = barrier_hits
    df['label'] = labels
    df['tb_return'] = tb_returns
    return df
