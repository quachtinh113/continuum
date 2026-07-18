import MetaTrader5 as mt5
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import settings

def close_position(p):
    # Determine opposite order type
    opposite_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    # Get current price for closing
    tick = mt5.symbol_info_tick(p.symbol)
    if tick is None:
        print(f"Unable to get tick for {p.symbol}")
        return False
    price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": p.symbol,
        "volume": p.volume,
        "type": opposite_type,
        "position": p.ticket,
        "price": price,
        "deviation": 10,
        "magic": getattr(settings, "MAGIC_NUMBER", 202500),
        "comment": "Close GBPUSD end of week",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to close {p.ticket} {p.symbol}: retcode={result.retcode}")
        return False
    print(f"Closed {p.ticket} {p.symbol} profit={p.profit:.2f}")
    return True

def main():
    if not mt5.initialize():
        print('MT5 init failed')
        sys.exit(1)
    positions = mt5.positions_get()
    if not positions:
        print('No open positions')
        mt5.shutdown()
        return
    closed_any = False
    for p in positions:
        if p.symbol.upper().startswith('GBPUSD'):
            closed_any = close_position(p) or closed_any
    if not closed_any:
        print('No GBPUSD positions to close')
    mt5.shutdown()

if __name__ == '__main__':
    main()
