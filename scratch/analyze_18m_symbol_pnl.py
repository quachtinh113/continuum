import os
import sys
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from v9_continuum.backtest import V9ContinuumBacktester

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=========================================================================")
    print("     18-MONTH STANDALONE SYMBOL AUDIT (NO CROSS-SYMBOL GOVERNOR DRAG)")
    print("=========================================================================")
    
    symbols = ["XAUUSD", "US500", "US100", "USDCAD", "GBPUSD", "US30"]
    start_date = datetime(2025, 6, 2, tzinfo=timezone.utc)
    end_date = datetime(2026, 6, 18, tzinfo=timezone.utc)
    
    results = []
    
    for sym in symbols:
        print(f"\nProcessing {sym} standalone...")
        # 1. Standalone with ML veto disabled (threshold=1.0)
        tester_no_veto = V9ContinuumBacktester(ml_veto_threshold=1.0)
        port_no_veto, _ = tester_no_veto.run([sym], start_date, end_date, initial_balance=10000.0)
        trades_no_veto = port_no_veto.closed_cycles
        
        deals_nv = len(trades_no_veto)
        pnl_nv = sum(c['final_pnl'] for c in trades_no_veto)
        wins_nv = len([c for c in trades_no_veto if c['final_pnl'] > 0])
        wr_nv = (wins_nv / deals_nv * 100) if deals_nv > 0 else 0.0
        exp_nv = pnl_nv / deals_nv if deals_nv > 0 else 0.0
        
        # 2. Standalone with ML veto enabled (threshold=0.80)
        tester_veto = V9ContinuumBacktester(ml_veto_threshold=0.80)
        port_veto, _ = tester_veto.run([sym], start_date, end_date, initial_balance=10000.0)
        trades_veto = port_veto.closed_cycles
        
        deals_v = len(trades_veto)
        pnl_v = sum(c['final_pnl'] for c in trades_veto)
        wins_v = len([c for c in trades_veto if c['final_pnl'] > 0])
        wr_v = (wins_v / deals_v * 100) if deals_v > 0 else 0.0
        exp_v = pnl_v / deals_v if deals_v > 0 else 0.0
        
        results.append({
            'Symbol': sym,
            'NV_Deals': deals_nv,
            'NV_PnL ($)': round(pnl_nv, 2),
            'NV_WR (%)': round(wr_nv, 1),
            'NV_Exp ($)': round(exp_nv, 2),
            'V_Deals': deals_v,
            'V_PnL ($)': round(pnl_v, 2),
            'V_WR (%)': round(wr_v, 1),
            'V_Exp ($)': round(exp_v, 2)
        })
        
    df_res = pd.DataFrame(results)
    print("\n📊 STANDALONE SYMBOL COMPARISON MATRIX (VETO VS NO-VETO):")
    print(df_res.to_string(index=False))
    print("=========================================================================")

if __name__ == '__main__':
    main()
