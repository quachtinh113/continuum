import MetaTrader5 as mt5
import sys

def main():
    if not mt5.initialize():
        print("Failed to initialize MT5")
        sys.exit(1)
        
    positions = mt5.positions_get(symbol="US500m")
    if not positions:
        print("No open positions for US500m")
        mt5.shutdown()
        sys.exit(0)
        
    for p in positions:
        print(f"Closing position: {p.ticket} Volume: {p.volume}")
        tick = mt5.symbol_info_tick("US500m")
        action_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if action_type == mt5.ORDER_TYPE_SELL else tick.ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": "US500m",
            "volume": p.volume,
            "type": action_type,
            "position": p.ticket,
            "price": price,
            "deviation": 20,
            "magic": 999999,
            "comment": "Close US500m position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result is None:
            print("No response from server")
        elif result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to close: {result.retcode} - {result.comment}")
        else:
            print(f"Successfully closed position {p.ticket}")
            
    mt5.shutdown()

if __name__ == '__main__':
    main()
