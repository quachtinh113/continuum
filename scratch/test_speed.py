import time
import pandas as pd
import numpy as np

def find_swings_opt(df, swing_window=5):
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    
    sh_arr = np.full(n, np.nan)
    sl_arr = np.full(n, np.nan)
    
    w = swing_window
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

def detect_order_blocks_opt(df, swing_highs, swing_lows):
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
        
        if close_curr > sh_vals[i - 1] and close_prev < open_prev:
            obs.append({
                "type": "BULLISH",
                "top": max(open_prev, close_prev),
                "bottom": low_vals[i - 1],
                "ticket_index": df_index[i - 1]
            })
        elif close_curr < sl_vals[i - 1] and close_prev > open_prev:
            obs.append({
                "type": "BEARISH",
                "top": high_vals[i - 1],
                "bottom": min(open_prev, close_prev),
                "ticket_index": df_index[i - 1]
            })
    return obs

def main():
    df = pd.DataFrame({
        "high": np.random.randn(100) + 10.0,
        "low": np.random.randn(100) + 9.0,
        "open": np.random.randn(100) + 9.5,
        "close": np.random.randn(100) + 9.5
    })

    t0 = time.time()
    for _ in range(1000):
        sh, sl = find_swings_opt(df)
    print(f"1000 OPTIMIZED find_swings calls: {time.time() - t0:.6f}s")
    
    sh, sl = find_swings_opt(df)
    
    t0 = time.time()
    for _ in range(1000):
        obs = detect_order_blocks_opt(df, sh, sl)
    print(f"1000 OPTIMIZED detect_order_blocks calls: {time.time() - t0:.6f}s")

if __name__ == "__main__":
    main()
