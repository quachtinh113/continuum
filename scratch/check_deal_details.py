import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        sys.exit(1)
        
    ticket = 4485409205
    # Look back 1 week
    from_date = datetime.now(timezone.utc) - timedelta(days=7)
    to_date = datetime.now(timezone.utc)
    
    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None:
        print(f"Failed to get deals: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)
        
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    
    # Filter for position ticket or deal ticket matching the ticket of our interest
    pos_deals = df[df['position_id'] == ticket]
    print(f"Deals for position ID {ticket}:")
    print(pos_deals[['time', 'symbol', 'type', 'entry', 'volume', 'price', 'profit', 'comment']].to_string(index=False))
    
    mt5.shutdown()

if __name__ == '__main__':
    main()
