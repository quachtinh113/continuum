import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
log_path = Path("logs/audit_2026-08-10.jsonl")

if not log_path.exists():
    print(f"Log path not found: {log_path}")
    sys.exit(1)

records = []
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except Exception:
                pass

print(f"Loaded {len(records)} records from {log_path}")

# Filter records with trade events, drawdown events, balance/equity events, signal details
print("\n--- NON-SPAM AUDIT EVENTS ---")
for r in records:
    msg = str(r.get("message", ""))
    reason = str(r.get("reason", ""))
    evt = str(r.get("event", ""))
    
    if "Governor blocked" in msg or "Governor blocked" in reason:
        continue
    if "ML filter vetoed" in msg or "ML filter vetoed" in reason:
        continue
        
    print(json.dumps(r, indent=2, ensure_ascii=False))
