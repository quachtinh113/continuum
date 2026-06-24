import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def check_overnight_trades(log_path):
    print(f"\n==========================================")
    print(f"OVERNIGHT TRADE HISTORY FOR: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    trades = []
    decisions = []
    errors = []
    
    # We are interested in events after 13:12 (the time we restarted the bot)
    start_ts = "2026-06-24T13:12:00"
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                ts = data.get("timestamp", "")
                if ts < start_ts:
                    continue
                    
                event = data.get("event")
                risk_decision = data.get("risk_decision")
                
                if event in ["CYCLE_OPEN", "CYCLE_CLOSE", "DCA_OPEN", "DCA_CLOSE"]:
                    trades.append((line_num, ts, event, data))
                elif risk_decision == "APPROVED" or data.get("execution_action") == "ROUTE":
                    decisions.append((line_num, ts, "APPROVED", data))
                elif event == "ERROR":
                    errors.append((line_num, ts, data))
            except Exception as e:
                pass
                
    print(f"Total overnight execution events: {len(trades)}")
    for num, ts, ev, data in trades:
        print(f"  Line {num} [{ts}] Event: {ev} | Symbol: {data.get('symbol')} | Dir: {data.get('direction')} | Price: {data.get('price') or data.get('dca_price')} | Ticket: {data.get('ticket')}")
        
    print(f"\nTotal APPROVED decisions (routed to broker): {len(decisions)}")
    for num, ts, ev, data in decisions:
        print(f"  Line {num} [{ts}] Approved: {data.get('symbol')} ({data.get('signal')}) | Reason: {data.get('reason')}")
        
    print(f"\nTotal Errors overnight: {len(errors)}")
    for num, ts, data in errors[:20]:
        print(f"  Line {num} [{ts}]: {data.get('message')}")
    if len(errors) > 20:
        print(f"  ... and {len(errors) - 20} more errors.")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    check_overnight_trades(project_root / "logs" / "audit_2026-06-24.jsonl")
