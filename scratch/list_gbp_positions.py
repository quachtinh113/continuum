import MetaTrader5 as mt5
import datetime, sys

def main():
    if not mt5.initialize():
        print('Failed to initialize MT5')
        sys.exit(1)
    positions = mt5.positions_get()
    if not positions:
        print('No open positions')
        mt5.shutdown()
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    found = False
    for p in positions:
        if p.symbol.upper().startswith('GBPUSD'):
            found = True
            open_time = datetime.datetime.fromtimestamp(p.time, datetime.timezone.utc)
            duration = now - open_time
            typ = 'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL' if p.type == mt5.ORDER_TYPE_SELL else str(p.type)
            print(f"Ticket:{p.ticket} Symbol:{p.symbol} Type:{typ} Volume:{p.volume} Open:{p.price_open:.5f} Profit:{p.profit:.2f} Opened:{open_time.strftime('%Y-%m-%d %H:%M:%S UTC')} Duration:{duration}")
    if not found:
        print('No GBPUSD positions open')
    mt5.shutdown()

if __name__ == '__main__':
    main()
