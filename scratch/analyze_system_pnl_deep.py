import json
import glob
import os
import sys
import pandas as pd
from collections import defaultdict
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

def calculate_pnl(symbol, direction, open_p, close_p, lot):
    if direction == "BUY":
        pips_diff = close_p - open_p
    else:
        pips_diff = open_p - close_p

    if "JPY" in symbol:
        pnl = (pips_diff / close_p * lot * 100000) if close_p else 0
    elif any(k in symbol for k in ["US30", "US500", "NAS100", "US100"]):
        pnl = pips_diff * lot * 10
    elif "XAU" in symbol:
        pnl = pips_diff * lot * 100
    elif "BTC" in symbol:
        pnl = pips_diff * lot
    else:
        pnl = pips_diff * lot * 100000
    return pnl

def analyze_all_audit_logs():
    all_files = sorted(glob.glob("logs/audit_2026-*.jsonl"))
    print(f"Total audit log files found: {len(all_files)}")
    
    open_cycles = {}
    closed_cycles = []
    reason_stats = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    symbol_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0, "lots": 0.0})
    monthly_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0})

    for fpath in all_files:
        month_key = os.path.basename(fpath)[6:13] # 2026-06, 2026-07, 2026-08
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    evt = data.get("event")
                    symbol = data.get("symbol")
                    ts = data.get("timestamp", "")
                    
                    if not symbol:
                        continue
                        
                    if evt == "CYCLE_OPEN":
                        open_cycles[symbol] = {
                            "symbol": symbol,
                            "direction": data.get("direction", "BUY"),
                            "open_price": data.get("price") or data.get("entry_price") or 0.0,
                            "lot": data.get("lot") or data.get("lot_size") or 0.01,
                            "open_time": ts,
                            "dca_layers": []
                        }
                    elif evt == "DCA_OPEN":
                        if symbol in open_cycles:
                            open_cycles[symbol]["dca_layers"].append({
                                "price": data.get("price") or data.get("dca_price") or 0.0,
                                "lot": data.get("lot") or data.get("lot_size") or 0.01
                            })
                    elif evt == "CYCLE_CLOSE":
                        cycle = open_cycles.pop(symbol, None)
                        close_p = data.get("price") or 0.0
                        reason = data.get("reason") or "UNKNOWN"
                        
                        if cycle:
                            direction = cycle["direction"]
                            open_p = cycle["open_price"]
                            main_lot = cycle["lot"]
                            
                            total_pnl = calculate_pnl(symbol, direction, open_p, close_p, main_lot)
                            total_lot = main_lot
                            
                            for dca in cycle["dca_layers"]:
                                total_pnl += calculate_pnl(symbol, direction, dca["price"], close_p, dca["lot"])
                                total_lot += dca["lot"]
                                
                            item = {
                                "symbol": symbol,
                                "direction": direction,
                                "open_time": cycle["open_time"],
                                "close_time": ts,
                                "open_price": open_p,
                                "close_price": close_p,
                                "lot": total_lot,
                                "reason": reason,
                                "pnl": total_pnl,
                                "month": month_key
                            }
                            closed_cycles.append(item)
                            
                            # Aggregations
                            reason_stats[reason]["count"] += 1
                            reason_stats[reason]["pnl"] += total_pnl
                            
                            symbol_stats[symbol]["count"] += 1
                            symbol_stats[symbol]["pnl"] += total_pnl
                            symbol_stats[symbol]["lots"] += total_lot
                            if total_pnl > 0:
                                symbol_stats[symbol]["wins"] += 1
                                
                            monthly_stats[month_key]["count"] += 1
                            monthly_stats[month_key]["pnl"] += total_pnl
                            if total_pnl > 0:
                                monthly_stats[month_key]["wins"] += 1
                except Exception:
                    pass

    print("\n==========================================================================")
    print("                PHÂN TÍCH PnL TỔNG THỂ HỆ THỐNG CONTINUUM V9              ")
    print("==========================================================================")

    # 1. Monthly Breakdown
    print("\n📌 1. KẾT QUẢ THEO THÁNG:")
    print(f"  {'Tháng':10s} | {'Số Lệnh':8s} | {'Win Rate':10s} | {'Tổng PnL ($)'}")
    print("  --------------------------------------------------")
    for m, d in sorted(monthly_stats.items()):
        wr = (d["wins"] / d["count"] * 100) if d["count"] > 0 else 0
        print(f"  {m:10s} | {d['count']:8d} | {wr:9.1f}% | ${d['pnl']:+12.2f}")

    # 2. Symbol Breakdown
    print("\n📌 2. KẾT QUẢ THEO TÀI SẢN (SYMBOL BREAKDOWN):")
    print(f"  {'Symbol':10s} | {'Số Lệnh':8s} | {'Win Rate':10s} | {'Tổng Lot':10s} | {'Tổng PnL ($)'}")
    print("  -----------------------------------------------------------------")
    for s, d in sorted(symbol_stats.items(), key=lambda x: x[1]["pnl"], reverse=True):
        wr = (d["wins"] / d["count"] * 100) if d["count"] > 0 else 0
        print(f"  {s:10s} | {d['count']:8d} | {wr:9.1f}% | {d['lots']:10.2f} | ${d['pnl']:+12.2f}")

    # 3. Exit Reason Breakdown
    print("\n📌 3. PHÂN TÍCH THEO LÝ DO ĐÓNG LỆNH (EXIT REASON ANALYSIS):")
    print(f"  {'Exit Reason':25s} | {'Số Lệnh':8s} | {'Tổng PnL ($)'}")
    print("  --------------------------------------------------")
    for r, d in sorted(reason_stats.items(), key=lambda x: x[1]["pnl"], reverse=True):
        print(f"  {r:25s} | {d['count']:8d} | ${d['pnl']:+12.2f}")

    total_pnl = sum(c["pnl"] for c in closed_cycles)
    total_trades = len(closed_cycles)
    win_trades = sum(1 for c in closed_cycles if c["pnl"] > 0)
    loss_trades = sum(1 for c in closed_cycles if c["pnl"] < 0)
    win_rate = (win_trades / total_trades * 100) if total_trades else 0
    
    print("\n==========================================================================")
    print(f"🎯 TỔNG CỘNG HỆ THỐNG: {total_trades} LỆNH | Win Rate: {win_rate:.1f}% | Tổng PnL: ${total_pnl:+.2f} USD")
    print("==========================================================================")

    # Check 18m weekly csv if present
    if os.path.exists("logs/pnl_18months_weekly.csv"):
        df_csv = pd.read_csv("logs/pnl_18months_weekly.csv")
        print("\n📌 4. THỐNG KÊ BACKTEST / HISTORICAL WEEKLY CSV (18 MONTHS):")
        print(f"  - Số tuần ghi nhận: {len(df_csv)}")
        if "pnl" in df_csv.columns:
            tot_csv_pnl = df_csv["pnl"].sum()
            win_weeks = (df_csv["pnl"] > 0).sum()
            print(f"  - Win Weeks: {win_weeks}/{len(df_csv)} ({win_weeks/len(df_csv)*100:.1f}%)")
            print(f"  - Total Historical CSV PnL: ${tot_csv_pnl:+.2f}")
            if "drawdown" in df_csv.columns:
                print(f"  - Max Drawdown: {df_csv['drawdown'].min():.2f}%")

if __name__ == "__main__":
    analyze_all_audit_logs()
