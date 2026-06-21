import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta
import sys

def main():
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

    # History from 24 hours ago
    utc_now = datetime.now(timezone.utc)
    from_date = utc_now - timedelta(days=1)
    
    print(f"\nRetrieving trading history since {from_date.strftime('%Y-%m-%d %H:%M:%S')} UTC...")
    
    # Get history deals
    deals = mt5.history_deals_get(from_date, utc_now)
    if deals is None:
        print(f"Failed to get deals history: {mt5.last_error()}")
    elif len(deals) == 0:
        print("No trade deals found in history for the last 24 hours.")
    else:
        df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        df_deals['time'] = pd.to_datetime(df_deals['time'], unit='s')
        
        print(f"\nFound {len(deals)} deals in the last 24 hours:")
        cols = ['time', 'symbol', 'type', 'entry', 'volume', 'price', 'profit', 'comment']
        # Filter columns to only show existing ones
        existing_cols = [c for c in cols if c in df_deals.columns]
        
        # Map type to BUY/SELL
        # 0 = Buy, 1 = Sell
        df_deals['type'] = df_deals['type'].map({0: 'BUY', 1: 'SELL'}).fillna(df_deals['type'])
        df_deals['entry'] = df_deals['entry'].map({0: 'IN', 1: 'OUT', 2: 'INOUT'}).fillna(df_deals['entry'])
        
        print(df_deals[existing_cols].to_string(index=False))

    # Get active positions currently
    positions = mt5.positions_get()
    if positions is None:
        print(f"Failed to get active positions: {mt5.last_error()}")
    elif len(positions) == 0:
        print("\nNo active positions currently open.")
    else:
        df_pos = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
        df_pos['time'] = pd.to_datetime(df_pos['time'], unit='s')
        df_pos['type'] = df_pos['type'].map({0: 'BUY', 1: 'SELL'}).fillna(df_pos['type'])
        
        print(f"\nFound {len(positions)} active positions currently open:")
        cols = ['time', 'symbol', 'type', 'volume', 'price_open', 'price_current', 'profit', 'comment']
        existing_cols = [c for c in cols if c in df_pos.columns]
        print(df_pos[existing_cols].to_string(index=False))

    mt5.shutdown()

if __name__ == "__main__":
    main()
