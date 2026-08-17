import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import datetime
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return

    account_info = mt5.account_info()
    now = datetime.datetime.now()
    start_of_week = now - datetime.timedelta(days=now.weekday(), hours=now.hour, minutes=now.minute, seconds=now.second)
    deals = mt5.history_deals_get(start_of_week, now + datetime.timedelta(days=1))
    
    if deals:
        df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        close_deals = df[df['entry'].isin([1, 2, 3])].copy()
        close_deals['net_pnl'] = close_deals['profit'] + close_deals['swap'] + close_deals['commission']
        close_deals['time_dt'] = pd.to_datetime(close_deals['time'], unit='s')
        
        print("\n--- CHI TIẾT CÁC LỆNH ĐÃ ĐÓNG TRONG TUẦN NÀY ---")
        for _, r in close_deals.iterrows():
            dir_str = "BUY" if r['type'] == 0 else "SELL"
            print(f"  • [{r['time_dt'].strftime('%Y-%m-%d %H:%M:%S')}] {r['symbol']:<8} | {dir_str:<4} {r['volume']:.2f} lot | Px: {r['price']:<10} | Net PnL: ${r['net_pnl']:+7.2f} | Comment: {r['comment']}")

    mt5.shutdown()

if __name__ == "__main__":
    main()
