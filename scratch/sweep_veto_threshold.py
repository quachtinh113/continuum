import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.backtest import V9ContinuumBacktester

def test_threshold(veto_thresh):
    tester = V9ContinuumBacktester(ml_veto_threshold=veto_thresh)
    symbols = ["XAUUSD", "US100"]
    start_date = datetime(2025, 6, 2, tzinfo=timezone.utc)
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)
    
    portfolio, _ = tester.run(symbols, start_date, end_date, initial_balance=10000.0)
    trades = portfolio.closed_cycles
    
    if not trades:
        return 0, 0.0, 0, 0.0, 0.0
        
    df = pd.DataFrame([{
        'exit_time': c['exit_time'],
        'profit': c['final_pnl']
    } for c in trades])
    
    df['close_time'] = pd.to_datetime(df['exit_time'])
    df = df.sort_values('close_time')
    df['week'] = df['close_time'].dt.to_period('W-SUN')
    
    weekly_summary = []
    for week, group in df.groupby('week'):
        weekly_summary.append(group['profit'].sum())
        
    if not weekly_summary:
        return 0, 0.0, 0, 0.0, 0.0
        
    pnl_series = np.array(weekly_summary)
    total_net = pnl_series.sum()
    avg_weekly = pnl_series.mean()
    losing_weeks = (pnl_series < 0).sum()
    winning_weeks = (pnl_series > 0).sum()
    total_weeks = len(pnl_series)
    loss_rate = losing_weeks / total_weeks * 100 if total_weeks > 0 else 0.0
    
    # Max consecutive losing weeks
    is_loss = pd.Series((pnl_series < 0).astype(int))
    consec_losses = is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumsum()
    max_consec = consec_losses.max() if len(consec_losses) > 0 else 0
    
    return total_weeks, total_net, losing_weeks, loss_rate, avg_weekly, max_consec

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=========================================================================")
    print("     THRESHOLD SWEEP FOR OPTIMIZED PORTFOLIO (XAUUSD + US100)")
    print("=========================================================================")
    
    thresholds = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.0]
    results = []
    for th in thresholds:
        print(f"Testing threshold: {th}...")
        w, net, lw, lr, avg, consec = test_threshold(th)
        results.append({
            'Threshold': th,
            'Weeks': w,
            'Total PnL ($)': round(net, 2),
            'Losing Weeks': lw,
            'Loss Rate (%)': round(lr, 1),
            'Avg Weekly PnL ($)': round(avg, 2),
            'Max Consec Loss Weeks': consec
        })
        
    res_df = pd.DataFrame(results)
    print("\n📊 SWEEP RESULT MATRIX:")
    print(res_df.to_string(index=False))
    print("=========================================================================")

if __name__ == '__main__':
    main()
