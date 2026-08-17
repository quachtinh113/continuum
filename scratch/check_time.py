import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
log_path = Path("logs/audit_2026-08-10.jsonl")

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        ts = data.get("timestamp", "")
        if "02:47:" in ts:
            print(f"[{ts}] {data}")
