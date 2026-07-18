import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
import sys

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

    # Monday July 6, 2026 00:00:00 UTC
    from_date = datetime(2026, 7, 6, 0, 0, 0, tzinfo=timezone.utc)
    utc_now = datetime.now(timezone.utc)
    
    print(f"\nRetrieving trading history from {from_date.strftime('%Y-%m-%d %H:%M:%S')} UTC to now...")
    
    # Get history deals
    deals = mt5.history_deals_get(from_date, utc_now)
    if deals is None:
        print(f"Failed to get deals history: {mt5.last_error()}")
    elif len(deals) == 0:
        print("No trade deals found in history since Monday.")
    else:
        df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        df_deals['time'] = pd.to_datetime(df_deals['time'], unit='s')
        
        print(f"\nFound {len(deals)} deals in history:")
        cols = ['time', 'symbol', 'type', 'entry', 'volume', 'price', 'profit', 'comment']
        # Filter columns to only show existing ones
        existing_cols = [c for c in cols if c in df_deals.columns]
        
        # Map type to BUY/SELL
        # 0 = Buy, 1 = Sell
        df_deals['type'] = df_deals['type'].map({0: 'BUY', 1: 'SELL'}).fillna(df_deals['type'])
        df_deals['entry'] = df_deals['entry'].map({0: 'IN', 1: 'OUT', 2: 'INOUT'}).fillna(df_deals['entry'])
        
        print(df_deals[existing_cols].to_string(index=False))

    mt5.shutdown()

if __name__ == "__main__":
    main()
