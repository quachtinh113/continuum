import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
import sys

def main():
    print("Connecting to MetaTrader 5...")
    if not mt5.initialize():
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        sys.exit(1)

    # Bot restart time
    restart_time_utc = datetime(2026, 6, 17, 14, 24, 0, tzinfo=timezone.utc)
    print(f"Bot restart time: {restart_time_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    positions = mt5.positions_get()
    if positions is None:
        print(f"Failed to get active positions: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)

    if len(positions) == 0:
        print("No active positions open.")
        mt5.shutdown()
        sys.exit(0)

    print(f"\nScanning {len(positions)} open positions for orphaned trades...")
    orphaned_tickets = []

    for pos in positions:
        pos_dict = pos._asdict()
        ticket = pos_dict['ticket']
        symbol = pos_dict['symbol']
        pos_type = pos_dict['type']
        volume = pos_dict['volume']
        price_open = pos_dict['price_open']
        profit = pos_dict['profit']
        
        # open time in UTC
        open_time = datetime.fromtimestamp(pos_dict['time'], tz=timezone.utc)
        
        is_orphaned = open_time < restart_time_utc
        status = "ORPHANED [WARNING]" if is_orphaned else "TRACKED [OK]"
        
        print(f"Ticket: {ticket:<9} | Symbol: {symbol:<8} | Type: {'BUY' if pos_type == 0 else 'SELL'} | Vol: {volume:.2f} | Open Px: {price_open:.5f} | Open Time: {open_time.strftime('%H:%M:%S')} UTC | Profit: {profit:+.2f} USD | {status}")
        
        if is_orphaned:
            orphaned_tickets.append((ticket, symbol, pos_type, volume))

    if not orphaned_tickets:
        print("\nNo orphaned positions found.")
        mt5.shutdown()
        sys.exit(0)

    print(f"\nFound {len(orphaned_tickets)} orphaned positions. Closing them now...")
    
    for ticket, symbol, pos_type, volume in orphaned_tickets:
        # To close, we need to send opposite order
        # BUY to close SELL (pos_type 1)
        # SELL to close BUY (pos_type 0)
        action_type = 0 if pos_type == 1 else 1
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            print(f"Failed to get tick for {symbol}. Skipping close.")
            continue
            
        price = tick.ask if action_type == 0 else tick.bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": action_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 999999,
            "comment": "Close Orphaned Trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result is None:
            print(f"Close request failed for ticket {ticket}: No response from server.")
        elif result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Close request failed for ticket {ticket}: Retcode {result.retcode} - {result.comment}")
        else:
            print(f"Successfully closed orphaned ticket {ticket} for {symbol}")

    mt5.shutdown()

if __name__ == "__main__":
    main()
