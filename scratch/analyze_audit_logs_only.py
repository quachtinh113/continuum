import os
import glob
import json
from datetime import datetime

def main():
    print("=== AUDIT LOG ANALYSIS FOR LAST WEEK (2026-07-26 to 2026-08-02) ===", flush=True)
    
    hb_path = "logs/heartbeat.txt"
    if os.path.exists(hb_path):
        mtime = datetime.fromtimestamp(os.path.getmtime(hb_path))
        with open(hb_path, "r", encoding="utf-8") as f:
            print(f"Heartbeat MTime: {mtime} | Content: {f.read().strip()}", flush=True)
            
    pid_path = "logs/bot.pid"
    if os.path.exists(pid_path):
        with open(pid_path, "r", encoding="utf-8") as f:
            print(f"bot.pid: {f.read().strip()}", flush=True)

    log_files = sorted(glob.glob("logs/audit_2026-07-*.jsonl") + glob.glob("logs/audit_2026-08-*.jsonl"))
    # filter files for last week (2026-07-26 onwards)
    target_files = [f for f in log_files if os.path.basename(f) >= "audit_2026-07-26.jsonl"]
    
    print(f"\nFound {len(target_files)} log files for last week: {[os.path.basename(f) for f in target_files]}", flush=True)
    
    cycle_closed = []
    cycle_open = []
    vetoes = []
    errors = []
    
    for fpath in target_files:
        fname = os.path.basename(fpath)
        print(f"Analyzing {fname}...", flush=True)
        with open(fpath, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                try:
                    data = json.loads(line)
                    evt = data.get("event", "")
                    lvl = data.get("level", "")
                    
                    if "CYCLE_CLOSE" in evt or "TRADE_CLOSE" in evt:
                        cycle_closed.append((fname, data))
                    elif "CYCLE_OPEN" in evt or "TRADE_OPEN" in evt:
                        cycle_open.append((fname, data))
                    elif "VETO" in evt or "REJECT" in evt:
                        vetoes.append((fname, data))
                    if lvl in ["ERROR", "WARNING"] or "ERROR" in evt or "WARNING" in evt:
                        if len(errors) < 50:
                            errors.append((fname, line_no, data))
                except Exception:
                    pass

    print(f"\n--- AUDIT SUMMARY ---", flush=True)
    print(f"Total Cycles/Trades Opened: {len(cycle_open)}", flush=True)
    print(f"Total Cycles/Trades Closed: {len(cycle_closed)}", flush=True)
    print(f"Total Vetoes/Rejections: {len(vetoes)}", flush=True)
    print(f"Total Errors/Warnings: {len(errors)}", flush=True)
    
    if cycle_closed:
        print("\n--- CLOSED TRADES SUMMARY FROM LOGS ---", flush=True)
        total_pnl = 0.0
        for fname, d in cycle_closed:
            pnl = d.get("realized_pnl", d.get("pnl", d.get("net_pnl", 0.0)))
            total_pnl += pnl
            print(f"  [{d.get('timestamp')}] {d.get('symbol', 'N/A')} | Event: {d.get('event')} | PnL: ${pnl:.2f} | Reason: {d.get('reason', d.get('message'))}", flush=True)
        print(f"\nTotal Realized PnL (from logs): ${total_pnl:.2f}", flush=True)

    if errors:
        print("\n--- SAMPLE ERRORS / WARNINGS ---", flush=True)
        for fname, lno, d in errors[:20]:
            print(f"  [{d.get('timestamp')}] [{fname}:{lno}] [{d.get('event')}] {d.get('message', d.get('msg', str(d)))}", flush=True)

if __name__ == "__main__":
    main()
