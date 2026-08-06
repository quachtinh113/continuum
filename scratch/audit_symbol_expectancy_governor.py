import sys
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

if not mt5.initialize():
    print("MT5 initialization failed.")
    sys.exit(1)

print("="*85)
print(f"WORLDQUANT DYNAMIC ASSET GOVERNOR - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("="*85)

# Fetch historical deals over last 30 days to evaluate symbol expectancy
start_time = datetime.now(timezone.utc) - timedelta(days=30)
history_deals = mt5.history_deals_get(start_time, datetime.now(timezone.utc) + timedelta(days=1))

EXPECTANCY_CUTOFF_USD = -0.10 # Suspend symbol if Net Expectancy < -$0.10 / trade after 30 deals
MIN_DEALS_THRESHOLD = 30      # Minimum deal sample size before suspending

if history_deals is not None and len(history_deals) > 0:
    df_deals = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    df_trades = df_deals[df_deals['entry'].isin([0, 1])].copy()
    df_trades['net_pnl'] = df_trades['profit'] + df_trades['commission'] + df_trades['swap']
    
    sym_summary = df_trades.groupby('symbol').agg(
        total_pnl=('net_pnl', 'sum'),
        deals_count=('ticket', 'count'),
        win_deals=('net_pnl', lambda x: (x > 0).sum())
    ).reset_index()
    
    sym_summary['win_rate_pct'] = (sym_summary['win_deals'] / sym_summary['deals_count']) * 100.0
    sym_summary['expectancy_per_deal'] = sym_summary['total_pnl'] / sym_summary['deals_count']
    
    suspended_symbols = []
    active_symbols = []
    
    for idx, r in sym_summary.iterrows():
        sym = r['symbol']
        n_deals = r['deals_count']
        exp_deal = r['expectancy_per_deal']
        
        is_suspended = (n_deals >= MIN_DEALS_THRESHOLD) and (exp_deal < EXPECTANCY_CUTOFF_USD)
        if is_suspended:
            suspended_symbols.append(sym)
            status_str = "SUSPENDED (BLACK-LISTED)"
        else:
            active_symbols.append(sym)
            status_str = "ACTIVE (QUALIFIED)"
            
        print(f"Symbol: [{sym:<10}] | Deals: {n_deals:3d} | Net PnL: ${r['total_pnl']:+8.2f} | Expectancy: ${exp_deal:+6.2f}/deal | Status: {status_str}")
        
    print("\n" + "="*85)
    print("ASSET GOVERNOR DECISION MATRIX")
    print("="*85)
    print(f"Active Symbols ({len(active_symbols)}):      {', '.join(active_symbols) if active_symbols else 'None'}")
    print(f"Suspended Symbols ({len(suspended_symbols)}): {', '.join(suspended_symbols) if suspended_symbols else 'None (All Symbols Qualified)'}")
else:
    print("No historical deals found.")

mt5.shutdown()
