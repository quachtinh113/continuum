import json
from pathlib import Path
from datetime import datetime

def main():
    log_path = Path("logs/audit_2026-08-06.jsonl")
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                if data.get("symbol") == "US100":
                    ts_str = data.get("timestamp")
                    ts = datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
                    if ts >= datetime(2026, 8, 6, 10, 13, 0):
                        print(line.strip())
            except Exception:
                pass

if __name__ == '__main__':
    main()
