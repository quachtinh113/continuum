import json
import glob
import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

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
    else:
        pnl = pips_diff * lot * 100000
    return pnl

def analyze_period(log_files):
    open_cycles = {}  # (symbol, direction) or symbol -> list of position components
    closed_cycles = []
    
    # We maintain active cycles and DCA layers
    for fpath in log_files:
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
                                "lot": data.get("lot") or data.get("lot_size") or 0.01,
                                "layer": data.get("layer", 1),
                                "time": ts
                            })
                    elif evt == "CYCLE_CLOSE":
                        cycle = open_cycles.pop(symbol, None)
                        close_p = data.get("price") or 0.0
                        reason = data.get("reason") or "UNKNOWN"
                        
                        if cycle:
                            direction = cycle["direction"]
                            open_p = cycle["open_price"]
                            main_lot = cycle["lot"]
                            
                            main_pnl = calculate_pnl(symbol, direction, open_p, close_p, main_lot)
                            total_pnl = main_pnl
                            total_lot = main_lot
                            
                            dca_pnls = []
                            for dca in cycle["dca_layers"]:
                                d_pnl = calculate_pnl(symbol, direction, dca["price"], close_p, dca["lot"])
                                total_pnl += d_pnl
                                total_lot += dca["lot"]
                                dca_pnls.append(d_pnl)
                                
                            closed_cycles.append({
                                "symbol": symbol,
                                "direction": direction,
                                "open_time": cycle["open_time"],
                                "close_time": ts,
                                "open_price": open_p,
                                "close_price": close_p,
                                "main_lot": main_lot,
                                "total_lot": total_lot,
                                "dca_count": len(cycle["dca_layers"]),
                                "reason": reason,
                                "pnl": total_pnl,
                                "file": os.path.basename(fpath)
                            })
                        else:
                            # Cycle close without open record in window (opened earlier)
                            # Estimate using price or check if we had direction
                            closed_cycles.append({
                                "symbol": symbol,
                                "direction": data.get("direction", "UNKNOWN"),
                                "open_time": "PREVIOUS_PERIOD",
                                "close_time": ts,
                                "open_price": 0.0,
                                "close_price": close_p,
                                "main_lot": 0.01,
                                "total_lot": 0.01,
                                "dca_count": 0,
                                "reason": reason,
                                "pnl": 0.0, # Cannot compute exact without open price
                                "file": os.path.basename(fpath),
                                "orphan": True
                            })
                except Exception:
                    pass
                    
    return closed_cycles, open_cycles

