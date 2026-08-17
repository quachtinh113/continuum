import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

def get_daily_volatility(close_prices, lookback=14):
    """
    Computes daily volatility using ATR normalized by close price or log return std.
    """
    returns = np.log(close_prices / close_prices.shift(1))
    vol = returns.rolling(window=lookback).std()
    return vol

def apply_triple_barrier_labels(df, pt_mult=1.5, sl_mult=1.0, max_holding_bars=24):
    """
    Applies Marcos Lopez de Prado's Triple-Barrier Method.
    
    Barriers:
    1. Upper Barrier (Take Profit): Pt * (1 + pt_mult * vol)
    2. Lower Barrier (Stop Loss): Pt * (1 - sl_mult * vol)
    3. Vertical Barrier (Time Limit): max_holding_bars
    
    Returns DataFrame with columns:
    - 'barrier_hit': 'TP', 'SL', or 'TIME'
    - 'label': 1 for Win (TP hit first), 0 for Loss (SL or negative TIME hit)
    - 'ret': actual return achieved
    """
    df = df.copy()
    volatility = get_daily_volatility(df['close'])
    
    labels = []
    barrier_hits = []
    returns = []
    
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    vol = volatility.values
    n = len(df)
    
    for i in range(n):
        if i + max_holding_bars >= n or np.isnan(vol[i]) or vol[i] == 0:
            labels.append(np.nan)
            barrier_hits.append('NONE')
            returns.append(0.0)
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
            
            # Check Upper Barrier (TP)
            if curr_high >= tp_price:
                hit = 'TP'
                final_ret = pt_mult * sigma
                label = 1
                break
            # Check Lower Barrier (SL)
            elif curr_low <= sl_price:
                hit = 'SL'
                final_ret = -sl_mult * sigma
                label = 0
                break
                
        barrier_hits.append(hit)
        labels.append(label)
        returns.append(final_ret)
        
    df['barrier_hit'] = barrier_hits
    df['label'] = labels
    df['triple_barrier_ret'] = returns
    return df

class PurgedWalkForwardCV:
    """
    Purged Walk-Forward Cross Validation with Embargo.
    36-Month Period, 12M Train, 3M Test, 14-Day Embargo, Purging Overlaps.
    """
    def __init__(self, start_date, end_date, train_months=12, test_months=3, embargo_days=14):
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.train_months = train_months
        self.test_months = test_months
        self.embargo_days = embargo_days

    def split(self, df):
        """
        Yields (train_indices, test_indices) with purging and embargo applied.
        """
        df_time = pd.to_datetime(df['timestamp'])
        current_train_start = self.start_date

        while True:
            current_train_end = current_train_start + pd.DateOffset(months=self.train_months)
            current_test_start = current_train_end
            current_test_end = current_test_start + pd.DateOffset(months=self.test_months)

            if current_test_end > self.end_date:
                break

            # 1. Test Mask
            test_mask = (df_time >= current_test_start) & (df_time < current_test_end)
            test_indices = df.index[test_mask].tolist()

            if not test_indices:
                current_train_start = current_train_start + pd.DateOffset(months=self.test_months)
                continue

            # 2. Train Mask before test window
            train_mask = (df_time >= current_train_start) & (df_time < current_train_end)
            
            # 3. Purging & Embargo Application
            # Embargo: drop data within embargo_days AFTER test window for next train folds
            # Purge: drop data near boundary that overlaps with barrier events
            embargo_boundary = current_train_end - pd.Timedelta(days=self.embargo_days)
            purged_train_mask = train_mask & (df_time < embargo_boundary)

            train_indices = df.index[purged_train_mask].tolist()

            yield train_indices, test_indices, current_train_start, current_train_end, current_test_start, current_test_end

            # Advance sliding train window
            current_train_start = current_train_start + pd.DateOffset(months=self.test_months)

def main():
    print("==========================================================")
    print("  TESTING PURGED WALK-FORWARD & TRIPLE-BARRIER LOGIC")
    print("==========================================================")
    
    # Generate dummy M15 dataset over 36 months
    dates = pd.date_range(start="2023-08-01", end="2026-08-01", freq="15min")
    np.random.seed(42)
    price_path = 2000.0 + np.cumsum(np.random.randn(len(dates)) * 0.5)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': price_path,
        'high': price_path + abs(np.random.randn(len(dates))),
        'low': price_path - abs(np.random.randn(len(dates))),
        'close': price_path + np.random.randn(len(dates)) * 0.2
    })
    
    print(f"Generated synthetic M15 data: {len(df)} rows from {dates[0]} to {dates[-1]}")
    
    # Apply Triple-Barrier Labeling
    df_labeled = apply_triple_barrier_labels(df.iloc[:1000]) # test sample
    print("\nTriple-Barrier Labeling Sample:")
    print(df_labeled[['timestamp', 'close', 'barrier_hit', 'label', 'triple_barrier_ret']].head(10))
    
    # Test Purged Walk Forward CV splits
    pwf = PurgedWalkForwardCV(start_date="2023-08-01", end_date="2026-08-01", train_months=12, test_months=3, embargo_days=14)
    
    fold_count = 0
    print("\nWalk-Forward Splits Generated:")
    for tr_idx, te_idx, tr_s, tr_e, te_s, te_e in pwf.split(df):
        fold_count += 1
        print(f"  Fold {fold_count}: Train [{tr_s.strftime('%Y-%m-%d')} -> {tr_e.strftime('%Y-%m-%d')}] (Samples: {len(tr_idx)}) │ Test [{te_s.strftime('%Y-%m-%d')} -> {te_e.strftime('%Y-%m-%d')}] (Samples: {len(te_idx)})")

    print("==========================================================")

if __name__ == '__main__':
    main()
