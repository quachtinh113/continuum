import json

# Verify calculations for closed cycles this week:
trades = [
    {"symbol": "XAUUSD", "dir": "SELL", "open": 4345.793, "close": 4339.425, "lot": 0.02, "reason": "TRAILING_BE_EXIT", "pnl": (4345.793 - 4339.425)*0.02*100},
    {"symbol": "US100",  "dir": "SELL", "open": 29731.07, "close": 29737.56, "lot": 0.02, "reason": "SOFT_ML_SL",       "pnl": (29731.07 - 29737.56)*0.02*10},
    {"symbol": "US100",  "dir": "SELL", "open": 29737.56, "close": 29773.06, "lot": 0.02, "reason": "SOFT_ML_SL",       "pnl": (29737.56 - 29773.06)*0.02*10},
]

print("Weekly Profit Verification:")
tot = 0
for t in trades:
    print(f"[{t['symbol']}] {t['dir']} Open: {t['open']} -> Close: {t['close']} | Lot: {t['lot']} | PnL: ${t['pnl']:+.2f} ({t['reason']})")
    tot += t["pnl"]

print(f"\nTOTAL PnL (Closed trades 10/08 - 16/08): ${tot:+.2f} USD")