def main():
    print("==========================================================================")
    print("              BÁO CÁO LOG KIỂM TRA LỢI NHUẬN VÀ LỊCH SỬ GIAO DỊCH         ")
    print("==========================================================================\n")

    all_logs = sorted(glob.glob("logs/audit_2026-08-*.jsonl"))
    print(f"Tổng số file log tháng 8/2026 tìm thấy: {len(all_logs)} file(s)")

    # Group files by week
    # This week: Aug 10 - Aug 16 (2026-08-10 to 2026-08-16)
    # Last week: Aug 03 - Aug 09 (2026-08-03 to 2026-08-09)
    # Earlier: Aug 01 - Aug 02
    
    this_week_files = [f for f in all_logs if "audit_2026-08-10.jsonl" <= os.path.basename(f) <= "audit_2026-08-16.jsonl"]
    last_week_files = [f for f in all_logs if "audit_2026-08-03.jsonl" <= os.path.basename(f) <= "audit_2026-08-09.jsonl"]
    
    print(f"Files tuần này (10/08 - 16/08/2026): {[os.path.basename(f) for f in this_week_files]}")
    print(f"Files tuần trước (03/08 - 09/08/2026): {[os.path.basename(f) for f in last_week_files]}\n")

    # Analyze full August for full context
    all_closed, current_open = analyze_period(all_logs)

    # Filter closed trades by week
    this_week_trades = [c for c in all_closed if any(f in c["file"] for f in [os.path.basename(x) for x in this_week_files])]
    last_week_trades = [c for c in all_closed if any(f in c["file"] for f in [os.path.basename(x) for x in last_week_files])]

    # 1. TUẦN NÀY
    print("--------------------------------------------------------------------------")
    print("📌 1. KẾT QUẢ GIAO DỊCH TUẦN NÀY (10/08/2026 - 16/08/2026)")
    print("--------------------------------------------------------------------------")
    if not this_week_trades:
        print("  Không có chu kỳ (cycle) nào ĐÃ ĐÓNG trong tuần này.")
    else:
        tot_pnl = sum(t["pnl"] for t in this_week_trades)
        wins = sum(1 for t in this_week_trades if t["pnl"] > 0)
        losses = sum(1 for t in this_week_trades if t["pnl"] < 0)
        win_rate = (wins / len(this_week_trades) * 100) if this_week_trades else 0
        
        print(f"  • Tổng số cycle đã hoàn tất : {len(this_week_trades)}")
        print(f"  • Chu kỳ Thắng (Win)         : {wins}")
        print(f"  • Chu kỳ Thua (Loss)         : {losses}")
        print(f"  • Tỷ lệ thắng (Win Rate)    : {win_rate:.1f}%")
        print(f"  • TỔNG LỢI NHUẬN (PnL)       : ${tot_pnl:+.2f} USD\n")

        print("  Chi tiết các giao dịch tuần này:")
        print(f"  {'Ngày/File':18s} | {'Symbol':7s} | {'Dir':4s} | {'Open Px':9s} | {'Close Px':9s} | {'Lot':5s} | {'PnL ($)':10s} | {'Lý do đóng'}")
        print("  ------------------------------------------------------------------------------------------------------")
        for t in this_week_trades:
            ts_short = t['close_time'][5:16].replace('T', ' ') if len(t['close_time']) >= 16 else t['file']
            print(f"  {ts_short:18s} | {t['symbol']:7s} | {t['direction']:4s} | {t['open_price']:9.2f} | {t['close_price']:9.2f} | {t['total_lot']:5.2f} | ${t['pnl']:+9.2f} | {t['reason']}")

    # 2. TUẦN TRƯỚC (COMPARE)
    print("\n--------------------------------------------------------------------------")
    print("📌 2. KẾT QUẢ GIAO DỊCH TUẦN TRƯỚC (03/08/2026 - 09/08/2026)")
    print("--------------------------------------------------------------------------")
    if last_week_trades:
        tot_pnl_lw = sum(t["pnl"] for t in last_week_trades)
        wins_lw = sum(1 for t in last_week_trades if t["pnl"] > 0)
        losses_lw = sum(1 for t in last_week_trades if t["pnl"] < 0)
        win_rate_lw = (wins_lw / len(last_week_trades) * 100) if last_week_trades else 0
        
        print(f"  • Tổng số cycle đã hoàn tất : {len(last_week_trades)}")
        print(f"  • Chu kỳ Thắng / Thua       : {wins_lw} Thắng / {losses_lw} Thua")
        print(f"  • Tỷ lệ thắng (Win Rate)    : {win_rate_lw:.1f}%")
        print(f"  • TỔNG LỢI NHUẬN (PnL)       : ${tot_pnl_lw:+.2f} USD\n")

        print("  Chi tiết các giao dịch tuần trước:")
        print(f"  {'Ngày/File':18s} | {'Symbol':7s} | {'Dir':4s} | {'Open Px':9s} | {'Close Px':9s} | {'Lot':5s} | {'PnL ($)':10s} | {'Lý do đóng'}")
        print("  ------------------------------------------------------------------------------------------------------")
        for t in last_week_trades:
            ts_short = t['close_time'][5:16].replace('T', ' ') if len(t['close_time']) >= 16 else t['file']
            print(f"  {ts_short:18s} | {t['symbol']:7s} | {t['direction']:4s} | {t['open_price']:9.2f} | {t['close_price']:9.2f} | {t['total_lot']:5.2f} | ${t['pnl']:+9.2f} | {t['reason']}")

    # 3. TRẠNG THÁI HIỆN TẠI (OPEN POSITIONS)
    print("\n--------------------------------------------------------------------------")
    print("📌 3. CÁC LỆNH ĐANG MỞ HOẶC ĐANG CHẠY (ACTIVE OPEN CYCLES)")
    print("--------------------------------------------------------------------------")
    if not current_open:
        print("  Hiện tại không có lệnh/chu kỳ nào đang mở.")
    else:
        for sym, c in current_open.items():
            print(f"  • {sym}: {c['direction']} | Open: {c['open_price']} | Lot: {c['lot']} | Open Time: {c['open_time']} | DCA Layers: {len(c['dca_layers'])}")

    # 4. TỔNG KẾT THEO SYMBOL TRONG THÁNG 8
    print("\n--------------------------------------------------------------------------")
    print("📌 4. THỐNG KÊ LỢI NHUẬN THEO CẶP TIỀN / TÀI SẢN (THÁNG 8/2026)")
    print("--------------------------------------------------------------------------")
    sym_summary = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": 0.0})
    for t in all_closed:
        sym_summary[t["symbol"]]["count"] += 1
        if t["pnl"] > 0:
            sym_summary[t["symbol"]]["wins"] += 1
        sym_summary[t["symbol"]]["pnl"] += t["pnl"]

    print(f"  {'Symbol':10s} | {'Số Lệnh':8s} | {'Win Rate':10s} | {'Tổng PnL ($)'}")
    print("  --------------------------------------------------")
    tot_aug_pnl = sum(t["pnl"] for t in all_closed)
    for sym, data in sym_summary.items():
        wr = (data["wins"] / data["count"] * 100) if data["count"] > 0 else 0
        print(f"  {sym:10s} | {data['count']:8d} | {wr:9.1f}% | ${data['pnl']:+10.2f}")
    print("  --------------------------------------------------")
    print(f"  TỔNG THÁNG 8 : {len(all_closed)} lệnh   |             | ${tot_aug_pnl:+10.2f} USD")
    print("==========================================================================")

if __name__ == "__main__":
    main()
