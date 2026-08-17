import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==========================================================")
    print("      POST-CALIBRATION PERFORMANCE AUDIT (AUG 6 - AUG 9)")
    print("==========================================================")
    
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        sys.exit(1)
        
    # Start: Aug 6, 2026 10:13 UTC (Calibration completion time)
    start_date = datetime(2026, 8, 6, 10, 13, 0, tzinfo=timezone.utc)
    end_date = datetime(2026, 8, 9, 23, 59, 59, tzinfo=timezone.utc)
    
    print(f"Retrieving trading history post-calibration from {start_date.strftime('%Y-%m-%d %H:%M:%S')} UTC...")
    
    deals = mt5.history_deals_get(start_date, end_date)
    if deals is None:
        print(f"Failed to retrieve deals: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)
        
    if len(deals) == 0:
        print("No trades found in the history post-calibration.")
        mt5.shutdown()
        sys.exit(0)
        
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    
    total_profit = df['profit'].sum()
    total_commission = df['commission'].sum()
    total_swap = df['swap'].sum()
    net_pnl = total_profit + total_commission + total_swap
    
    closed_deals = df[df['entry'] == 1]
    total_closed = len(closed_deals)
    winning_deals = closed_deals[closed_deals['profit'] > 0]
    losing_deals = closed_deals[closed_deals['profit'] <= 0]
    win_rate = (len(winning_deals) / total_closed * 100) if total_closed > 0 else 0.0
    
    print(f"\nPOST-CALIBRATION STATISTICS:")
    print(f"  Net PnL            │ ${net_pnl:+.2f} USD (Profit: ${total_profit:+.2f}, Comm: ${total_commission:.2f}, Swap: ${total_swap:.2f})")
    print(f"  Closed Cycles      │ {total_closed}")
    print(f"  Win Rate           │ {win_rate:.1f}% ({len(winning_deals)} Wins / {len(losing_deals)} Losses)")
    
    print("\n📊 SYMBOL BREAKDOWN POST-CALIBRATION:")
    sym_summary = []
    for sym, group in df.groupby('symbol'):
        s_profit = group['profit'].sum()
        s_comm = group['commission'].sum()
        s_swap = group['swap'].sum()
        s_net = s_profit + s_comm + s_swap
        
        s_closed = group[group['entry'] == 1]
        s_deals = len(s_closed)
        s_wins = len(s_closed[s_closed['profit'] > 0])
        s_wr = (s_wins / s_deals * 100) if s_deals > 0 else 0.0
        
        sym_summary.append({
            'Symbol': sym,
            'Deals': s_deals,
            'Net PnL ($)': round(s_net, 2),
            'Win Rate (%)': round(s_wr, 1)
        })
        
    df_sym = pd.DataFrame(sym_summary)
    print(df_sym.to_string(index=False))
    
    print("\n🔍 LIST OF INDIVIDUAL DEALS POST-CALIBRATION:")
    cols = ['time', 'symbol', 'type', 'entry', 'volume', 'price', 'profit', 'comment']
    df['type'] = df['type'].map({0: 'BUY', 1: 'SELL'}).fillna(df['type'])
    df['entry'] = df['entry'].map({0: 'IN', 1: 'OUT', 2: 'INOUT'}).fillna(df['entry'])
    print(df[cols].to_string(index=False))
    
    mt5.shutdown()
    print("==========================================================")

if __name__ == '__main__':
    main()
