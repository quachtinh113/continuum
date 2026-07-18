import MetaTrader5 as mt5
import sys

def main():
    if not mt5.initialize():
        print('Failed to initialize MT5')
        sys.exit(1)
    positions = mt5.positions_get()
    if not positions:
        print('No open positions')
    else:
        for p in positions:
            typ = 'BUY' if p.type == mt5.ORDER_TYPE_BUY else 'SELL' if p.type == mt5.ORDER_TYPE_SELL else str(p.type)
            print(f"Ticket:{p.ticket} Symbol:{p.symbol} Type:{typ} Volume:{p.volume} Open:{p.price_open:.5f} Profit:{p.profit:.2f}")
    mt5.shutdown()

if __name__ == '__main__':
    main()
