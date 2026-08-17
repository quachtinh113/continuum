import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
log_path = Path("logs/audit_2026-08-10.jsonl")

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        msg = str(data.get("message", ""))
        evt = str(data.get("event", ""))
        lvl = str(data.get("level", data.get("severity", "")))
        if "Drawdown" in msg or "Emergency" in msg or "LOCKED" in msg and "breach" in msg.lower():
            print(json.dumps(data, indent=2))
        if evt in ["EMERGENCY_CLOSE", "SYSTEM_LOCK", "DRAWDOWN_BREACH"]:
            print(json.dumps(data, indent=2))
