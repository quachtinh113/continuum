import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("==========================================================")
    print("      WORLDQUANT WEEKLY PERFORMANCE AUDIT - MT5 LIVE")
    print("==========================================================")
    
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        sys.exit(1)
        
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info.")
        mt5.shutdown()
        sys.exit(1)
        
    print(f"Account: {account_info.login} ({account_info.name})")
    print(f"Broker:  {account_info.company} | Server: {account_info.server}")
    print(f"Balance: ${account_info.balance:.2f} | Equity: ${account_info.equity:.2f}")
    
    # Range of this week: Monday Aug 3, 2026 to Sunday Aug 9, 2026
    start_date = datetime(2026, 8, 3, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2026, 8, 9, 23, 59, 59, tzinfo=timezone.utc)
    
    print(f"\nScanning deals from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
    
    deals = mt5.history_deals_get(start_date, end_date)
    if deals is None:
        print(f"Failed to retrieve deals: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)
        
    if len(deals) == 0:
        print("No trades found in the history for this week.")
        mt5.shutdown()
        sys.exit(0)
        
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    # Ensure timezone info is preserved or processed
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    
    # Filter deals with profit != 0 or entry type OUT (close of cycle)
    # Entry types: 0 = IN, 1 = OUT, 2 = INOUT
    # We want to measure closed trade deals. MT5 records commissions and swaps on deals.
    trade_deals = df[(df['entry'] == 1) | (df['profit'] != 0.0)]
    
    total_profit = df['profit'].sum()
    total_commission = df['commission'].sum()
    total_swap = df['swap'].sum()
    net_pnl = total_profit + total_commission + total_swap
    
    print(f"\nOVERALL PERFORMANCE SUMMARY:")
    print(f"  Gross Profit/Loss  │ ${total_profit:+.2f} USD")
    print(f"  Total Commissions  │ ${total_commission:+.2f} USD")
    print(f"  Total Swaps        │ ${total_swap:+.2f} USD")
    print(f"  Net PnL            │ ${net_pnl:+.2f} USD")
    
    # Calculate cycle statistics
    closed_deals = df[df['entry'] == 1] # OUT deals represent trade exits
    total_closed = len(closed_deals)
    winning_deals = closed_deals[closed_deals['profit'] > 0]
    losing_deals = closed_deals[closed_deals['profit'] <= 0]
    
    win_rate = (len(winning_deals) / total_closed * 100) if total_closed > 0 else 0.0
    
    gross_gain = winning_deals['profit'].sum()
    gross_loss = abs(losing_deals['profit'].sum())
    profit_factor = (gross_gain / gross_loss) if gross_loss > 0 else gross_gain
    
    print(f"  Closed Cycles      │ {total_closed}")
    print(f"  Win Rate           │ {win_rate:.1f}% ({len(winning_deals)} Wins / {len(losing_deals)} Losses)")
    print(f"  Profit Factor      │ {profit_factor:.2f}")
    
    # Symbol breakdown
    print("\n📊 ASSET CLASS / SYMBOL BREAKDOWN:")
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
            'Gross Profit': round(s_profit, 2),
            'Commission': round(s_comm, 2),
            'Swap': round(s_swap, 2),
            'Net PnL ($)': round(s_net, 2),
            'Win Rate (%)': round(s_wr, 1)
        })
        
    df_sym = pd.DataFrame(sym_summary)
    print(df_sym.to_string(index=False))
    
    # Active Positions
    positions = mt5.positions_get()
    print("\n👁️ CURRENT OPEN POSITIONS:")
    if not positions:
        print("  No open positions.")
    else:
        for p in positions:
            typ = 'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL'
            print(f"  Ticket: {p.ticket:<9} │ Symbol: {p.symbol:<8} │ Type: {typ} │ Volume: {p.volume:.2f} │ Open Px: {p.price_open:.5f} │ Profit: ${p.profit:+.2f} USD")
            
    mt5.shutdown()
    print("==========================================================")

if __name__ == '__main__':
    main()
