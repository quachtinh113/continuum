import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

try:
    import MetaTrader5 as mt5
    if mt5.initialize():
        acc = mt5.account_info()
        if acc:
            print(f"MT5 Account Info:")
            print(f"  Balance: ${acc.balance:.2f}")
            print(f"  Equity: ${acc.equity:.2f}")
            print(f"  Margin: ${acc.margin:.2f}")
            print(f"  Free Margin: ${acc.margin_free:.2f}")
            print(f"  Leverage: 1:{acc.leverage}")

        from datetime import datetime, timezone
        from_date = datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc)
        to_date = datetime(2026, 8, 10, 23, 59, 59, tzinfo=timezone.utc)
        
        deals = mt5.history_deals_get(from_date, to_date)
        if deals:
            print(f"\nMT5 History Deals for 2026-08-10 ({len(deals)} deals):")
            for d in deals:
                print(f"  Ticket: {d.ticket} | Order: {d.order} | Symbol: {d.symbol} | Type: {'BUY' if d.type==0 else 'SELL'} | Entry: {d.entry} | Vol: {d.volume} | Price: {d.price} | Profit: ${d.profit:.2f} | Swap: ${d.swap:.2f} | Comm: ${d.commission:.2f} | Time: {datetime.fromtimestamp(d.time, tz=timezone.utc)}")
        else:
            print("\nNo MT5 deals returned for 2026-08-10 or history unavailable.")
            
        mt5.shutdown()
    else:
        print("Failed to initialize MT5")
except Exception as e:
    print(f"Error accessing MT5: {e}")
