import json
from pathlib import Path
from datetime import datetime

def main():
    log_path = Path("logs/audit_2026-08-06.jsonl")
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                ts_str = data.get("timestamp")
                ts = datetime.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S")
                # Filter for Aug 6 between 04:19:00 and 04:21:00 UTC
                if datetime(2026, 8, 6, 4, 19, 0) <= ts <= datetime(2026, 8, 6, 4, 21, 0):
                    print(f"[{ts_str}] Event: {data.get('event') or data.get('severity')} | Symbol: {data.get('symbol')} | Msg: {data.get('message') or data.get('reason')}")
            except Exception:
                pass

if __name__ == '__main__':
    main()
