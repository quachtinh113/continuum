import sys
import os
from datetime import datetime, timezone

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
    positions = mt5.positions_get()
    if positions is not None:
        print(f"Total open positions in MT5: {len(positions)}")
        for pos in positions:
            # open time
            t_open = datetime.fromtimestamp(pos.time, tz=timezone.utc)
            print(f"Ticket: {pos.ticket} | Symbol: {pos.symbol} | Type: {'BUY' if pos.type==0 else 'SELL'} | Vol: {pos.volume} | Open Price: {pos.price_open} | Profit: ${pos.profit:.2f} | Time: {t_open.strftime('%Y-%m-%d %H:%M:%S')} UTC | Comment: {pos.comment} | Magic: {pos.magic}")
    else:
        print("No open positions in MT5")
finally:
    connector.disconnect()
