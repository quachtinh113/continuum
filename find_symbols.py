"""Quick script to find available symbols on Exness MT5 server."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import MetaTrader5 as mt5
from config import settings

mt5.initialize()
mt5.login(login=settings.MT5_ACCOUNT, password=settings.MT5_PASSWORD, server=settings.MT5_SERVER)

# Get all symbols
symbols = mt5.symbols_get()
print(f"Total symbols on server: {len(symbols)}\n")

# Search for our target symbols
targets = ["EUR", "GBP", "USD", "JPY", "AUD", "CHF", "CAD", "NZD", "US30", "US100", "US500", "USTEC", "XAU", "BTC", "SP"]

print("="*80)
print(f"{'Symbol':<20} {'Path':<30} {'Visible':<8} {'Spread':<10}")
print("="*80)

for s in symbols:
    name = s.name.upper()
    if any(t in name for t in targets):
        tick = mt5.symbol_info_tick(s.name)
        spread = ""
        if tick and tick.ask > 0:
            spread = f"{tick.ask - tick.bid:.5f}"
        print(f"{s.name:<20} {s.path:<30} {'Yes' if s.visible else 'No':<8} {spread:<10}")

mt5.shutdown()
