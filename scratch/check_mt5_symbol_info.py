import sys
import MetaTrader5 as mt5

sys.stdout.reconfigure(encoding='utf-8')

if mt5.initialize():
    for sym in ["USTECm", "XAUUSDm"]:
        info = mt5.symbol_info(sym)
        if info:
            print(f"=== Symbol: {sym} ===")
            print(f"  Volume Min: {info.volume_min}")
            print(f"  Volume Max: {info.volume_max}")
            print(f"  Volume Step: {info.volume_step}")
            print(f"  Contract Size: {info.trade_contract_size}")
            print(f"  Point: {info.point}")
            print(f"  Digits: {info.digits}")
    mt5.shutdown()
else:
    print("Failed to initialize MT5")
