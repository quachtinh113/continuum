import json
from pathlib import Path
from collections import defaultdict

logs_dir = Path("logs")
log_files = sorted(logs_dir.glob("audit_2026-08-*.jsonl"))

print(f"Found {len(log_files)} August log files.")

event_types = set()
sample_closed_events = []

for log_file in log_files:
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                evt = data.get("event")
                if evt:
                    event_types.add(evt)
                # Check for pnl, profit, cycle close, trade close
                if evt in ["CYCLE_CLOSE", "TRADE_CLOSE", "POSITION_CLOSE", "CLOSE"] or "pnl" in str(data).lower() or "profit" in str(data).lower():
                    if len(sample_closed_events) < 10:
                        sample_closed_events.append((log_file.name, data))
            except Exception:
                pass

print("Event types found:", event_types)
print("\nSample closed/pnl events:")
for fname, ev in sample_closed_events[:5]:
    print(f"--- {fname} ---")
    print(json.dumps(ev, indent=2))
