import json
from pathlib import Path
from collections import Counter
from datetime import datetime
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    log_paths = [Path("logs/audit_2026-08-06.jsonl"), Path("logs/audit_2026-08-07.jsonl")]
    
    for log_path in log_paths:
        if not log_path.exists():
            continue
            
        print(f"\n==========================================")
        print(f"Post-calibration audit lines in {log_path.name}:")
        
        symbols_scanned = Counter()
        veto_counts = Counter()
        
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    ts_str = data.get("timestamp")
                    # Parse timestamp (e.g. 2026-08-06T00:00:04.005195+00:00)
                    # We can parse the first 19 chars for simplicity
                    ts = datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
                    
                    # Filter for post-calibration (only needed for Aug 6)
                    if log_path.name == "audit_2026-08-06.jsonl" and ts < datetime(2026, 8, 6, 10, 13, 0):
                        continue
                        
                    sym = data.get("symbol", "None")
                    symbols_scanned[sym] += 1
                    
                    risk = data.get("risk_decision") or data.get("execution_action")
                    if risk == "VETOED" or risk == "BLOCKED":
                        reason = data.get("reason", "")
                        veto_counts[reason] += 1
                except Exception as e:
                    pass
                    
        print(f"Symbols scanned count:")
        for sym, cnt in symbols_scanned.items():
            print(f"  {sym:<8} │ {cnt}")
            
        print(f"Veto/Block reasons count (Top 5):")
        for reason, cnt in veto_counts.most_common(5):
            print(f"  {reason:<45} │ {cnt}")

if __name__ == '__main__':
    main()
