import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
log_path = Path("logs/audit_2026-08-10.jsonl")

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        if data.get("symbol") == "US100":
            ts = data.get("timestamp", "")
            if any(t in ts for t in ["00:00:1", "00:00:2", "01:10:1", "01:10:2", "02:20:1", "02:20:2"]):
                print(f"[{ts}] {data}")
