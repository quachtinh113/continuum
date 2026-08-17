import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
log_path = Path("logs/audit_2026-08-10.jsonl")

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        sym = data.get("symbol", "")
        evt = data.get("event", "")
        if sym == "US100":
            ts = data.get("timestamp", "")
            if any(t in ts for t in ["00:00:27", "01:10:21", "02:20:20"]):
                print(f"[{ts}] {data}")
