import sys
import os
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.mt5_connector import MT5Connector
import MetaTrader5 as mt5

if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')

connector = MT5Connector()
if not connector.connect():
    print("Failed to connect to MT5")
    sys.exit(1)

try:
    symbol = "USTECm"
    
    # Fetch M15 bars for USTECm starting from 2026-06-15 02:00 to 2026-06-15 20:00 UTC
    utc_from = datetime(2026, 6, 15, 2, 0, tzinfo=timezone.utc)
    utc_to = datetime(2026, 6, 15, 20, 0, tzinfo=timezone.utc)
    
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, utc_from, utc_to)
    if rates is None or len(rates) == 0:
        print(f"Failed to fetch rates for {symbol}")
    else:
        print(f"Fetched {len(rates)} bars for {symbol}:")
        print(f"{'Time (UTC)':<20} | {'Open':<10} | {'High':<10} | {'Low':<10} | {'Close':<10}")
        for r in rates:
            dt = datetime.fromtimestamp(r['time'], tz=timezone.utc)
            print(f"{dt.strftime('%Y-%m-%d %H:%M:%S')} | {r['open']:<10.2f} | {r['high']:<10.2f} | {r['low']:<10.2f} | {r['close']:<10.2f}")
finally:
    connector.disconnect()
