import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def find_status_changes(log_path):
    print(f"\n==========================================")
    print(f"STATUS CHANGES & TRADE TIMELINE FOR: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    last_was_breach = False
    breach_streak = 0
    streak_start_ts = None
    streak_end_ts = None
    
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception as e:
                continue
                
            event = data.get("event")
            message = data.get("message", "")
            timestamp = data.get("timestamp")
            
            is_breach = (event == "ERROR" and "Drawdown Limit Breached" in message)
            
            if is_breach:
                if not last_was_breach:
                    if breach_streak > 0:
                        print(f"  [{streak_start_ts} to {streak_end_ts}] - Breached/Locked for {breach_streak} ticks")
                    streak_start_ts = timestamp
                    breach_streak = 1
                else:
                    breach_streak += 1
                streak_end_ts = timestamp
                last_was_breach = True
            else:
                if last_was_breach:
                    print(f"  [{streak_start_ts} to {streak_end_ts}] - Breached/Locked for {breach_streak} ticks")
                    print(f"Line {line_num} [{timestamp}]: Status transitioned to OPERATIONAL (or non-breach log) - Event: {event}, Message: {message[:100]}")
                    breach_streak = 0
                    last_was_breach = False
                
                # Print interesting non-breach messages (excluding standard ML Veto logs)
                is_veto = ("ML filter vetoed" in message or data.get("reason", "").startswith("ML filter vetoed") or data.get("reason", "").startswith("Governor blocked"))
                if not is_veto and event not in ["UNKNOWN", None]:
                    print(f"Line {line_num} [{timestamp}]: Event: {event} | {message[:120]} | Data: {list(data.keys())}")
                        
        if last_was_breach and breach_streak > 0:
            print(f"  [{streak_start_ts} to {streak_end_ts}] - Breached/Locked for {breach_streak} ticks (Ends file)")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    find_status_changes(project_root / "logs" / "audit_2026-06-23.jsonl")
    find_status_changes(project_root / "logs" / "audit_2026-06-24.jsonl")
