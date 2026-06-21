import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

mt5.initialize()

print(f"Local PC: {datetime.now()}")
print(f"UTC:      {datetime.now(timezone.utc)}")

rates = mt5.copy_rates_from_pos("EURUSDm", mt5.TIMEFRAME_H1, 0, 1)
if rates is not None and len(rates) > 0:
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    print("\nMT5 Candle Time (converted with unit='s'):")
    print(df[['time', 'open', 'close']].iloc[-1])
else:
    print("No rates found")

mt5.shutdown()
