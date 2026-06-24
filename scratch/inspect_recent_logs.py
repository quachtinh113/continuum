import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def inspect_recent(log_path, count=100):
    print(f"\n==========================================")
    print(f"LAST {count} LINES IN: {log_path.name}")
    print(f"==========================================")
    
    if not log_path.exists():
        print("File does not exist.")
        return
        
    lines = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                lines.append(line.strip())
                
    start_idx = max(0, len(lines) - count)
    for i, line in enumerate(lines[start_idx:], start_idx + 1):
        try:
            data = json.loads(line)
            # Re-format to a nice string if it's a decision log
            event = data.get("event")
            timestamp = data.get("timestamp")
            if event:
                print(f"[{i}] [{timestamp}] Event: {event} | {json.dumps(data)}")
            else:
                print(f"[{i}] [{timestamp}] Decision: {data.get('symbol')} ({data.get('signal')}) | Risk: {data.get('risk_decision')} | Action: {data.get('execution_action')} | Reason: {data.get('reason')}")
        except Exception as e:
            print(f"[{i}] Raw: {line}")

if __name__ == "__main__":
    project_root = Path("d:/05_Quant/v9 Continuum")
    inspect_recent(project_root / "logs" / "audit_2026-06-24.jsonl", 100)
