import os
import sys
from datetime import datetime, timedelta, timezone

def main():
    print("=== SYSTEM HEARTBEAT & PROCESS STATUS ===")
    hb_path = "logs/heartbeat.txt"
    if os.path.exists(hb_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(hb_path))
        with open(hb_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        print(f"Heartbeat: {mtime} | Status: {content}")
    
    pid_path = "logs/bot.pid"
    if os.path.exists(pid_path):
        with open(pid_path, "r", encoding="utf-8") as f:
            print(f"bot.pid: {f.read().strip()}")
            
    print("\n=== MT5 TRADE HISTORY (2026-07-26 to 2026-08-02) ===")
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            print(f"MT5 Init Error: {mt5.last_error()}")
            return

        acc = mt5.account_info()
        if acc:
            print(f"Account: {acc.login} | Server: {acc.server}")
            print(f"Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f}")

        from_date = datetime(2026, 7, 26, 0, 0, 0, tzinfo=timezone.utc)
        to_date = datetime(2026, 8, 2, 23, 59, 59, tzinfo=timezone.utc)

        deals = mt5.history_deals_get(from_date, to_date)
        if not deals:
            print("No deals returned.")
            mt5.shutdown()
            return

        closed_trades = []
        for d in deals:
            if d.entry in [1, 2]: # Out
                net = d.profit + d.commission + d.swap
                closed_trades.append({
                    "ticket": d.ticket,
                    "order": d.order,
                    "time": datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "symbol": d.symbol,
                    "type": "BUY" if d.type == 1 else "SELL",
                    "volume": d.volume,
                    "price": d.price,
                    "profit": d.profit,
                    "commission": d.commission,
                    "swap": d.swap,
                    "net_pnl": net,
                    "comment": d.comment
                })

        print(f"\nTotal Closed Deals: {len(closed_trades)}")
        total_net = sum(t["net_pnl"] for t in closed_trades)
        wins = [t for t in closed_trades if t["net_pnl"] > 0]
        losses = [t for t in closed_trades if t["net_pnl"] < 0]
        
        print(f"Wins: {len(wins)} | Losses: {len(losses)} | Breakeven: {len(closed_trades) - len(wins) - len(losses)}")
        if closed_trades:
            print(f"Win Rate: {len(wins)/len(closed_trades)*100:.1f}%")
        print(f"Total Net PnL: ${total_net:,.2f}")

        by_symbol = {}
        for t in closed_trades:
            sym = t["symbol"]
            if sym not in by_symbol:
                by_symbol[sym] = {"count": 0, "wins": 0, "net": 0.0}
            by_symbol[sym]["count"] += 1
            if t["net_pnl"] > 0:
                by_symbol[sym]["wins"] += 1
            by_symbol[sym]["net"] += t["net_pnl"]

        print("\n--- SYMBOL BREAKDOWN ---")
        for sym, s in by_symbol.items():
            wr = (s["wins"]/s["count"]*100) if s["count"] else 0
            print(f"  {sym:10s}: {s['count']:2d} trades | WR: {wr:5.1f}% | PnL: ${s['net']:8.2f}")

        print("\n--- DETAILED TRADES LIST ---")
        for t in closed_trades:
            print(f"  [{t['time']}] {t['symbol']} {t['type']} Vol:{t['volume']} Price:{t['price']} NetPnL:${t['net_pnl']:.2f} ({t['comment']})")

        positions = mt5.positions_get()
        print(f"\n--- CURRENT OPEN POSITIONS ({len(positions) if positions else 0}) ---")
        if positions:
            for p in positions:
                ptype = "BUY" if p.type == 0 else "SELL"
                ptime = datetime.fromtimestamp(p.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  Ticket: {p.ticket} | {p.symbol} {ptype} | Vol: {p.volume} | Open: {p.price_open} | Curr: {p.price_current} | PnL: ${p.profit:.2f} | {p.comment}")

        mt5.shutdown()
    except Exception as e:
        print(f"MT5 Exception: {e}")

if __name__ == "__main__":
    main()
