import json
import sys
from pathlib import Path

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

log_path = Path("logs/audit_2026-08-10.jsonl")

if not log_path.exists():
    print(f"File not found: {log_path}")
    sys.exit(1)

events = []
with open(log_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            events.append(data)
        except Exception as e:
            pass

print(f"Total log records: {len(events)}")

# Filter out repetitive Governor Block / ML Veto spam to highlight significant actions
important_events = []
governor_block_count = 0
ml_veto_count = 0

for ev in events:
    msg = str(ev.get("message", ""))
    reason = str(ev.get("reason", ""))
    
    if "Governor blocked: System status is LOCKED" in msg or "Governor blocked: System status is LOCKED" in reason:
        governor_block_count += 1
        continue
    if "ML filter vetoed" in msg or "ML filter vetoed" in reason:
        ml_veto_count += 1
        continue
        
    important_events.append(ev)

print(f"Governor Block count: {governor_block_count}")
print(f"ML Veto count: {ml_veto_count}")
print(f"Important events count: {len(important_events)}")
print("="*80)

for ev in important_events:
    ts = ev.get("timestamp", ev.get("time", ""))
    lvl = ev.get("level", ev.get("severity", ""))
    evt = ev.get("event", "")
    msg = ev.get("message", "")
    extra = {k: v for k, v in ev.items() if k not in ["timestamp", "time", "level", "severity", "event", "message"]}
    
    extra_str = f" | {extra}" if extra else ""
    print(f"[{ts}] [{lvl}/{evt}] {msg}{extra_str}")
