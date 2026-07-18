import MetaTrader5 as mt5
import pandas as pd
import sys
from datetime import datetime, timezone

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("Connecting to MetaTrader 5...")
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        sys.exit(1)
        
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info.")
        mt5.shutdown()
        sys.exit(1)
        
    print(f"Connected to Account: {account_info.login}")
    print(f"Balance: ${account_info.balance:.2f} | Equity: ${account_info.equity:.2f}")

    # Monday July 13, 2026 00:00:00 UTC
    from_date = datetime(2026, 7, 13, 0, 0, 0, tzinfo=timezone.utc)
    utc_now = datetime.now(timezone.utc)
    
    print(f"\nRetrieving trading history from {from_date.strftime('%Y-%m-%d %H:%M:%S')} UTC to now...")
    
    # Get history deals
    deals = mt5.history_deals_get(from_date, utc_now)
    if deals is None or len(deals) == 0:
        print("No trade deals found in history since Monday July 13.")
        mt5.shutdown()
        sys.exit(0)
        
    df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df_deals['time'] = pd.to_datetime(df_deals['time'], unit='s')
    
    # Map entry to string
    df_deals['entry_str'] = df_deals['entry'].map({0: 'IN', 1: 'OUT', 2: 'INOUT'}).fillna(df_deals['entry'])
    df_deals['type_str'] = df_deals['type'].map({0: 'BUY', 1: 'SELL'}).fillna(df_deals['type'])
    
    # Out deals represent closures
    df_out = df_deals[df_deals['entry'] == 1].copy()
    
    total_deals = len(df_deals)
    total_in = len(df_deals[df_deals['entry'] == 0])
    total_out = len(df_out)
    
    # Sum up totals
    gross_profit = df_deals['profit'].sum()
    total_commission = df_deals['commission'].sum() if 'commission' in df_deals.columns else 0.0
    total_swap = df_deals['swap'].sum() if 'swap' in df_deals.columns else 0.0
    net_pnl = gross_profit + total_commission + total_swap
    
    print("\n==================================================================")
    print("📊 MT5 ACCOUNT PNL SUMMARY (July 13 - July 18, 2026)")
    print("==================================================================")
    print(f"Total Deals Analyzed      │ {total_deals}")
    print(f"Total Opened Positions (IN)│ {total_in}")
    print(f"Total Closed Positions (OUT)│ {total_out}")
    print(f"Gross Profit/Loss (Deals) │ ${gross_profit:+.2f}")
    print(f"Total Commissions         │ ${total_commission:+.2f}")
    print(f"Total Swap Fees           │ ${total_swap:+.2f}")
    print(f"Net Account PnL           │ ${net_pnl:+.2f}")
    
    if total_out > 0:
        wins = df_out[df_out['profit'] > 0]
        losses = df_out[df_out['profit'] <= 0]
        win_rate = len(wins) / total_out * 100
        
        print(f"Win Rate (Closed Trades)  │ {win_rate:.2f}% ({len(wins)} Wins / {len(losses)} Losses)")
        print(f"Gross Win Amount          │ ${wins['profit'].sum():+.2f}")
        print(f"Gross Loss Amount         │ ${losses['profit'].sum():+.2f}")
        
        loss_sum = losses['profit'].sum()
        if loss_sum != 0:
            print(f"Profit Factor             │ {abs(wins['profit'].sum() / loss_sum):.2f}")
        else:
            print("Profit Factor             │ N/A")
            
        print(f"Average Profit per Win    │ ${wins['profit'].mean():.2f}" if len(wins) > 0 else "N/A")
        print(f"Average Loss per Loss     │ ${losses['profit'].mean():.2f}" if len(losses) > 0 else "N/A")
        print(f"Max Win                   │ ${df_out['profit'].max():.2f}")
        print(f"Max Loss                  │ ${df_out['profit'].min():.2f}")
    print("==================================================================\n")
    
    if total_out > 0:
        # PnL by Symbol
        print("💱 PNL BY SYMBOL:")
        print("------------------------------------------------------------------")
        # For each symbol, sum profit, commission, swap
        symbol_groups = df_deals.groupby('symbol').agg(
            gross_pnl=('profit', 'sum'),
            commissions=('commission', 'sum'),
            swaps=('swap', 'sum'),
            trades_closed=('entry', lambda x: (x == 1).sum())
        )
        symbol_groups['net_pnl'] = symbol_groups['gross_pnl'] + symbol_groups['commissions'] + symbol_groups['swaps']
        print(symbol_groups.to_string())
        print("------------------------------------------------------------------\n")
        
        # PnL by Date (based on deal time)
        print("📈 PNL BY DATE (Closed Trades):")
        print("------------------------------------------------------------------")
        df_out['date'] = df_out['time'].dt.date
        date_groups = df_out.groupby('date').agg(
            gross_pnl=('profit', 'sum'),
            trades_closed=('entry', 'count')
        )
        print(date_groups.to_string())
        print("------------------------------------------------------------------\n")
        
        # Detailed Closed Deals List
        print("📝 DETAILED CLOSED DEALS (OUT):")
        print("------------------------------------------------------------------")
        df_out_print = df_out.rename(columns={'type_str': 'type'})
        cols_to_print = ['time', 'symbol', 'type', 'volume', 'price', 'profit', 'comment']
        print(df_out_print[cols_to_print].to_string(index=False))
        print("------------------------------------------------------------------\n")

    # Check for active positions
    positions = mt5.positions_get()
    if positions is not None and len(positions) > 0:
        df_pos = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
        df_pos['time'] = pd.to_datetime(df_pos['time'], unit='s')
        df_pos['type'] = df_pos['type'].map({0: 'BUY', 1: 'SELL'}).fillna(df_pos['type'])
        
        print("🔔 ACTIVE POSITIONS CURRENTLY OPEN:")
        print("------------------------------------------------------------------")
        cols = ['time', 'symbol', 'type', 'volume', 'price_open', 'price_current', 'profit', 'comment']
        existing_cols = [c for c in cols if c in df_pos.columns]
        print(df_pos[existing_cols].to_string(index=False))
        print("------------------------------------------------------------------\n")
    else:
        print("No active positions currently open.")

    mt5.shutdown()

if __name__ == "__main__":
    main()
