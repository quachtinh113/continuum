import MetaTrader5 as mt5
from datetime import datetime, timezone

mt5.initialize()
tick = mt5.symbol_info_tick('XAUUSDm')

print(f"Local PC: {datetime.now()}")
print(f"UTC:      {datetime.now(timezone.utc)}")

if tick:
    # MT5 times are in seconds
    mt5_time = datetime.fromtimestamp(tick.time)
    print(f"MT5 Tick: {mt5_time} (this is local timezone representation of MT5 timestamp)")
    print(f"MT5 Tick raw time (unix): {tick.time}")
    
    # Let's get MT5 terminal info for time
    term = mt5.terminal_info()
    # There's no direct "server time" field in terminal_info in python, but tick.time is the server timestamp
else:
    print("No tick data")

mt5.shutdown()
