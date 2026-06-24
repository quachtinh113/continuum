import sys
import json
from pathlib import Path
from datetime import datetime

# Reconfigure stdout to use utf-8 to avoid encoding errors on Windows console
sys.stdout.reconfigure(encoding='utf-8')

def analyze_drawdowns(log_path):
    print(f"\n==========================================")
    print(f"DRAWDOWN ANALYSIS FOR: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    first_breach = None
    last_breach = None
    breach_count = 0
    
    interleaving_events = []
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                event = data.get("event")
                message = data.get("message", "")
                timestamp = data.get("timestamp")
                
                is_breach = False
                if event == "ERROR" and "Drawdown Limit Breached" in message:
                    is_breach = True
                    breach_count += 1
                    if first_breach is None:
                        first_breach = (line_num, timestamp, message, data)
                    last_breach = (line_num, timestamp, message, data)
                
                if not is_breach and event in ["CYCLE_OPEN", "CYCLE_CLOSE", "DCA_OPEN", "DCA_CLOSE"]:
                    interleaving_events.append((line_num, timestamp, event, data))
            except Exception as e:
                pass
                
    if first_breach:
        print(f"Total breach logs: {breach_count}")
        print(f"First Breach at Line {first_breach[0]} [{first_breach[1]}]:")
        print(f"  Message: {first_breach[2]}")
        print(f"  Data: {json.dumps(first_breach[3], indent=2)}")
        print(f"Last Breach at Line {last_breach[0]} [{last_breach[1]}]:")
        print(f"  Message: {last_breach[2]}")
        print(f"  Data: {json.dumps(last_breach[3], indent=2)}")
    else:
        print("No drawdown breaches found.")
        
    if interleaving_events:
        print(f"\nOther trading events ({len(interleaving_events)}):")
        for num, ts, ev, data in interleaving_events[:15]:
            print(f"  Line {num} [{ts}] {ev}: {json.dumps(data)}")
        if len(interleaving_events) > 15:
            print(f"  ... and {len(interleaving_events) - 15} more trading events.")
    else:
        print("\nNo trade execution events (CYCLE_OPEN/CLOSE, DCA_OPEN) found in this log.")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    analyze_drawdowns(project_root / "logs" / "audit_2026-06-23.jsonl")
    analyze_drawdowns(project_root / "logs" / "audit_2026-06-24.jsonl")
