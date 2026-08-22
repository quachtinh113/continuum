import sys
import os
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5

def check_pnl():
    if not mt5.initialize():
        print("MT5 initialization failed:", mt5.last_error())
        return

    acc = mt5.account_info()
    if not acc:
        print("Failed to get account info.")
        mt5.shutdown()
        return

    print("==========================================================================")
    print("               V9 CONTINUUM: PERFORMANCE & AUDIT REPORT                   ")
    print("==========================================================================")
    print(f" Account   : {acc.login} ({acc.server})")
    print(f" Balance   : ${acc.balance:,.2f}")
    print(f" Equity    : ${acc.equity:,.2f}")
    print(f" Margin    : ${acc.margin:,.2f} | Free Margin: ${acc.margin_free:,.2f}")
    print("==========================================================================")

    now_utc = datetime.now(timezone.utc)
    start_of_today_utc = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=timezone.utc)
    start_of_week_utc = start_of_today_utc - timedelta(days=start_of_today_utc.weekday())
    start_of_month_utc = datetime(now_utc.year, now_utc.month, 1, 0, 0, 0, tzinfo=timezone.utc)

    # 1. Deals Today
    deals_today = mt5.history_deals_get(start_of_today_utc, now_utc + timedelta(hours=1)) or []
    closed_today = [d for d in deals_today if d.entry in [1, 2, 3] and d.profit != 0]

    print(f"\n--- 1. TODAY'S CLOSED DEALS ({start_of_today_utc.strftime('%Y-%m-%d')} UTC) ---")
    if not closed_today:
        print("  No closed deals yet today.")
    else:
        wins, losses, breakevens = 0, 0, 0
        total_pnl = 0.0
        for d in closed_today:
            deal_time = datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%H:%M:%S")
            pnl = d.profit + d.commission + d.swap
            total_pnl += pnl
            direction = "BUY" if d.type == 0 else "SELL"
            outcome = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
            if pnl > 0: wins += 1
            elif pnl < 0: losses += 1
            else: breakevens += 1
            print(f"  [{deal_time} UTC] Ticket: {d.ticket} | {d.symbol} {direction} {d.volume:.2f} lot | "
                  f"Price: {d.price} | PnL: ${pnl:+.2f} ({outcome}) | {d.comment}")

        win_rate = (wins / len(closed_today) * 100) if closed_today else 0
        print(f"  --> Today Summary : {len(closed_today)} trades ({wins}W / {losses}L) | WR: {win_rate:.1f}% | Net PnL: ${total_pnl:+,.2f}")

    # 2. Deals This Week
    deals_week = mt5.history_deals_get(start_of_week_utc, now_utc + timedelta(hours=1)) or []
    closed_week = [d for d in deals_week if d.entry in [1, 2, 3] and d.profit != 0]
    week_wins = sum(1 for d in closed_week if (d.profit + d.commission + d.swap) > 0)
    week_losses = sum(1 for d in closed_week if (d.profit + d.commission + d.swap) < 0)
    week_pnl = sum(d.profit + d.commission + d.swap for d in closed_week)
    week_wr = (week_wins / len(closed_week) * 100) if closed_week else 0

    print(f"\n--- 2. WEEK-TO-DATE PERFORMANCE ---")
    print(f"  Total Closed Deals : {len(closed_week)} ({week_wins}W / {week_losses}L)")
    print(f"  Week Win Rate      : {week_wr:.1f}%")
    print(f"  Week Net Realized  : ${week_pnl:+,.2f}")

    # 3. Open Positions
    open_positions = mt5.positions_get() or []
    print(f"\n--- 3. CURRENT OPEN POSITIONS ({len(open_positions)}) ---")
    if not open_positions:
        print("  No open positions currently (Clean book).")
    else:
        total_unrealized = 0.0
        for pos in open_positions:
            open_time = datetime.fromtimestamp(pos.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            direction = "BUY" if pos.type == 0 else "SELL"
            pnl = pos.profit + pos.swap
            total_unrealized += pnl
            print(f"  Ticket: {pos.ticket} | {pos.symbol} {direction} {pos.volume:.2f} lot | "
                  f"Open: {pos.price_open} | Current: {pos.price_current} | PnL: ${pnl:+.2f} | Open: {open_time} UTC")
        print(f"  --> Total Floating PnL: ${total_unrealized:+,.2f}")

    print("==========================================================================\n")
    mt5.shutdown()

if __name__ == "__main__":
    check_pnl()
