import sys
import os
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

def check_today_pnl():
    if not mt5.initialize():
        print("MT5 initialization failed:", mt5.last_error())
        return

    acc = mt5.account_info()
    if not acc:
        print("Failed to get account info.")
        mt5.shutdown()
        return

    print("==========================================================================")
    print("                    V9 CONTINUUM: TODAY'S PNL REPORT                      ")
    print("==========================================================================")
    print(f" Account  : {acc.login} ({acc.server})")
    print(f" Balance  : ${acc.balance:,.2f}")
    print(f" Equity   : ${acc.equity:,.2f}")
    print(f" Margin   : ${acc.margin:,.2f} | Free Margin: ${acc.margin_free:,.2f}")
    print("==========================================================================")

    # Calculate start of today in UTC
    now_utc = datetime.now(timezone.utc)
    start_of_today_utc = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=timezone.utc)
    start_of_week_utc = start_of_today_utc - timedelta(days=start_of_today_utc.weekday())

    # Fetch deals for today
    deals_today = mt5.history_deals_get(start_of_today_utc, now_utc + timedelta(hours=1)) or []
    
    # Filter only closed trades (entry out / out by)
    closed_today = [d for d in deals_today if d.entry in [1, 2, 3] and d.profit != 0]

    print(f"\n--- 1. TODAY'S CLOSED DEALS ({start_of_today_utc.strftime('%Y-%m-%d')} UTC) ---")
    if not closed_today:
        print("  No deals closed yet today.")
    else:
        wins, losses, breakevens = 0, 0, 0
        total_pnl = 0.0
        total_commission = 0.0
        total_swap = 0.0
        
        for d in closed_today:
            deal_time = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%H:%M:%S")
            pnl = d.profit + d.commission + d.swap
            total_pnl += pnl
            total_commission += d.commission
            total_swap += d.swap
            
            direction = "BUY" if d.type == 0 else "SELL"
            outcome = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
            if pnl > 0: wins += 1
            elif pnl < 0: losses += 1
            else: breakevens += 1

            print(f"  [{deal_time} UTC] Ticket: {d.ticket} | {d.symbol} {direction} {d.volume:.2f} lot | "
                  f"Price: {d.price} | PnL: ${pnl:+.2f} ({outcome}) | Comment: {d.comment}")

        win_rate = (wins / len(closed_today) * 100) if closed_today else 0
        print("--------------------------------------------------------------------------")
        print(f"  Total Closed Today : {len(closed_today)} deals ({wins}W / {losses}L / {breakevens}BE)")
        print(f"  Win Rate           : {win_rate:.1f}%")
        print(f"  Net Realized PnL   : ${total_pnl:+,.2f} (Commission: ${total_commission:.2f}, Swap: ${total_swap:.2f})")

    # Fetch all deals for this week
    deals_week = mt5.history_deals_get(start_of_week_utc, now_utc + timedelta(hours=1)) or []
    closed_week = [d for d in deals_week if d.entry in [1, 2, 3] and d.profit != 0]
    week_pnl = sum(d.profit + d.commission + d.swap for d in closed_week)
    print(f"\n--- 2. THIS WEEK'S NET REALIZED PNL ---")
    print(f"  Total Trades: {len(closed_week)} | Week PnL: ${week_pnl:+,.2f}")

    # Fetch currently open positions
    open_positions = mt5.positions_get() or []
    print(f"\n--- 3. CURRENT OPEN POSITIONS ({len(open_positions)}) ---")
    if not open_positions:
        print("  No open positions currently.")
    else:
        total_unrealized = 0.0
        for pos in open_positions:
            open_time = datetime.fromtimestamp(pos.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            direction = "BUY" if pos.type == 0 else "SELL"
            pnl = pos.profit + pos.swap
            total_unrealized += pnl
            print(f"  Ticket: {pos.ticket} | {pos.symbol} {direction} {pos.volume:.2f} lot | "
                  f"Open Price: {pos.price_open} | Current: {pos.price_current} | Unrealized: ${pnl:+.2f} | Open Time: {open_time} UTC")
        print("--------------------------------------------------------------------------")
        print(f"  Total Unrealized PnL: ${total_unrealized:+,.2f}")

    print("==========================================================================\n")
    mt5.shutdown()

if __name__ == "__main__":
    check_today_pnl()
