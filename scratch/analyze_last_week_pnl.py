import os
import sys
import json
from datetime import datetime, timedelta, timezone

def check_system_status():
    print("=== SYSTEM & BOT PROCESS STATUS ===")
    heartbeat_path = "logs/heartbeat.txt"
    pid_path = "logs/bot.pid"
    
    if os.path.exists(heartbeat_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(heartbeat_path))
        with open(heartbeat_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        print(f"Heartbeat last modified: {mtime} | Content: {content}")
    else:
        print("Heartbeat file not found.")

    if os.path.exists(pid_path):
        with open(pid_path, "r", encoding="utf-8") as f:
            pid = f.read().strip()
        print(f"Bot PID file exists: PID {pid}")
    else:
        print("Bot PID file not found.")

def check_mt5_trades():
    print("\n=== MT5 TRADE HISTORY (LAST WEEK: 2026-07-26 to 2026-08-02) ===")
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            print(f"MT5 initialize failed, error code: {mt5.last_error()}")
            return
        
        account_info = mt5.account_info()
        if account_info:
            print(f"Account #: {account_info.login} | Server: {account_info.server}")
            print(f"Balance: {account_info.balance:.2f} | Equity: {account_info.equity:.2f} | Margin: {account_info.margin:.2f} | Free Margin: {account_info.margin_free:.2f}")

        from_date = datetime(2026, 7, 26, 0, 0, 0, tzinfo=timezone.utc)
        to_date = datetime(2026, 8, 2, 23, 59, 59, tzinfo=timezone.utc)
        
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            print("No deals found or error getting deals.")
            mt5.shutdown()
            return
        
        print(f"Total deals retrieved: {len(deals)}")
        
        # Filter entry/exit deals
        total_profit = 0.0
        total_commission = 0.0
        total_swap = 0.0
        closed_trades = []
        
        for d in deals:
            # deal entry out (1) or out_by (2)
            if d.entry in [1, 2]: # Out / Close
                profit = d.profit + d.commission + d.swap
                total_profit += d.profit
                total_commission += d.commission
                total_swap += d.swap
                closed_trades.append({
                    "ticket": d.ticket,
                    "order": d.order,
                    "time": datetime.fromtimestamp(d.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "symbol": d.symbol,
                    "type": "BUY" if d.type == 1 else "SELL", # opposite of position
                    "volume": d.volume,
                    "price": d.price,
                    "profit": d.profit,
                    "commission": d.commission,
                    "swap": d.swap,
                    "net_pnl": profit,
                    "comment": d.comment
                })
        
        net_total = total_profit + total_commission + total_swap
        wins = [t for t in closed_trades if t["net_pnl"] > 0]
        losses = [t for t in closed_trades if t["net_pnl"] < 0]
        breakevens = [t for t in closed_trades if t["net_pnl"] == 0]
        
        win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0
        gross_win = sum(t["net_pnl"] for t in wins)
        gross_loss = abs(sum(t["net_pnl"] for t in losses))
        profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float('inf')
        
        print(f"\n--- WEEKLY MT5 PnL SUMMARY ---")
        print(f"Closed Trades: {len(closed_trades)}")
        print(f"Wins: {len(wins)} | Losses: {len(losses)} | Breakeven: {len(breakevens)}")
        print(f"Win Rate: {win_rate:.2f}%")
        print(f"Gross Profit: ${gross_win:.2f}")
        print(f"Gross Loss: ${gross_loss:.2f}")
        print(f"Profit Factor: {profit_factor:.2f}")
        print(f"Total Gross Trade PnL: ${total_profit:.2f}")
        print(f"Total Commission: ${total_commission:.2f}")
        print(f"Total Swap: ${total_swap:.2f}")
        print(f"NET PnL: ${net_total:.2f}")
        
        # Breakdown by symbol
        symbols = {}
        for t in closed_trades:
            sym = t["symbol"]
            if sym not in symbols:
                symbols[sym] = {"trades": 0, "wins": 0, "losses": 0, "net_pnl": 0.0}
            symbols[sym]["trades"] += 1
            if t["net_pnl"] > 0:
                symbols[sym]["wins"] += 1
            elif t["net_pnl"] < 0:
                symbols[sym]["losses"] += 1
            symbols[sym]["net_pnl"] += t["net_pnl"]
            
        print("\n--- PnL BY SYMBOL ---")
        for sym, stats in symbols.items():
            wr = (stats["wins"] / stats["trades"] * 100) if stats["trades"] else 0
            print(f"  {sym:10s}: {stats['trades']} trades | Win Rate: {wr:5.1f}% | Net PnL: ${stats['net_pnl']:8.2f}")
            
        # Check open positions
        positions = mt5.positions_get()
        print(f"\n--- CURRENT OPEN POSITIONS ({len(positions) if positions else 0}) ---")
        if positions:
            for p in positions:
                p_type = "BUY" if p.type == 0 else "SELL"
                p_time = datetime.fromtimestamp(p.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  Ticket: {p.ticket} | {p.symbol} {p_type} | Vol: {p.volume} | Open Price: {p.price_open} | Curr: {p.price_current} | Profit: ${p.profit:.2f} | Comment: {p.comment} | Time: {p_time}")

        mt5.shutdown()
    except Exception as e:
        print(f"Error checking MT5 history: {e}")

def parse_logs_summary():
    print("\n=== AUDIT LOGS ANALYSIS (LAST WEEK) ===")
    log_dir = "logs"
    log_files = [
        "audit_2026-07-27.jsonl",
        "audit_2026-07-28.jsonl",
        "audit_2026-07-29.jsonl",
        "audit_2026-07-30.jsonl",
        "audit_2026-07-31.jsonl",
    ]
    
    total_events = 0
    event_counts = {}
    errors_warnings = []
    cycle_events = []
    
    for fname in log_files:
        fpath = os.path.join(log_dir, fname)
        if not os.path.exists(fpath):
            continue
        print(f"Parsing log file: {fname}...")
        with open(fpath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                total_events += 1
                try:
                    data = json.loads(line)
                    evt = data.get("event", "UNKNOWN")
                    level = data.get("level", "INFO")
                    event_counts[evt] = event_counts.get(evt, 0) + 1
                    
                    if level in ["ERROR", "WARNING"] or "error" in evt.lower() or "warning" in evt.lower():
                        if len(errors_warnings) < 30:
                            errors_warnings.append({
                                "file": fname,
                                "line": line_num,
                                "timestamp": data.get("timestamp"),
                                "event": evt,
                                "msg": data.get("message", data.get("msg", str(data)))
                            })
                    if "CYCLE" in evt or "SIGNAL" in evt or "VETO" in evt or "TRADE" in evt:
                        cycle_events.append((fname, evt, data))
                except Exception:
                    pass

    print(f"\nTotal Log Events Processed across files: {total_events}")
    print("Event Type Summary (Top 15):")
    sorted_evts = sorted(event_counts.items(), key=lambda x: x[1], reverse=True)[:15]
    for evt, cnt in sorted_evts:
        print(f"  {evt:35s}: {cnt}")
        
    print(f"\nErrors & Warnings Count (sampled up to 30): {len(errors_warnings)}")
    for ew in errors_warnings[:15]:
        print(f"  [{ew['timestamp']}] [{ew['file']}:{ew['line']}] [{ew['event']}] {ew['msg']}")

if __name__ == "__main__":
    check_system_status()
    check_mt5_trades()
    parse_logs_summary()
